from typing import Optional, Type

import requests
from pydantic import BaseModel, Field

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
    Отправляет задачу в локальную Qwen через Ollama
    и требует ответ по заданной JSON-схеме.
    """

    schema = response_model.model_json_schema()

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "format": schema,
        "think": False,
        "keep_alive": "10m",
        "options": {
            "temperature": 0,
            "num_ctx": 2048,
            "num_predict": 250,
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
        "",
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
    Извлекает факты,
    относящиеся к документу в целом.
    """

    prompt = f"""
Извлеки данные из российского судебного документа.

Используй только информацию из текста.
Не придумывай значения.
Если значения нет — верни null.

Нужно извлечь:

- document_type
- case_number
- case_date
- debt_period_start
- debt_period_end
- principal_debt
- penalty_amount
- state_duty

Правила:

document_type — только одно значение:
- судебный приказ
- исполнительный лист
- постановление ФССП

case_number — номер судебного дела.

case_date — дата судебного акта или дата дела,
относящаяся к номеру дела.

Все даты приводи к формату YYYY-MM-DD.

debt_period_start — начало периода задолженности.
debt_period_end — конец периода задолженности.

principal_debt — сумма основного долга.
penalty_amount — сумма пеней.
state_duty — государственная пошлина.

Денежные значения возвращай только числом строкой.
Не добавляй "руб." и другие обозначения валюты.

Не извлекай персональные данные должников.
Не пытайся определить основного должника.

ТЕКСТ ДОКУМЕНТА:

{document.full_text}
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
    Отдельно извлекает всех должников.
    """

    prompt = f"""
Найди всех должников, ответчиков или соответчиков
в российском судебном документе.

Используй только информацию из текста.
Не придумывай значения.

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

Не включай:
- взыскателя;
- судью;
- представителя суда;
- судебного пристава;
- организации и других лиц,
  которые не являются должниками.

Если должников несколько —
верни каждого отдельным объектом списка debtors.

full_name возвращай в именительном падеже,
если это можно однозначно определить из текста.

Все даты приводи к формату YYYY-MM-DD.

Адрес разделяй на:
- street
- house
- apartment

ИНН взыскателя или организации
не записывай как ИНН должника.

Если паспорт, СНИЛС, ИНН или другое поле
для конкретного должника отсутствует —
верни null.

ТЕКСТ ДОКУМЕНТА:

{document.full_text}
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