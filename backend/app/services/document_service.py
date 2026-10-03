from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_file import DocumentFile
from app.models.document_history import DocumentHistory


WARNING_LABELS = {
    "invalid_inn": "Некорректный ИНН",
    "invalid_state_duty": "Не удалось корректно определить госпошлину",
    "missing_case_number": "Не удалось определить номер дела",
    "missing_document_type": "Не удалось определить тип документа",
    "missing_debtor": "Не удалось определить должника",
    "missing_amount": "Не удалось определить сумму задолженности",
    "multiple_debtors": "Обнаружено несколько должников",
    "ambiguous_debtor": "Не удалось однозначно определить должника",
    "invalid_snils": "Некорректный СНИЛС",
    "invalid_date": "Некорректная дата",
    "invalid_amount": "Некорректная сумма",
}


TECHNICAL_REVIEW_STATUSES = {
    "unclear",
    "invalid",
    "conflict",
    "multiple_values",
    "not_found",
    "warning",
    "needs_review",
}


def get_field_value(
    fields: dict,
    field_name: str,
):
    """
    Возвращает обычное значение поля.

    Поддерживает два формата:

    1. Новый:
    {
        "document_type": "исполнительный лист"
    }

    2. Backend/API формат:
    {
        "document_type": {
            "value": "исполнительный лист",
            "status": "ok",
        }
    }
    """

    value = fields.get(field_name)

    if isinstance(value, dict):
        return value.get("value")

    return value


def format_review_reason(
    warnings: list[str],
    missing_fields: list[str] | None = None,
) -> str | None:
    """
    Формирует причину технической ручной проверки.

    Это НЕ причина передачи документа юристу.
    """

    reasons = []

    for warning in warnings:
        reasons.append(
            WARNING_LABELS.get(
                warning,
                f"Требуется дополнительная проверка: {warning}",
            )
        )

    if missing_fields:
        readable_missing = ", ".join(
            missing_fields
        )

        reasons.append(
            "Не удалось уверенно извлечь поля: "
            f"{readable_missing}"
        )

    if not reasons:
        return None

    return "; ".join(
        dict.fromkeys(reasons)
    )


def find_duplicate(
    db: Session,
    file_hash: str,
) -> DocumentFile | None:

    return db.scalar(
        select(DocumentFile).where(
            DocumentFile.file_hash == file_hash
        )
    )


def create_document(
    db: Session,
    filename: str,
    original_filename: str,
    file_path: str,
    file_format: str,
    file_size: int,
    file_hash: str,
) -> Document:

    document = Document(
        status="new",
        document_type=None,
        needs_review=False,
        requires_legal_action=False,
    )

    db.add(document)
    db.flush()

    document_file = DocumentFile(
        document_id=document.id,
        filename=filename,
        original_filename=original_filename,
        file_path=file_path,
        file_format=file_format,
        file_size=file_size,
        file_hash=file_hash,
    )

    db.add(document_file)

    history = DocumentHistory(
        document_id=document.id,
        event_type="document_created",
        message="Document created",
    )

    db.add(history)

    file_history = DocumentHistory(
        document_id=document.id,
        event_type="file_uploaded",
        message=f"File uploaded: {original_filename}",
    )

    db.add(file_history)

    db.commit()
    db.refresh(document)

    return document


def apply_processing_result(
    db: Session,
    document: Document,
    result: dict,
) -> Document:
    """
    Сохраняет результат document_processing
    в запись документа.

    Разделяем:

    needs_review
        техническая ручная проверка:
        OCR, нераспознанные поля,
        конфликтующие реквизиты и т.п.

    requires_legal_action
        содержание документа требует
        внимания/действий юриста.

    Окончательное юридическое решение
    остаётся за сотрудником.
    """

    # Поддерживаем оба формата:
    #
    # 1. Новый:
    # {
    #     "document_type": ...,
    #     "case_number": ...,
    #     ...
    # }
    #
    # 2. Старый backend/API формат:
    # {
    #     "fields": {
    #         "document_type": {
    #             "value": "...",
    #             "status": "ok"
    #         }
    #     }
    # }

    fields = result.get(
        "fields",
        result,
    )

    # ========================================
    # Основные поля
    # ========================================

    document.document_type = (
        result.get("document_type")
        or get_field_value(
            fields,
            "document_type",
        )
    )

    case_number = (
        result.get("case_number")
        or get_field_value(
            fields,
            "case_number",
        )
    )

    document.case_number = case_number

    document.summary = (
        result.get("summary")
        or ""
    )

    document.debtor = (
        result.get("debtor")
        or get_field_value(
            fields,
            "full_name",
        )
        or get_field_value(
            fields,
            "co_defendants_names",
        )
    )

    amount = (
        result.get("amount")
        or get_field_value(
            fields,
            "principal_debt",
        )
    )

    try:
        document.amount = (
            float(amount)
            if amount is not None
            else None
        )

    except (
        TypeError,
        ValueError,
    ):
        document.amount = None

    # ========================================
    # Техническая ручная проверка
    # ========================================

    processing_status = (
        result.get("extraction_status")
        or result.get("status")
        or get_field_value(
            fields,
            "status",
        )
        or "ok"
    )

    warnings = (
        result.get("warnings")
        or get_field_value(
            fields,
            "warnings",
        )
        or []
    )

    missing_fields = (
        result.get("missing_fields")
        or get_field_value(
            fields,
            "missing_fields",
        )
        or []
    )

    needs_review = (
        processing_status
        in TECHNICAL_REVIEW_STATUSES
    )

    document.needs_review = needs_review

    if processing_status == "error":
        document.status = "error"

    elif needs_review:
        document.status = "needs_review"

    else:
        document.status = "processed"

    document.review_reason = (
        format_review_reason(
            warnings,
            missing_fields,
        )
        if needs_review
        else None
    )

    # ========================================
    # Юридическая маршрутизация
    # ========================================

    requires_legal_action = (
        result.get(
            "requires_legal_action"
        )
    )

    if requires_legal_action is None:
        requires_legal_action = (
            get_field_value(
                fields,
                "requires_legal_action",
            )
        )

    document.requires_legal_action = bool(
        requires_legal_action
    )

    document.legal_action_reason = (
        result.get(
            "legal_action_reason"
        )
        or get_field_value(
            fields,
            "legal_action_reason",
        )
    )

    document.evidence_fragment = (
        result.get(
            "evidence_fragment"
        )
        or get_field_value(
            fields,
            "evidence_fragment",
        )
    )

    # ========================================
    # Полный результат
    # ========================================

    document.extracted_data = result

    # ========================================
    # История обработки
    # ========================================

    history_message = (
        "Document processing completed. "
        f"Status: {document.status}. "
        f"Needs review: {document.needs_review}. "
        f"Requires legal action: "
        f"{document.requires_legal_action}"
    )

    history = DocumentHistory(
        document_id=document.id,
        event_type="document_processed",
        message=history_message,
    )

    db.add(history)

    if document.requires_legal_action:
        legal_history = DocumentHistory(
            document_id=document.id,
            event_type="legal_action_required",
            message=(
                document.legal_action_reason
                or "Document requires legal review"
            ),
        )

        db.add(legal_history)

    db.commit()
    db.refresh(document)

    return document


def attach_file_to_document(
    db: Session,
    document: Document,
    filename: str,
    original_filename: str,
    file_path: str,
    file_format: str,
    file_size: int,
    file_hash: str,
) -> DocumentFile:
    """
    Прикрепляет дополнительный файл
    к уже созданному документу.

    Например:
    XML -> источник данных для обработки
    PDF -> оригинал для просмотра.
    """

    document_file = DocumentFile(
        document_id=document.id,
        filename=filename,
        original_filename=original_filename,
        file_path=file_path,
        file_format=file_format,
        file_size=file_size,
        file_hash=file_hash,
    )

    db.add(document_file)

    history = DocumentHistory(
        document_id=document.id,
        event_type="file_uploaded",
        message=f"File uploaded: {original_filename}",
    )

    db.add(history)

    db.commit()
    db.refresh(document_file)

    return document_file