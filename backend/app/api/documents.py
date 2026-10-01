from pathlib import Path
import sys

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models.document import Document
from app.models.document_history import DocumentHistory
from app.schemas.document import (
    DocumentDetailResponse,
    DocumentListResponse,
    DuplicateResponse,
    StatusUpdate,
    UploadErrorResponse,
    UploadedDocumentResponse,
    UploadResponse,
)
from app.services.document_service import (
    apply_processing_result,
    create_document,
    find_duplicate,
)
from app.services.file_service import (
    calculate_sha256,
    generate_storage_filename,
    read_file,
    save_file,
    validate_file_extension,
)


DOCUMENT_PROCESSING_SRC = (
    Path(__file__).resolve().parents[3]
    / "document_processing"
    / "src"
)

if str(DOCUMENT_PROCESSING_SRC) not in sys.path:
    sys.path.append(
        str(DOCUMENT_PROCESSING_SRC)
    )

from api_adapter import build_api_result


router = APIRouter(
    prefix="/documents",
    tags=["Documents"]
)


def document_to_response(document: Document) -> dict:
    file = document.files[0] if document.files else None

    return {
        "id": document.id,
        "filename": file.original_filename if file else "",
        "documentType": document.document_type,
        "caseNumber": document.case_number,
        "enforcementNumber": None,
        "status": document.status,
        "createdAt": document.created_at,
        "summary": document.summary or "",
        "needsReview": document.needs_review,
        "reviewReason": document.review_reason,
        "files": document.files,
        "debtor": document.debtor,
        "amount": document.amount,
        "fileFormat": file.file_format if file else "pdf",
    }


@router.post(
    "/upload",
    response_model=UploadResponse
)
async def upload_documents(
    file: UploadFile = File(
        ...,
        description="PDF/XML документ"
    ),
    db: Session = Depends(get_db)
):
    uploaded = []
    duplicates = []
    errors = []

    files = [file]

    for file in files:
        saved_path = None

        try:
            extension = validate_file_extension(
                file.filename or ""
            )

            content = await read_file(file)

            file_hash = calculate_sha256(content)

            duplicate = find_duplicate(
                db,
                file_hash
            )

            if duplicate:
                duplicates.append(
                    DuplicateResponse(
                        status="duplicate",
                        filename=file.filename or "",
                        existing_document_id=duplicate.document_id
                    )
                )
                continue

            storage_filename = generate_storage_filename(
                extension
            )

            saved_path = save_file(
                content,
                storage_filename
            )

            document = create_document(
                db=db,
                filename=storage_filename,
                original_filename=file.filename or "",
                file_path=str(saved_path),
                file_format=extension.lstrip("."),
                file_size=len(content),
                file_hash=file_hash
            )

            document.status = "processing"
            db.commit()
            db.refresh(document)

            processing_result = build_api_result(
                saved_path
            )

            document = apply_processing_result(
                db=db,
                document=document,
                result=processing_result,
            )

            uploaded.append(
                UploadedDocumentResponse(
                    document_id=document.id,
                    filename=file.filename or "",
                    status=document.status
                )
            )

        except ValueError as exc:
            errors.append(
                UploadErrorResponse(
                    filename=file.filename or "",
                    error=str(exc)
                )
            )

        except OSError:
            if saved_path and Path(saved_path).exists():
                Path(saved_path).unlink()

            errors.append(
                UploadErrorResponse(
                    filename=file.filename or "",
                    error="File write error"
                )
            )

        except Exception as exc:

            if saved_path and Path(saved_path).exists():
                Path(saved_path).unlink()

            db.rollback()

            errors.append(
                UploadErrorResponse(
                    filename=file.filename or "",
                    error="Database or internal error"
                )
            )
        
    return UploadResponse(
        uploaded=uploaded,
        duplicates=duplicates,
        errors=errors
    )


@router.get(
    "",
    response_model=list[DocumentListResponse]
)
def get_documents(
    db: Session = Depends(get_db)
):
    documents = db.scalars(
        select(Document)
        .options(
            selectinload(Document.files)
        )
        .order_by(Document.created_at.desc())
    ).all()

    return [
        document_to_response(document)
        for document in documents
    ]


@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse
)
def get_document(
    document_id: int,
    db: Session = Depends(get_db)
):
    document = db.scalar(
        select(Document)
        .options(
            selectinload(Document.files),
            selectinload(Document.history)
        )
        .where(Document.id == document_id)
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    response = document_to_response(document)
    response["history"] = document.history

    return response


@router.put(
    "/{document_id}/status",
    response_model=DocumentDetailResponse
)
def update_document_status(
    document_id: int,
    status_data: StatusUpdate,
    db: Session = Depends(get_db)
):
    document = db.scalar(
        select(Document)
        .options(
            selectinload(Document.files),
            selectinload(Document.history)
        )
        .where(Document.id == document_id)
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    old_status = document.status
    document.status = status_data.status

    history = DocumentHistory(
        document_id=document.id,
        event_type="status_changed",
        message=(
            f"Status changed from "
            f"{old_status} to {document.status}"
        )
    )

    db.add(history)
    db.commit()
    db.refresh(document)

    response = document_to_response(document)
    response["history"] = document.history

    return response