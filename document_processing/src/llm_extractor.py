import re
import time
from datetime import datetime
from typing import Optional, Type

import requests
from pydantic import BaseModel, Field, ValidationError

from models import (
    OfficialExtractedFields,
    ParsedDocument,
)


MODEL_NAME = "qwen3:4b"

OLLAMA_URL = (
    "http://localhost:11434/api/generate"
)


# ============================================================
# Промежуточные модели
# ============================================================

class DocumentFacts(BaseModel):
    """
    Факты, относящиеся к документу в целом.
    Без персональных данных конкретного должника.
    """

    document_type: Optional[str] = None

    case_number: Optional[str] = None
    case_date: Optional[str] = None

    debt_period_start: Optional[str] = None
    debt_period_end: Optional[str] = None

    principal_debt: Optional[str] = None
    penalty_amount: Optional[str] = None
    state_duty: Optional[str] = None


class DebtorCandidate(BaseModel):
    """
    Один найденный должник.
    """

    full_name: Optional[str] = None
    birth_date: Optional[str] = None

    street: Optional[str] = None
    house: Optional[str] = None
    apartment: Optional[str] = None

    passport: Optional[str] = None
    snils: Optional[str] = None
    inn: Optional[str] = None


class DebtorsExtraction(BaseModel):
    """
    Список всех найденных должников.
    """

    debtors: list[DebtorCandidate] = Field(
        default_factory=list
    )


# ============================================================
# Regex
# ============================================================

CASE_NUMBER_PATTERN = re.compile(
    r"\b\d{1,3}-\d{1,7}(?:-\d{1,4})?/\d{4}\b"
)

DATE_DMY_PATTERN = re.compile(
    r"\b\d{2}\.\d{2}\.\d{4}\b"
)

DATE_YMD_PATTERN = re.compile(
    r"\b\d{4}-\d{2}-\d{2}\b"
)

MONEY_PATTERN = re.compile(
    r"\b\d[\d\s]*(?:[.,]\d{1,2})?\s*(?:руб|рублей)\b",
    re.IGNORECASE,
)


# ============================================================
# Вызов Ollama
# ============================================================

def call_ollama_json(
    prompt: str,
    response_model: Type[BaseModel],
    *,
    pass_name: str,
    num_predict: int,
) -> BaseModel:
    """
    Отправляет задачу в локальную Qwen через Ollama
    и валидирует ответ по Pydantic JSON-схеме.
    """

    schema = response_model.model_json_schema()

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "format": schema,
        "keep_alive": "10m",
        "options": {
            "temperature": 0,
            "num_ctx": 2048,
            "num_predict": num_predict,
        },
    }

    started = time.perf_counter()

    print(
        f"  Qwen [{pass_name}]: запуск, "
        f"prompt={len(prompt)} символов..."
    )

    try:
        response = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=90,
        )

    except requests.Timeout as exc:
        raise RuntimeError(
            f"Qwen [{pass_name}]: превышен timeout Ollama."
        ) from exc

    except requests.ConnectionError as exc:
        raise RuntimeError(
            f"Qwen [{pass_name}]: Ollama недоступна. "
            "Проверь, что Ollama запущена."
        ) from exc

    except requests.RequestException as exc:
        raise RuntimeError(
            f"Qwen [{pass_name}]: ошибка запроса к Ollama: "
            f"{type(exc).__name__}."
        ) from exc

    elapsed = time.perf_counter() - started

    if response.status_code != 200:
        raise RuntimeError(
            f"Qwen [{pass_name}]: Ollama вернула "
            f"HTTP {response.status_code}."
        )

    try:
        ollama_data = response.json()

    except ValueError as exc:
        raise RuntimeError(
            f"Qwen [{pass_name}]: Ollama вернула "
            "некорректный HTTP JSON."
        ) from exc

    content = ollama_data.get(
        "response",
        "",
    )

    if (
        not isinstance(content, str)
        or not content.strip()
    ):
        raise ValueError(
            f"Qwen [{pass_name}]: модель вернула пустой ответ."
        )

    try:
        result = response_model.model_validate_json(
            content
        )

    except ValidationError as exc:
        raise ValueError(
            f"Qwen [{pass_name}]: ответ модели "
            "не соответствует JSON-схеме "
            f"({exc.error_count()} ошибок валидации)."
        ) from exc

    except Exception as exc:
        raise ValueError(
            f"Qwen [{pass_name}]: не удалось "
            "обработать JSON-ответ модели."
        ) from exc

    print(
        f"  Qwen [{pass_name}]: готово за "
        f"{elapsed:.2f} сек."
    )

    return result


# ============================================================
# Выбор контекста для facts-pass
# ============================================================

FACT_KEYWORDS = (
    "дело",
    "судебный приказ",
    "исполнительный лист",
    "решение",
    "постановление",
    "задолженность",
    "основной долг",
    "долг",
    "пени",
    "пеня",
    "госпошлина",
    "государственная пошлина",
    "государственной пошлины",
    "за период",
    "взыскать",
    "взыскание",
    "руб.",
    "рублей",
)


def find_case_number_candidates(
    text: str,
) -> list[str]:
    """
    Ищет явные номера судебных дел в тексте.
    """

    candidates = []

    for match in CASE_NUMBER_PATTERN.finditer(text):
        value = match.group(0).strip()

        if value not in candidates:
            candidates.append(value)

    return candidates


def build_facts_context(
    text: str,
    max_chars: int = 6000,
) -> str:
    """
    Собирает релевантные фрагменты текста для facts-pass.
    """

    if not text:
        return ""

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    if not lines:
        return text[:max_chars]

    selected_indexes: set[int] = set()

    # Начало документа.
    for index in range(
        min(25, len(lines))
    ):
        selected_indexes.add(index)

    # Юридически значимые строки.
    for index, line in enumerate(lines):
        lower_line = line.lower()

        has_keyword = any(
            keyword in lower_line
            for keyword in FACT_KEYWORDS
        )

        has_case_number = bool(
            CASE_NUMBER_PATTERN.search(line)
        )

        if has_keyword or has_case_number:

            start = max(
                0,
                index - 2,
            )

            end = min(
                len(lines),
                index + 4,
            )

            for nearby_index in range(
                start,
                end,
            ):
                selected_indexes.add(
                    nearby_index
                )

    # Строки с номером дела.
    for index, line in enumerate(lines):

        if CASE_NUMBER_PATTERN.search(line):

            selected_indexes.add(index)

            if index > 0:
                selected_indexes.add(
                    index - 1
                )

            if index + 1 < len(lines):
                selected_indexes.add(
                    index + 1
                )

    # Денежные строки около юридически значимого контекста.
    for index, line in enumerate(lines):

        if not MONEY_PATTERN.search(line):
            continue

        start = max(
            0,
            index - 2,
        )

        end = min(
            len(lines),
            index + 3,
        )

        nearby_text = " ".join(
            lines[start:end]
        ).lower()

        if any(
            keyword in nearby_text
            for keyword in FACT_KEYWORDS
        ):
            for nearby_index in range(
                start,
                end,
            ):
                selected_indexes.add(
                    nearby_index
                )

    ordered_indexes = sorted(
        selected_indexes
    )

    selected_lines = [
        lines[index]
        for index in ordered_indexes
    ]

    context = "\n".join(
        selected_lines
    )

    if len(context) < 500:
        context = text

    if len(context) > max_chars:
        context = context[:max_chars]

    return context


# ============================================================
# Проход №1 — факты документа
# ============================================================

def extract_document_facts(
    document: ParsedDocument,
) -> DocumentFacts:
    """
    Извлекает факты документа.
    """

    context = build_facts_context(
        document.full_text
    )

    print(
        "  Facts context: "
        f"{len(document.full_text)} -> "
        f"{len(context)} символов"
    )

    prompt = f"""
Извлеки факты из российского судебного документа.

Используй только явно указанные в тексте значения.
Если значение отсутствует или неоднозначно — верни null.
Ничего не придумывай.

Поля:
- document_type: только "судебный приказ",
  "исполнительный лист" или "постановление ФССП";
- case_number: номер судебного дела,
  НЕ номер исполнительного производства;
- case_date: дата судебного акта,
  относящаяся к case_number;
- debt_period_start;
- debt_period_end;
- principal_debt;
- penalty_amount;
- state_duty.

Правила извлечения:
- фраза "за период с ДАТА по ДАТА" означает
  debt_period_start и debt_period_end;
- сумма "задолженности" или "основного долга"
  означает principal_debt;
- сумма "пени" или "пеней"
  означает penalty_amount;
- сумма "государственной пошлины" или "госпошлины"
  означает state_duty.

Не путай:
- основной долг и пени;
- госпошлину и общий долг;
- дату судебного акта с другими датами;
- номер дела с номером исполнительного производства.

Даты верни в формате YYYY-MM-DD.
Денежные суммы верни строкой только с числом.

Текст:
{context}
"""

    result = call_ollama_json(
        prompt=prompt,
        response_model=DocumentFacts,
        pass_name="facts",
        num_predict=300,
    )

    return result


# ============================================================
# Проход №2 — должники
# ============================================================

def extract_debtors(
    document: ParsedDocument,
) -> DebtorsExtraction:
    """
    Извлекает всех должников.
    """

    prompt = f"""
Извлеки ВСЕХ должников из российского судебного документа.

Для каждого должника извлеки:
- full_name
- birth_date
- street
- house
- apartment
- passport
- snils
- inn

Правила:
- включай только лиц, прямо указанных как должники;
- каждого должника возвращай отдельным объектом;
- не включай взыскателя, организацию-взыскателя,
  судью, судебного пристава или представителя;
- не объединяй нескольких должников в одного;
- ИНН организации-взыскателя не является ИНН должника;
- ИНН, СНИЛС, паспорт, дату рождения и адрес
  связывай только с конкретным должником;
- если принадлежность реквизита конкретному должнику
  неоднозначна, верни null;
- если значение отсутствует, верни null;
- ничего не придумывай.

Текст:
{document.full_text}
"""

    result = call_ollama_json(
        prompt=prompt,
        response_model=DebtorsExtraction,
        pass_name="debtors",
        num_predict=1200,
    )

    return result


# ============================================================
# Нормализация
# ============================================================

def normalize_date(
    value: Optional[str],
) -> Optional[str]:
    """
    Приводит распространённые форматы дат
    к YYYY-MM-DD.
    """

    if not value:
        return None

    value = value.strip()

    formats = (
        "%Y-%m-%d",
        "%d.%m.%Y",
        "%d/%m/%Y",
    )

    for fmt in formats:
        try:
            parsed = datetime.strptime(
                value,
                fmt,
            )

            return parsed.strftime(
                "%Y-%m-%d"
            )

        except ValueError:
            continue

    return value


def normalize_case_number(
    value: Optional[str],
    text: str,
) -> Optional[str]:
    """
    Исправляет только очевидные ошибки case_number.

    Не пытается придумывать номер дела.
    """

    candidates = find_case_number_candidates(
        text
    )

    # Если Qwen ничего не вернула,
    # но в тексте есть ровно один хороший кандидат.
    if not value:
        if len(candidates) == 1:
            return candidates[0]

        return None

    value = value.strip()

    # Дата точно не является номером дела.
    if (
        DATE_DMY_PATTERN.fullmatch(value)
        or DATE_YMD_PATTERN.fullmatch(value)
    ):
        if len(candidates) == 1:
            return candidates[0]

        return None

    # Уже корректный номер.
    if CASE_NUMBER_PATTERN.fullmatch(value):
        return value

    # Если есть единственный regex-кандидат,
    # используем его вместо OCR-мусора.
    if len(candidates) == 1:
        return candidates[0]

    # Попытка сопоставить повреждённый ответ с кандидатом.
    digits_value = re.sub(
        r"\D",
        "",
        value,
    )

    for candidate in candidates:
        digits_candidate = re.sub(
            r"\D",
            "",
            candidate,
        )

        if not digits_value:
            continue

        if (
            digits_value.endswith(
                digits_candidate
            )
            or digits_candidate.endswith(
                digits_value
            )
        ):
            return candidate

    return value


def normalize_llm_results(
    facts: DocumentFacts,
    debtors_result: DebtorsExtraction,
    document_text: str,
) -> None:
    """
    Минимальная постобработка.
    """

    facts.case_number = normalize_case_number(
        facts.case_number,
        document_text,
    )

    facts.case_date = normalize_date(
        facts.case_date
    )

    facts.debt_period_start = normalize_date(
        facts.debt_period_start
    )

    facts.debt_period_end = normalize_date(
        facts.debt_period_end
    )

    for debtor in debtors_result.debtors:
        debtor.birth_date = normalize_date(
            debtor.birth_date
        )


# ============================================================
# Вспомогательная логика
# ============================================================

def split_name(
    full_name: Optional[str],
) -> tuple[
    Optional[str],
    Optional[str],
    Optional[str],
]:
    """
    Делит ФИО на фамилию, имя, отчество.
    """

    if not full_name:
        return None, None, None

    parts = full_name.strip().split()

    if len(parts) < 2:
        return None, None, None

    last_name = parts[0]
    first_name = parts[1]

    patronymic = (
        parts[2]
        if len(parts) >= 3
        else None
    )

    return (
        last_name,
        first_name,
        patronymic,
    )


def get_common_value(
    debtors: list[DebtorCandidate],
    field_name: str,
) -> Optional[str]:
    """
    Если значение одинаковое у всех должников,
    возвращает его как общее.
    """

    values = []

    for debtor in debtors:

        value = getattr(
            debtor,
            field_name,
            None,
        )

        if value is not None:
            value = value.strip()

        if value:
            values.append(
                value
            )

    if not values:
        return None

    unique_values = set(
        values
    )

    if len(unique_values) == 1:
        return values[0]

    return None


def build_co_defendants_names(
    debtors: list[DebtorCandidate],
) -> Optional[str]:
    """
    Формирует строку со всеми должниками.
    """

    names = [
        debtor.full_name.strip()
        for debtor in debtors
        if debtor.full_name
        and debtor.full_name.strip()
    ]

    if not names:
        return None

    return "; ".join(
        names
    )


# ============================================================
# Merge
# ============================================================

def merge_results(
    facts: DocumentFacts,
    debtors_result: DebtorsExtraction,
) -> OfficialExtractedFields:
    """
    Объединяет результаты двух проходов.

    Бизнес-логика выбора основного должника
    намеренно не меняется.
    """

    debtors = debtors_result.debtors

    warnings = []

    primary_debtor = None

    if len(debtors) == 1:
        primary_debtor = debtors[0]

    elif len(debtors) > 1:
        warnings.append(
            "Найдено несколько должников. "
            "Основной должник пока не определён "
            "однозначно."
        )

    full_name = None
    birth_date = None
    passport = None
    snils = None
    inn = None

    last_name = None
    first_name = None
    patronymic = None

    if primary_debtor is not None:

        full_name = (
            primary_debtor.full_name
        )

        birth_date = (
            primary_debtor.birth_date
        )

        passport = (
            primary_debtor.passport
        )

        snils = (
            primary_debtor.snils
        )

        inn = (
            primary_debtor.inn
        )

        (
            last_name,
            first_name,
            patronymic,
        ) = split_name(
            full_name
        )

    if primary_debtor is not None:

        street = primary_debtor.street
        house = primary_debtor.house
        apartment = (
            primary_debtor.apartment
        )

    else:

        street = get_common_value(
            debtors,
            "street",
        )

        house = get_common_value(
            debtors,
            "house",
        )

        apartment = get_common_value(
            debtors,
            "apartment",
        )

    defendants_names = (
        build_co_defendants_names(
            debtors
        )
    )

    defendants_count = (
        len(debtors)
        if debtors
        else None
    )

    fields = OfficialExtractedFields(
        document_type=(
            facts.document_type
        ),

        street=street,
        house=house,
        apartment=apartment,

        last_name=last_name,
        first_name=first_name,
        patronymic=patronymic,
        full_name=full_name,

        birth_date=birth_date,

        passport=passport,
        snils=snils,
        inn=inn,

        case_number=(
            facts.case_number
        ),

        case_date=(
            facts.case_date
        ),

        debt_period_start=(
            facts.debt_period_start
        ),

        debt_period_end=(
            facts.debt_period_end
        ),

        principal_debt=(
            facts.principal_debt
        ),

        penalty_amount=(
            facts.penalty_amount
        ),

        state_duty=(
            facts.state_duty
        ),

        co_defendants_count=(
            defendants_count
        ),

        co_defendants_names=(
            defendants_names
        ),

        warnings=warnings,
    )

    return fields


# ============================================================
# Missing fields
# ============================================================

def fill_missing_fields(
    fields: OfficialExtractedFields,
) -> OfficialExtractedFields:
    """
    Заполняет missing_fields.
    """

    ignored_fields = {
        "missing_fields",
        "warnings",
    }

    missing = []

    data = fields.model_dump()

    for field_name, value in data.items():

        if field_name in ignored_fields:
            continue

        if value is None:
            missing.append(
                field_name
            )

        elif (
            isinstance(value, str)
            and not value.strip()
        ):
            missing.append(
                field_name
            )

    fields.missing_fields = missing

    return fields


# ============================================================
# Главная функция
# ============================================================

def extract_fields_with_llm(
    document: ParsedDocument,
) -> OfficialExtractedFields:
    """
    Главная точка входа.

    1. Извлекаем факты.
    2. Извлекаем должников.
    3. Нормализуем результат.
    4. Объединяем результаты.
    """

    if not document.full_text.strip():
        raise ValueError(
            "ParsedDocument не содержит текст."
        )

    facts = extract_document_facts(
        document
    )

    debtors = extract_debtors(
        document
    )

    normalize_llm_results(
        facts,
        debtors,
        document.full_text,
    )

    fields = merge_results(
        facts=facts,
        debtors_result=debtors,
    )

    fields = fill_missing_fields(
        fields
    )

    return fields