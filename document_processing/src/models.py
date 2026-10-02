from typing import Optional

from pydantic import BaseModel, Field


class Debtor(BaseModel):
    full_name: str
    birth_date: Optional[str] = None


class ExtractedFields(BaseModel):
    document_type: Optional[str] = None
    case_number: Optional[str] = None
    effective_date: Optional[str] = None

    creditor: Optional[str] = None
    creditor_inn: Optional[str] = None

    debtors: list[Debtor] = Field(
        default_factory=list
    )

    debt_amount: Optional[str] = None
    penalty_amount: Optional[str] = None
    state_duty: Optional[str] = None


class ParsedPage(BaseModel):
    page_number: int
    text: str

    source: str = "unknown"

    ocr_used: bool = False
    ocr_psm: Optional[int] = None

    warnings: list[str] = Field(
        default_factory=list
    )


class ParsedDocument(BaseModel):
    file_name: str
    file_path: str
    file_type: str

    extraction_method: str

    pages: list[ParsedPage] = Field(
        default_factory=list
    )

    full_text: str = ""

    fields: ExtractedFields = Field(
        default_factory=ExtractedFields
    )

    warnings: list[str] = Field(
        default_factory=list
    )

    status: str = "ok"


class OfficialExtractedFields(BaseModel):
    # Тип документа:
    # судебный приказ / исполнительный лист / постановление ФССП
    document_type: Optional[str] = None

    # Данные основного должника
    street: Optional[str] = None
    house: Optional[str] = None
    apartment: Optional[str] = None

    last_name: Optional[str] = None
    first_name: Optional[str] = None
    patronymic: Optional[str] = None
    full_name: Optional[str] = None

    birth_date: Optional[str] = None

    passport: Optional[str] = None
    snils: Optional[str] = None
    inn: Optional[str] = None

    # Дело
    case_number: Optional[str] = None
    case_date: Optional[str] = None

    # Период задолженности
    debt_period_start: Optional[str] = None
    debt_period_end: Optional[str] = None

    # Суммы
    principal_debt: Optional[str] = None
    penalty_amount: Optional[str] = None
    state_duty: Optional[str] = None

    # Соответчики
    co_defendants_count: Optional[int] = None
    co_defendants_names: Optional[str] = None

    # Поля, которые не удалось уверенно извлечь
    missing_fields: list[str] = Field(
        default_factory=list
    )

    # Предупреждения валидаторов
    warnings: list[str] = Field(
        default_factory=list
    )

    # Общий технический статус результата:
    # ok / unclear / error и т.п.
    status: str = "ok"

    # ========================================
    # Юридическая маршрутизация
    # ========================================

    # Требует ли содержание акта действий юриста.
    # Это НЕ то же самое, что техническая ручная проверка.
    requires_legal_action: bool = False

    # Почему документ передаётся юристу.
    legal_action_reason: Optional[str] = None

    # Фрагмент документа,
    # подтверждающий причину передачи.
    evidence_fragment: Optional[str] = None