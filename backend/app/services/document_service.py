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


def format_review_reason(warnings: list[str]) -> str | None:
    if not warnings:
        return None

    readable_warnings = []

    for warning in warnings:
        readable_warnings.append(
            WARNING_LABELS.get(
                warning,
                f"Требуется дополнительная проверка: {warning}"
            )
        )

    return "; ".join(readable_warnings)


def find_duplicate(
    db: Session,
    file_hash: str
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
    file_hash: str
) -> Document:

    document = Document(
        status="new",
        document_type=None
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
        file_hash=file_hash
    )

    db.add(document_file)

    history = DocumentHistory(
        document_id=document.id,
        event_type="document_created",
        message="Document created"
    )

    db.add(history)

    file_history = DocumentHistory(
        document_id=document.id,
        event_type="file_uploaded",
        message=f"File uploaded: {original_filename}"
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
    """

    fields = result.get(
        "fields",
        {},
    )

    case_number_field = fields.get(
        "case_number",
        {},
    )

    document.document_type = result.get(
        "document_type"
    )

    document.case_number = case_number_field.get(
        "value"
    )

    document.summary = result.get(
        "summary"
    )

    document.debtor = result.get(
        "debtor"
    )

    document.amount = result.get(
        "amount"
    )

    document.status = result.get(
        "status",
        "needs_review",
    )

    document.needs_review = (
        document.status == "needs_review"
    )

    warnings = result.get(
        "warnings",
        [],
    )

    document.review_reason = format_review_reason(
        warnings
    )

    document.extracted_data = result

    history = DocumentHistory(
        document_id=document.id,
        event_type="document_processed",
        message=(
            f"Document processing completed. "
            f"Status: {document.status}"
        ),
    )

    db.add(history)
    db.commit()
    db.refresh(document)

    return document