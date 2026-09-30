from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_file import DocumentFile
from app.models.document_history import DocumentHistory


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