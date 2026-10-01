from typing import Optional, Type

import requests
from pydantic import BaseModel, Field

from models import (
    OfficialExtractedFields,
    ParsedDocument,
)


MODEL_NAME = "qwen3:8b"

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
    Список всех должников,
    обнаруженных в документе.
    """

    debtors: list[DebtorCandidate] = Field(
        default_factory=list
    )


# ============================================================
# Вызов Ollama
# ============================================================

def call_ollama_json(
    prompt: str,
    response_model: Type[BaseModel],
) -> BaseModel:
    """
    Отправляет небольшую задачу в Qwen
    и требует ответ по конкретной JSON-схеме.
    """

    schema = response_model.model_json_schema()

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "format": schema,
        "keep_alive": 0,
        "options": {
            "temperature": 0,
        },
    }

    try:
        response = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=300,
        )

    except requests.RequestException as exc:
        raise RuntimeError(
            "Не удалось подключиться к Ollama. "
            "Проверь, что Ollama запущена."
        ) from exc

    if response.status_code != 200:
        raise RuntimeError(
            "Ollama вернула ошибку.\n"
            f"HTTP: {response.status_code}\n"
            f"Ответ: {response.text}"
        )

    try:
        ollama_data = response.json()

    except ValueError as exc:
        raise RuntimeError(
            "Ollama вернула некорректный JSON."
        ) from exc

    content = ollama_data.get(
        "response",
        ""
    )

    if not content.strip():
        raise ValueError(
            "Qwen вернула пустой ответ."
        )

    try:
        return response_model.model_validate_json(
            content
        )

    except Exception as exc:
        raise ValueError(
            "Не удалось преобразовать "
            "ответ Qwen в требуемую модель.\n\n"
            f"Ответ Qwen:\n{content}"
        ) from exc


# ============================================================
# Проход №1
# Факты документа
# ============================================================

def extract_document_facts(
    document: ParsedDocument,
) -> DocumentFacts:
    """
    Извлекает только факты,
    относящиеся к документу в целом.
    """

    prompt = f"""
Ты извлекаешь данные из российского судебного документа.

Используй ТОЛЬКО предоставленный текст.
Не придумывай значения.

Твоя задача сейчас — извлечь ТОЛЬКО следующие поля:

1. document_type
2. case_number
3. case_date
4. debt_period_start
5. debt_period_end
6. principal_debt
7. penalty_amount
8. state_duty

НЕ анализируй персональные данные должников.
НЕ пытайся определить основного должника.

Правила:

document_type:
используй только одно из значений:
- судебный приказ
- исполнительный лист
- постановление ФССП

case_number:
номер судебного дела.

Например:
2-80743/2023

case_date:
дата судебного акта или дата дела,
которая относится к номеру дела.

Все даты возвращай в формате:
YYYY-MM-DD

Например:
23.03.2023 -> 2023-03-23

Если в тексте написано:
"за период с 03.12.2021 по 02.01.2023"

верни:
debt_period_start = 2021-12-03
debt_period_end = 2023-01-02

principal_debt:
сумма основного долга.

Например:
"задолженность ... в размере 41828.90 руб."
-> 41828.90

penalty_amount:
сумма пеней.

Например:
"пени в размере 40593.68 руб."
-> 40593.68

state_duty:
государственная пошлина.

Например:
"государственной пошлины по 266.66 руб."
-> 266.66

Для денежных значений возвращай
только число строкой.
Не добавляй "руб.".

Если значение прямо присутствует в тексте,
извлеки его.

Используй null только тогда,
когда соответствующей информации
действительно нет в тексте.

--- НАЧАЛО ДОКУМЕНТА ---

{document.full_text}

--- КОНЕЦ ДОКУМЕНТА ---
"""

    result = call_ollama_json(
        prompt=prompt,
        response_model=DocumentFacts,
    )

    return result


# ============================================================
# Проход №2
# Все должники
# ============================================================

def extract_debtors(
    document: ParsedDocument,
) -> DebtorsExtraction:
    """
    Отдельно извлекает ВСЕХ должников.
    """

    prompt = f"""
Ты извлекаешь должников
из российского судебного документа.

Используй ТОЛЬКО предоставленный текст.
Ничего не придумывай.

Найди ВСЕХ должников / ответчиков /
соответчиков, с которых взыскивается
задолженность.

Не включай:
- взыскателя;
- судью;
- представителя суда;
- судебного пристава;
- другие организации и лица,
  которые не являются должниками.

Для КАЖДОГО должника извлеки:

- full_name
- birth_date
- street
- house
- apartment
- passport
- snils
- inn

ФИО возвращай в именительном падеже,
если форма очевидна из текста.

Например:

"с Архивниковой Маргариты Павловны"

нужно вернуть:

"Архивникова Маргарита Павловна"

Даты возвращай в формате:

YYYY-MM-DD

Например:

06.01.1999 -> 1999-01-06

Адрес вида:

ул. Макетная, 5-139

разбирай так:

street = "Макетная ул."
house = "5"
apartment = "139"

Если паспорт, СНИЛС или ИНН
для конкретного должника отсутствуют,
верни null.

ВАЖНО:
ИНН взыскателя или организации
НЕ является ИНН должника.

Если должников несколько,
обязательно верни ВСЕХ
отдельными объектами списка debtors.

Не отказывайся от извлечения только потому,
что должников несколько.

--- НАЧАЛО ДОКУМЕНТА ---

{document.full_text}

--- КОНЕЦ ДОКУМЕНТА ---
"""

    result = call_ollama_json(
        prompt=prompt,
        response_model=DebtorsExtraction,
    )

    return result


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
    Если одно и то же значение указано
    у всех должников, его можно безопасно
    использовать как общее.

    Например, у ocr_012.pdf
    все три должника имеют один адрес.
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
    Формирует строку со всеми найденными
    должниками.
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
    Объединяет результаты двух проходов
    в официальный формат.
    """

    debtors = debtors_result.debtors

    warnings = []

    # ----------------------------------------
    # Основной должник
    # ----------------------------------------

    primary_debtor = None

    if len(debtors) == 1:
        primary_debtor = debtors[0]

    elif len(debtors) > 1:
        warnings.append(
            "Найдено несколько должников. "
            "Основной должник пока не определён "
            "однозначно."
        )

    # ----------------------------------------
    # Персональные поля
    # ----------------------------------------

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

    # ----------------------------------------
    # Адрес
    # ----------------------------------------
    #
    # Если должник один — берём его адрес.
    #
    # Если их несколько, но адрес у всех
    # одинаковый — его можно безопасно
    # сохранить.
    # ----------------------------------------

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

    # ----------------------------------------
    # Все должники
    # ----------------------------------------

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

    1. Извлекаем факты документа.
    2. Отдельно извлекаем всех должников.
    3. Объединяем результаты.
    """

    if not document.full_text.strip():
        raise ValueError(
            "ParsedDocument не содержит текста."
        )

    print(
        "  Qwen: извлечение фактов документа..."
    )

    facts = extract_document_facts(
        document
    )

    print(
        "  Qwen: извлечение должников..."
    )

    debtors = extract_debtors(
        document
    )

    fields = merge_results(
        facts=facts,
        debtors_result=debtors,
    )

    fields = fill_missing_fields(
        fields
    )

    return fields