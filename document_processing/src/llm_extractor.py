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
    Список всех найденных должников
    и индекс основного должника.
    """

    debtors: list[DebtorCandidate] = Field(
        default_factory=list
    )

    # Индекс основного должника в debtors.
    # Например:
    # 0 — первый,
    # 1 — второй.
    #
    # Если определить основного должника
    # по тексту нельзя — null.
    primary_debtor_index: Optional[int] = None


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
            "seed": 42,
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
def extract_case_date_rule_based(
    text: str,
    case_number: str | None,
) -> str | None:
    """
    Ищет дату судебного акта,
    связанную с номером дела.

    Не использует даты вступления в силу,
    выдачи исполнительного листа и т.п.
    """

    if not text:
        return None

    # ---------------------------------------------------------
    # 1. "по делу № 2-123/2020 от 09.12.2020"
    # ---------------------------------------------------------

    if case_number:
        escaped_case = re.escape(
            case_number
        )

        pattern = (
            rf"(?:дел[оуеа]|дела|материал[а-я]*)"
            rf".{{0,80}}?"
            rf"№?\s*{escaped_case}"
            rf".{{0,50}}?"
            rf"(?:от\s*)?"
            rf"(\d{{1,2}}[./]\d{{1,2}}[./]\d{{4}})"
        )

        match = re.search(
            pattern,
            text,
            re.IGNORECASE | re.DOTALL,
        )

        if match:
            return normalize_date(
                match.group(1)
            )

    # ---------------------------------------------------------
    # 2. Частый формат исполнительного листа:
    #
    # 2-85418/2020
    # Дело № 09.12.2020
    # ---------------------------------------------------------

    pattern = (
        r"(?:дело|дела)"
        r"\s*№?\s*"
        r"(\d{1,2}[./]\d{1,2}[./]\d{4})"
    )

    match = re.search(
        pattern,
        text,
        re.IGNORECASE,
    )

    if match:
        return normalize_date(
            match.group(1)
        )

    # ---------------------------------------------------------
    # 3. Если номер дела найден,
    # смотрим небольшой фрагмент рядом с ним.
    # ---------------------------------------------------------

    if case_number:
        position = text.find(
            case_number
        )

        if position != -1:
            fragment = text[
                max(0, position - 150):
                position + 250
            ]

            dates = re.findall(
                r"\b"
                r"\d{1,2}[./]\d{1,2}[./]\d{4}"
                r"\b",
                fragment,
            )

            if dates:
                return normalize_date(
                    dates[0]
                )

    return None
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

- case_date: дата исходного судебного акта,
  относящаяся к case_number;

- debt_period_start;
- debt_period_end;
- principal_debt;
- penalty_amount;
- state_duty.

Правила для case_date:

Для "судебного приказа":
- бери дату самого судебного приказа;
- НЕ бери дату вступления в силу;
- НЕ бери дату выдачи копии;
- НЕ бери более поздние технические даты.

Для "исполнительного листа":
- бери дату судебного решения или судебного акта,
  на основании которого выдан исполнительный лист;
- НЕ бери дату выдачи исполнительного листа;
- НЕ бери дату изготовления исполнительного листа;
- НЕ бери дату вступления решения в законную силу;
- НЕ бери дату возбуждения исполнительного производства.

Если в тексте рядом с case_number указана дата,
предпочитай именно её.

Если в документе есть несколько дат,
выбирай дату исходного судебного акта,
а не более позднюю процессуальную дату.

Если дату исходного судебного акта
нельзя определить однозначно,
верни null.

Правила для задолженности:

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
- дату судебного акта с датой выдачи исполнительного листа;
- дату судебного акта с датой вступления решения в законную силу;
- дату судебного акта с датой возбуждения исполнительного производства;
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

    rule_case_date = (
        extract_case_date_rule_based(
            context,
            result.case_number,
        )
    )

    if rule_case_date:
        result.case_date = rule_case_date

    return result

# ============================================================
# Проход №2 — должники
# ============================================================

def extract_debtors(
    document: ParsedDocument,
) -> DebtorsExtraction:
    """
    Извлекает должников из ограниченного контекста документа.

    Для длинных документов используем начало и конец,
    чтобы не перегружать Qwen.

    Дополнительно модель определяет индекс
    основного должника.
    """

    full_text = document.full_text or ""

    # ========================================================
    # Ограничиваем контекст
    # ========================================================

    max_context_chars = 6000

    if len(full_text) <= max_context_chars:
        debtor_context = full_text

    else:
        head_size = 4000
        tail_size = 2000

        debtor_context = (
            full_text[:head_size]
            + "\n\n...[середина документа пропущена]...\n\n"
            + full_text[-tail_size:]
        )

    print(
        f"  Debtors context: "
        f"{len(full_text)} -> "
        f"{len(debtor_context)} символов"
    )

    # ========================================================
    # Prompt
    # ========================================================

    def build_prompt(
        context: str,
    ) -> str:
        return f"""
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

Дополнительно определи:
- primary_debtor_index — индекс ОСНОВНОГО должника
  в массиве debtors, начиная с 0.

Основной должник — лицо, к которому в документе
относятся основные персональные реквизиты и которое
является основным субъектом взыскания.

Если в документе несколько должников или соответчиков,
не считай автоматически первого найденного человека
основным должником.

Определи основного должника по смыслу документа:
- по явному указанию "должник";
- по основной карточке или блоку реквизитов;
- по ФИО, к которому относятся адрес, дата рождения,
  паспорт, ИНН, СНИЛС или другие основные реквизиты;
- по структуре исполнительного листа или судебного акта.

Если надёжно определить основного должника нельзя,
верни primary_debtor_index = null.

Правила:
- включай только лиц, прямо указанных как должники;
- каждого должника возвращай отдельным объектом;
- не включай взыскателя;
- не включай организацию-взыскателя;
- не включай судью;
- не включай судебного пристава;
- не включай представителя;
- не объединяй нескольких должников в одного;
- ИНН организации-взыскателя не является ИНН должника;
- ИНН, СНИЛС, паспорт, дату рождения и адрес
  связывай только с конкретным должником;
- если принадлежность реквизита конкретному должнику
  неоднозначна, верни null;
- если значение отсутствует, верни null;
- ничего не придумывай;
- не создавай должников только из-за упоминания
  посторонних лиц в описательной части.

Текст:

{context}
"""

    # ========================================================
    # Первая попытка
    # ========================================================

    prompt = build_prompt(
        debtor_context
    )

    try:
        result = call_ollama_json(
            prompt=prompt,
            response_model=DebtorsExtraction,
            pass_name="debtors",
            num_predict=700,
        )

        return result

    except ValueError:

        print(
            "  Qwen [debtors]: некорректный JSON, "
            "повторная попытка..."
        )

    # ========================================================
    # Fallback — уменьшаем контекст
    # ========================================================

    retry_context_chars = 3500

    if len(full_text) <= retry_context_chars:
        retry_context = full_text

    else:
        retry_context = (
            full_text[:2500]
            + "\n\n...[часть документа пропущена]...\n\n"
            + full_text[-1000:]
        )

    print(
        f"  Debtors retry context: "
        f"{len(full_text)} -> "
        f"{len(retry_context)} символов"
    )

    retry_prompt = build_prompt(
        retry_context
    )

    try:
        return call_ollama_json(
            prompt=retry_prompt,
            response_model=DebtorsExtraction,
            pass_name="debtors-retry",
            num_predict=600,
        )

    except ValueError:

        print(
            "  Qwen [debtors]: не удалось получить "
            "корректный JSON. Продолжаем без должников."
        )

        return DebtorsExtraction(
            debtors=[],
            primary_debtor_index=None,
        )
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
def extract_case_date_from_text(
    text: str,
    case_number: Optional[str],
) -> Optional[str]:
    """
    Ищет дату, привязанную именно к номеру дела.

    Пример:
    по делу №2-8179/2032 от 03.12.2032
    """

    if not text or not case_number:
        return None

    escaped_case = re.escape(
        case_number.strip()
    )

    pattern = (
        rf"(?:по\s+делу|дел[ау])"
        rf".{{0,120}}?"
        rf"№?\s*{escaped_case}"
        rf"\s+от\s+"
        rf"(\d{{2}}\.\d{{2}}\.\d{{4}})"
    )

    match = re.search(
        pattern,
        text,
        flags=(
            re.IGNORECASE
            | re.DOTALL
        ),
    )

    if not match:
        return None

    return normalize_date(
        match.group(1)
    )


def extract_debt_period_from_text(
    text: str,
) -> tuple[
    Optional[str],
    Optional[str],
]:
    """
    Ищет период именно задолженности.

    Пример:
    задолженность ... за период
    с 03.07.2028 по 18.05.2029
    """

    if not text:
        return None, None

    patterns = [
        (
            r"задолженн\w*"
            r".{0,500}?"
            r"за\s+период\s+с\s+"
            r"(\d{2}\.\d{2}\.\d{4})"
            r"\s+по\s+"
            r"(\d{2}\.\d{2}\.\d{4})"
        ),
        (
            r"за\s+период\s+с\s+"
            r"(\d{2}\.\d{2}\.\d{4})"
            r"\s+по\s+"
            r"(\d{2}\.\d{2}\.\d{4})"
        ),
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            flags=(
                re.IGNORECASE
                | re.DOTALL
            ),
        )

        if match:

            return (
                normalize_date(
                    match.group(1)
                ),
                normalize_date(
                    match.group(2)
                ),
            )

    return None, None


def normalize_name_for_match(
    value: Optional[str],
) -> Optional[str]:

    if not value:
        return None

    return re.sub(
        r"[^а-яёa-z]",
        "",
        value.lower(),
        flags=re.IGNORECASE,
    )


def find_primary_debtor_index(
    text: str,
    debtors: list[DebtorCandidate],
) -> Optional[int]:
    """
    Ищет должника из явного блока:

    "Должником по исполнительному документу
    является: физическое лицо ..."
    """

    if not text or not debtors:
        return None

    pattern = (
        r"должником\s+по\s+исполнительному\s+"
        r"документу\s+является"
        r".{0,200}?"
        r"физическое\s+лицо\s+"
        r"([а-яё-]+\s+[а-яё-]+\s+[а-яё-]+)"
    )

    match = re.search(
        pattern,
        text,
        flags=(
            re.IGNORECASE
            | re.DOTALL
        ),
    )

    if not match:
        return None

    target_name = normalize_name_for_match(
        match.group(1)
    )

    if not target_name:
        return None

    for index, debtor in enumerate(
        debtors
    ):

        debtor_name = normalize_name_for_match(
            debtor.full_name
        )

        if debtor_name == target_name:
            return index

    return None

def normalize_llm_results(
    facts: DocumentFacts,
    debtors_result: DebtorsExtraction,
    document_text: str,
) -> None:
    """
    Нормализация и детерминированная
    постобработка результатов LLM.
    """

    # ========================================
    # Номер дела
    # ========================================

    facts.case_number = normalize_case_number(
        facts.case_number,
        document_text,
    )

    # ========================================
    # Дата судебного дела
    # ========================================

    facts.case_date = normalize_date(
        facts.case_date
    )

    deterministic_case_date = (
        extract_case_date_from_text(
            document_text,
            facts.case_number,
        )
    )

    if deterministic_case_date:
        facts.case_date = (
            deterministic_case_date
        )

    # ========================================
    # Период задолженности
    # ========================================

    facts.debt_period_start = normalize_date(
        facts.debt_period_start
    )

    facts.debt_period_end = normalize_date(
        facts.debt_period_end
    )

    (
        deterministic_period_start,
        deterministic_period_end,
    ) = extract_debt_period_from_text(
        document_text
    )

    if deterministic_period_start:
        facts.debt_period_start = (
            deterministic_period_start
        )

    if deterministic_period_end:
        facts.debt_period_end = (
            deterministic_period_end
        )

    # ========================================
    # Должники
    # ========================================

    for debtor in debtors_result.debtors:

        debtor.birth_date = normalize_date(
            debtor.birth_date
        )

    # Если Qwen сама не определила основного
    # должника — пробуем взять его из
    # явного блока исполнительного листа.
    if (
        debtors_result.primary_debtor_index
        is None
    ):

        primary_index = (
            find_primary_debtor_index(
                document_text,
                debtors_result.debtors,
            )
        )

        if primary_index is not None:

            debtors_result.primary_debtor_index = (
                primary_index
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

    Основного должника выбираем по
    primary_debtor_index от Qwen.

    Если модель не смогла определить его,
    используем первого найденного должника
    как fallback.
    """

    debtors = debtors_result.debtors

    warnings = []

    primary_debtor = None

    # ========================================
    # Выбор основного должника
    # ========================================

    primary_index = (
        debtors_result.primary_debtor_index
    )

    if (
        primary_index is not None
        and 0 <= primary_index < len(debtors)
    ):
        primary_debtor = (
            debtors[primary_index]
        )

    elif debtors:

        primary_debtor = debtors[0]

        if len(debtors) > 1:
            warnings.append(
                "Найдено несколько должников, "
                "но основной не определён однозначно. "
                "Использован первый найденный должник."
            )

    # ========================================
    # Персональные данные
    # ========================================

    full_name = None
    birth_date = None

    passport = None
    snils = None
    inn = None

    street = None
    house = None
    apartment = None

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

        street = (
            primary_debtor.street
        )

        house = (
            primary_debtor.house
        )

        apartment = (
            primary_debtor.apartment
        )

        (
            last_name,
            first_name,
            patronymic,
        ) = split_name(
            full_name
        )

    # ========================================
    # Все должники
    # ========================================

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

    # ========================================
    # Итог
    # ========================================

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