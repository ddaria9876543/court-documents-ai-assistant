import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from models import OfficialExtractedFields


VALID_STATUSES = {
    "ok",
    "not_found",
    "multiple_values",
    "conflict",
    "invalid",
    "unclear",
}


# Эти поля являются служебными и не должны
# считаться "неизвлечёнными" реквизитами документа.
SERVICE_FIELDS = {
    "warnings",
    "status",
    "missing_fields",
    "requires_legal_action",
    "legal_action_reason",
    "evidence_fragment",
}


def is_valid_inn(value: str | None) -> bool:
    """
    Базовая проверка ИНН.
    """

    if value is None:
        return True

    value = value.strip()

    return (
        value.isdigit()
        and len(value) in {10, 12}
    )


def is_valid_snils(value: str | None) -> bool:
    """
    Базовая проверка СНИЛС.
    """

    if value is None:
        return True

    normalized = re.sub(
        r"\D",
        "",
        value,
    )

    return len(normalized) == 11


def is_valid_case_number(
    value: str | None,
) -> bool:
    """
    Базовая проверка номера дела.
    """

    if value is None:
        return True

    value = value.strip()

    if len(value) < 3:
        return False

    return bool(
        re.search(
            r"\d",
            value,
        )
    )


def is_valid_date(
    value: str | None,
) -> bool:
    """
    Проверяет дату в формате YYYY-MM-DD.
    """

    if value is None:
        return True

    try:
        datetime.strptime(
            value,
            "%Y-%m-%d",
        )

        return True

    except ValueError:
        return False


def is_valid_amount(
    value: str | None,
) -> bool:
    """
    Проверяет денежную сумму.
    """

    if value is None:
        return True

    normalized = (
        value
        .strip()
        .replace(" ", "")
        .replace(",", ".")
    )

    try:
        amount = Decimal(
            normalized
        )

    except InvalidOperation:
        return False

    return amount >= 0


def rebuild_missing_fields(
    fields: OfficialExtractedFields,
) -> None:
    """
    Пересобирает missing_fields.

    Учитываются только реальные поля документа.

    Служебные поля:
    - status
    - warnings
    - requires_legal_action
    - legal_action_reason
    - evidence_fragment

    не должны попадать в missing_fields.
    """

    data = fields.model_dump()

    missing_fields = []

    for field_name, value in data.items():

        if field_name in SERVICE_FIELDS:
            continue

        if value is None:
            missing_fields.append(
                field_name
            )

        elif (
            isinstance(value, str)
            and not value.strip()
        ):
            missing_fields.append(
                field_name
            )

    fields.missing_fields = missing_fields


def determine_status(
    fields: OfficialExtractedFields,
) -> str:
    """
    Определяет общий технический статус результата.

    Важно:
    requires_legal_action не влияет
    на технический status.

    Приоритет:
    invalid
    -> conflict
    -> multiple_values
    -> unclear
    -> not_found
    -> ok
    """

    warnings_text = " ".join(
        fields.warnings
    ).lower()

    # --------------------------------
    # 1. Некорректные значения
    # --------------------------------

    if any(
        warning.startswith("invalid_")
        for warning in fields.warnings
    ):
        return "invalid"

    # --------------------------------
    # 2. Конфликт значений
    # --------------------------------

    if "conflict" in warnings_text:
        return "conflict"

    # --------------------------------
    # 3. Несколько возможных значений
    # --------------------------------

    if "multiple_values" in warnings_text:
        return "multiple_values"

    # --------------------------------
    # 4. Неоднозначный результат
    # --------------------------------

    if (
        "неоднозначно" in warnings_text
        or "не определён" in warnings_text
        or "не определен" in warnings_text
        or "unclear" in warnings_text
    ):
        return "unclear"

    # --------------------------------
    # 5. Основные поля не найдены
    # --------------------------------

    critical_values = [
        fields.document_type,
        fields.case_number,
        fields.full_name,
        fields.principal_debt,
    ]

    if all(
        value is None
        for value in critical_values
    ):
        return "not_found"

    # --------------------------------
    # 6. Всё нормально
    # --------------------------------

    return "ok"


def validate_official_fields(
    fields: OfficialExtractedFields,
) -> OfficialExtractedFields:
    """
    Проверяет критичные поля,
    добавляет warnings,
    пересобирает missing_fields
    и выставляет общий технический status.
    """

    warnings = list(
        fields.warnings
    )

    # --------------------------------
    # ИНН
    # --------------------------------

    if not is_valid_inn(
        fields.inn
    ):
        warnings.append(
            "invalid_inn"
        )

    # --------------------------------
    # СНИЛС
    # --------------------------------

    if not is_valid_snils(
        fields.snils
    ):
        warnings.append(
            "invalid_snils"
        )

    # --------------------------------
    # Номер дела
    # --------------------------------

    if not is_valid_case_number(
        fields.case_number
    ):
        warnings.append(
            "invalid_case_number"
        )

    # --------------------------------
    # Даты
    # --------------------------------

    date_fields = {
        "birth_date": (
            fields.birth_date
        ),
        "case_date": (
            fields.case_date
        ),
        "debt_period_start": (
            fields.debt_period_start
        ),
        "debt_period_end": (
            fields.debt_period_end
        ),
    }

    for field_name, value in date_fields.items():

        if not is_valid_date(
            value
        ):
            warnings.append(
                f"invalid_{field_name}"
            )

    # --------------------------------
    # Суммы
    # --------------------------------

    amount_fields = {
        "principal_debt": (
            fields.principal_debt
        ),
        "penalty_amount": (
            fields.penalty_amount
        ),
        "state_duty": (
            fields.state_duty
        ),
    }

    for field_name, value in amount_fields.items():

        if not is_valid_amount(
            value
        ):
            warnings.append(
                f"invalid_{field_name}"
            )

    # --------------------------------
    # Убираем дубли warnings
    # --------------------------------

    fields.warnings = list(
        dict.fromkeys(
            warnings
        )
    )

    # --------------------------------
    # Пересобираем missing_fields
    # --------------------------------

    rebuild_missing_fields(
        fields
    )

    # --------------------------------
    # Определяем технический статус
    # --------------------------------

    fields.status = determine_status(
        fields
    )

    return fields