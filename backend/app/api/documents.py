from pathlib import Path
import os
import smtplib
import sys
from app.core.config import settings
from fastapi import APIRouter, Depends, File, UploadFile
from fastapi import HTTPException
from fastapi.responses import FileResponse

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db

from app.models.document import Document
from app.models.document_file import DocumentFile
from app.models.document_history import DocumentHistory

from app.schemas.document import (
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentUpdate,
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

from app.services.email_service import (
    send_document_email,
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
    tags=["Documents"],
)


def get_display_file(
    document: Document,
) -> DocumentFile | None:
    """
    Возвращает файл для показа пользователю.

    Приоритет:
    1. PDF — оригинал документа.
    2. Если PDF нет — любой доступный файл.
    """

    if not document.files:
        return None

    pdf_file = next(
        (
            item
            for item in document.files
            if item.file_format.lower() == "pdf"
        ),
        None,
    )

    if pdf_file:
        return pdf_file

    return document.files[0]


def document_to_response(
    document: Document,
) -> dict:

    display_file = get_display_file(
        document
    )

    extracted_data = (
        document.extracted_data or {}
    )

    return {
        "id": document.id,

        "filename": (
            display_file.original_filename
            if display_file
            else ""
        ),

        "documentType":
            document.document_type,

        "caseNumber":
            document.case_number,

        "enforcementNumber":
            extracted_data.get(
                "enforcementNumber"
            ),

        "status":
            document.status,

        "createdAt":
            document.created_at,

        "summary":
            document.summary or "",

        # Техническая проверка
        "needsReview":
            document.needs_review,

        "reviewReason":
            document.review_reason,

        # Юридическая маршрутизация
        "requiresLegalAction":
            document.requires_legal_action,

        "legalActionReason":
            document.legal_action_reason,

        "evidenceFragment":
            document.evidence_fragment,

        "dataVerified": bool(
            extracted_data.get(
                "dataVerified",
                False,
            )
        ),

        "files":
            document.files,

        "debtor":
            document.debtor,

        "amount":
            document.amount,

        "fileFormat": (
            display_file.file_format
            if display_file
            else "pdf"
        ),
    }


# ============================================================
# ОБЫЧНАЯ ЗАГРУЗКА ОДНОГО ФАЙЛА
# PDF или XML
# ============================================================

@router.post(
    "/upload",
    response_model=UploadResponse,
)
async def upload_documents(
    file: UploadFile = File(
        ...,
        description="PDF/XML документ",
    ),
    db: Session = Depends(get_db),
):
    uploaded = []
    duplicates = []
    errors = []

    saved_path = None

    try:
        extension = (
            validate_file_extension(
                file.filename or ""
            )
        )

        content = await read_file(
            file
        )

        file_hash = calculate_sha256(
            content
        )

        duplicate = find_duplicate(
            db,
            file_hash,
        )

        if duplicate:
            duplicates.append(
                DuplicateResponse(
                    status="duplicate",
                    filename=(
                        file.filename or ""
                    ),
                    existing_document_id=(
                        duplicate.document_id
                    ),
                )
            )

            return UploadResponse(
                uploaded=uploaded,
                duplicates=duplicates,
                errors=errors,
            )

        storage_filename = (
            generate_storage_filename(
                extension
            )
        )

        saved_path = save_file(
            content,
            storage_filename,
        )

        document = create_document(
            db=db,
            filename=storage_filename,
            original_filename=(
                file.filename or ""
            ),
            file_path=str(saved_path),
            file_format=(
                extension.lstrip(".")
            ),
            file_size=len(content),
            file_hash=file_hash,
        )

        document.status = "processing"

        db.commit()
        db.refresh(document)

        processing_result = (
            build_api_result(
                saved_path
            )
        )

        document = (
            apply_processing_result(
                db=db,
                document=document,
                result=processing_result,
            )
        )

        uploaded.append(
            UploadedDocumentResponse(
                document_id=document.id,
                filename=(
                    file.filename or ""
                ),
                status=document.status,
            )
        )

    except ValueError as exc:
        if (
            saved_path
            and Path(saved_path).exists()
        ):
            Path(saved_path).unlink()

        db.rollback()

        errors.append(
            UploadErrorResponse(
                filename=(
                    file.filename or ""
                ),
                error=str(exc),
            )
        )

    except OSError:
        if (
            saved_path
            and Path(saved_path).exists()
        ):
            Path(saved_path).unlink()

        db.rollback()

        errors.append(
            UploadErrorResponse(
                filename=(
                    file.filename or ""
                ),
                error="File write error",
            )
        )

    except Exception as exc:
        if (
            saved_path
            and Path(saved_path).exists()
        ):
            Path(saved_path).unlink()

        db.rollback()

        errors.append(
            UploadErrorResponse(
                filename=(
                    file.filename or ""
                ),
                error=(
                    "Database or internal error: "
                    f"{exc}"
                ),
            )
        )

    return UploadResponse(
        uploaded=uploaded,
        duplicates=duplicates,
        errors=errors,
    )


# ============================================================
# ЗАГРУЗКА ПАРЫ XML + PDF
#
# XML -> источник структурированных данных
# PDF -> оригинал для просмотра
# ============================================================

@router.post(
    "/upload-pair",
    response_model=UploadResponse,
)
async def upload_document_pair(
    source_file: UploadFile = File(
        ...,
        description=(
            "XML для автоматической обработки"
        ),
    ),
    original_file: UploadFile = File(
        ...,
        description=(
            "PDF-оригинал документа"
        ),
    ),
    db: Session = Depends(get_db),
):
    uploaded = []
    duplicates = []
    errors = []

    source_path = None
    original_path = None
    document = None

    try:
        # -------------------------
        # Проверка расширений
        # -------------------------

        source_extension = (
            validate_file_extension(
                source_file.filename or ""
            )
        )

        original_extension = (
            validate_file_extension(
                original_file.filename or ""
            )
        )

        if source_extension != ".xml":
            raise ValueError(
                "Первый файл должен быть XML"
            )

        if original_extension != ".pdf":
            raise ValueError(
                "Оригинал должен быть PDF"
            )

        # Проверяем одинаковые имена:
        # fssp_017.xml + fssp_017.pdf

        source_stem = Path(
            source_file.filename or ""
        ).stem.lower()

        original_stem = Path(
            original_file.filename or ""
        ).stem.lower()

        if source_stem != original_stem:
            raise ValueError(
                "XML и PDF должны иметь "
                "одинаковое имя файла"
            )

        # -------------------------
        # Читаем файлы
        # -------------------------

        source_content = await read_file(
            source_file
        )

        original_content = await read_file(
            original_file
        )

        source_hash = calculate_sha256(
            source_content
        )

        original_hash = calculate_sha256(
            original_content
        )

        # -------------------------
        # Проверяем дубликат XML
        # -------------------------

        duplicate = find_duplicate(
            db,
            source_hash,
        )

        if duplicate:
            duplicates.append(
                DuplicateResponse(
                    status="duplicate",
                    filename=(
                        source_file.filename
                        or ""
                    ),
                    existing_document_id=(
                        duplicate.document_id
                    ),
                )
            )

            return UploadResponse(
                uploaded=uploaded,
                duplicates=duplicates,
                errors=errors,
            )

        # -------------------------
        # Сохраняем XML
        # -------------------------

        source_storage_filename = (
            generate_storage_filename(
                ".xml"
            )
        )

        source_path = save_file(
            source_content,
            source_storage_filename,
        )

        # -------------------------
        # Создаём один Document
        # XML становится первым файлом
        # -------------------------

        document = create_document(
            db=db,
            filename=(
                source_storage_filename
            ),
            original_filename=(
                source_file.filename or ""
            ),
            file_path=str(source_path),
            file_format="xml",
            file_size=len(source_content),
            file_hash=source_hash,
        )

        # -------------------------
        # Сохраняем PDF
        # -------------------------

        original_storage_filename = (
            generate_storage_filename(
                ".pdf"
            )
        )

        original_path = save_file(
            original_content,
            original_storage_filename,
        )

        # -------------------------
        # Добавляем PDF к тому же
        # Document
        # -------------------------

        pdf_file = DocumentFile(
            document_id=document.id,
            filename=(
                original_storage_filename
            ),
            original_filename=(
                original_file.filename or ""
            ),
            file_path=str(original_path),
            file_format="pdf",
            file_size=len(
                original_content
            ),
            file_hash=original_hash,
        )

        db.add(pdf_file)

        pdf_history = DocumentHistory(
            document_id=document.id,
            event_type="file_uploaded",
            message=(
                "Original PDF uploaded: "
                f"{original_file.filename}"
            ),
        )

        db.add(pdf_history)

        document.status = "processing"

        db.commit()
        db.refresh(document)

        # -------------------------
        # Анализируем XML,
        # НЕ PDF
        # -------------------------

        processing_result = (
            build_api_result(
                source_path
            )
        )

        document = (
            apply_processing_result(
                db=db,
                document=document,
                result=processing_result,
            )
        )

        uploaded.append(
            UploadedDocumentResponse(
                document_id=document.id,
                filename=(
                    original_file.filename
                    or source_file.filename
                    or ""
                ),
                status=document.status,
            )
        )

    except Exception as exc:
        db.rollback()

        if (
            source_path
            and Path(source_path).exists()
        ):
            Path(source_path).unlink()

        if (
            original_path
            and Path(original_path).exists()
        ):
            Path(original_path).unlink()

        errors.append(
            UploadErrorResponse(
                filename=(
                    source_file.filename
                    or ""
                ),
                error=str(exc),
            )
        )

    return UploadResponse(
        uploaded=uploaded,
        duplicates=duplicates,
        errors=errors,
    )


# ============================================================
# СПИСОК ДОКУМЕНТОВ
# ============================================================

@router.get(
    "",
    response_model=list[
        DocumentListResponse
    ],
)
def get_documents(
    db: Session = Depends(get_db),
):
    documents = db.scalars(
        select(Document)
        .options(
            selectinload(
                Document.files
            )
        )
        .order_by(
            Document.created_at.desc()
        )
    ).all()

    return [
        document_to_response(
            document
        )
        for document in documents
    ]


# ============================================================
# КАРТОЧКА ДОКУМЕНТА
# ============================================================

@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
):
    document = db.scalar(
        select(Document)
        .options(
            selectinload(
                Document.files
            ),
            selectinload(
                Document.history
            ),
        )
        .where(
            Document.id
            == document_id
        )
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    response = document_to_response(
        document
    )

    response["history"] = (
        document.history
    )

    return response


# ============================================================
# ОРИГИНАЛ ДОКУМЕНТА
#
# ВАЖНО:
# если у документа есть PDF,
# всегда отдаём именно PDF.
# ============================================================

@router.get(
    "/{document_id}/file"
)
def get_document_file(
    document_id: int,
    db: Session = Depends(get_db),
):
    document = db.scalar(
        select(Document)
        .options(
            selectinload(
                Document.files
            )
        )
        .where(
            Document.id
            == document_id
        )
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    display_file = get_display_file(
        document
    )

    if display_file is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Document file not found"
            ),
        )

    file_path = Path(
        display_file.file_path
    )

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="File not found on disk",
        )

    media_types = {
        "pdf": "application/pdf",
        "xml": "application/xml",
    }

    media_type = media_types.get(
        display_file.file_format.lower(),
        "application/octet-stream",
    )

    return FileResponse(
    path=file_path,
    media_type=media_type,
    content_disposition_type="inline",
    )


# ============================================================
# ПОДТВЕРЖДЕНИЕ ИЗВЛЕЧЁННЫХ ДАННЫХ
# ============================================================

@router.put(
    "/{document_id}/verify",
    response_model=DocumentDetailResponse,
)
def verify_document_data(
    document_id: int,
    db: Session = Depends(get_db),
):
    document = db.scalar(
        select(Document)
        .options(
            selectinload(
                Document.files
            ),
            selectinload(
                Document.history
            ),
        )
        .where(
            Document.id
            == document_id
        )
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    extracted_data = dict(
        document.extracted_data or {}
    )

    extracted_data[
        "dataVerified"
    ] = True

    document.extracted_data = (
        extracted_data
    )

    history = DocumentHistory(
        document_id=document.id,
        event_type="data_verified",
        message=(
            "Extracted document data "
            "verified manually"
        ),
    )

    db.add(history)
    db.commit()
    db.refresh(document)

    response = document_to_response(
        document
    )

    response["history"] = (
        document.history
    )

    return response


# ============================================================
# РУЧНОЕ ИСПРАВЛЕНИЕ ДАННЫХ
# ============================================================

@router.put(
    "/{document_id}/data",
    response_model=DocumentDetailResponse,
)
def update_document_data(
    document_id: int,
    data: DocumentUpdate,
    db: Session = Depends(get_db),
):
    document = db.scalar(
        select(Document)
        .options(
            selectinload(
                Document.files
            ),
            selectinload(
                Document.history
            ),
        )
        .where(
            Document.id
            == document_id
        )
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    document.document_type = (
        data.documentType
    )

    document.case_number = (
        data.caseNumber
    )

    document.debtor = (
        data.debtor
    )

    document.amount = (
        data.amount
    )

    extracted_data = dict(
        document.extracted_data or {}
    )

    extracted_data[
        "enforcementNumber"
    ] = data.enforcementNumber

    extracted_data[
        "dataVerified"
    ] = True

    document.extracted_data = (
        extracted_data
    )

    history = DocumentHistory(
        document_id=document.id,
        event_type="manual_edit",
        message=(
            "Document data manually "
            "corrected and verified"
        ),
    )

    db.add(history)
    db.commit()
    db.refresh(document)

    response = document_to_response(
        document
    )

    response["history"] = (
        document.history
    )

    return response

# ============================================================
# ОТПРАВКА ДОКУМЕНТА ОТВЕТСТВЕННОМУ ПО E-MAIL
# ============================================================


@router.post(
    "/{document_id}/send-email"
)
def send_document_to_responsible(
    document_id: int,
    db: Session = Depends(get_db),
):
    """
    Отправляет документ ответственному сотруднику
    по электронной почте.

    Статус документа меняется на sent
    только после успешной SMTP-отправки.
    """

    document = db.scalar(
        select(Document)
        .options(
            selectinload(
                Document.files
            ),
            selectinload(
                Document.history
            ),
        )
        .where(
            Document.id
            == document_id
        )
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    # Отправлять можно только документы,
    # которые система отметила как требующие
    # дополнительной работы юриста.
    if not document.requires_legal_action:
        raise HTTPException(
            status_code=400,
            detail=(
                "Document does not require "
                "legal action"
            ),
        )

    extracted_data = (
        document.extracted_data or {}
    )

    # Перед отправкой данные должны быть
    # подтверждены сотрудником.
    if not extracted_data.get(
        "dataVerified",
        False,
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Document data must be "
                "verified before sending"
            ),
        )

    # Берём PDF, если он есть.
    display_file = get_display_file(
        document
    )

    if display_file is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Document file not found"
            ),
        )

    file_path = Path(
        display_file.file_path
    )

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                "Document file not found "
                "on disk"
            ),
        )

    recipient = (
        settings.SMTP_RECIPIENT
    )

    if not recipient:
        raise HTTPException(
            status_code=500,
            detail=(
                "SMTP_RECIPIENT is not "
                "configured"
            ),
        )

    original_filename = (
        display_file.original_filename
        or display_file.filename
    )

    # ========================================================
    # НОРМАЛИЗАЦИЯ НОМЕРА ДЕЛА
    # ========================================================

    raw_case_number = (
        document.case_number.strip()
        if document.case_number
        else ""
    )

    case_number = raw_case_number

    # Убираем служебные префиксы, чтобы не получилось:
    # "дело Дело № А56-..."
    lower_case_number = (
        case_number.lower()
    )

    prefixes = (
        "дело №",
        "дело n",
        "дело no",
        "дело:",
        "дело ",
        "№",
    )

    for prefix in prefixes:
        if lower_case_number.startswith(
            prefix
        ):
            case_number = (
                case_number[
                    len(prefix):
                ].strip()
            )
            break

    # Значения, которые не являются
    # реальным номером дела.
    invalid_case_values = {
        "",
        "дело",
        "номер дела",
        "номер",
        "n",
        "no",
        "-",
        "—",
        "не определено",
        "не найдено",
        "null",
        "none",
    }

    case_number_is_valid = (
        case_number.lower()
        not in invalid_case_values
        and len(case_number) >= 3
        and any(
            char.isdigit()
            for char in case_number
        )
    )

    # ========================================================
    # ТЕМА ПИСЬМА
    # ========================================================

    subject = (
        "Судебный акт требует работы юриста"
    )

    if case_number_is_valid:
        subject += (
            f" — дело {case_number}"
        )

    # ========================================================
    # ТЕЛО ПИСЬМА
    # ========================================================

    body_lines = [
        (
            "Автоматическая система анализа "
            "судебных документов определила, "
            "что документ требует "
            "дополнительной работы юриста."
        ),
        "",
        (
            f"Документ: "
            f"{original_filename}"
        ),
    ]

    # --------------------------------------------------------
    # Тип документа
    #
    # В письмо выводим только три типа,
    # которые предусмотрены задачей хакатона.
    # --------------------------------------------------------

    allowed_document_types = {
        "судебный приказ",
        "исполнительный лист",
        "постановление фссп",
    }

    document_type = (
        document.document_type.strip()
        if document.document_type
        else ""
    )

    normalized_document_type = (
        document_type.lower()
    )

    if (
        normalized_document_type
        in allowed_document_types
    ):
        body_lines.append(
            f"Тип документа: "
            f"{document_type}"
        )

    # --------------------------------------------------------
    # Номер дела
    # --------------------------------------------------------

    if case_number_is_valid:
        body_lines.append(
            f"Номер дела: "
            f"{case_number}"
        )

    # --------------------------------------------------------
    # Должник
    # --------------------------------------------------------

    if document.debtor:
        debtor = (
            document.debtor.strip()
        )

        invalid_debtor_values = {
            "",
            "-",
            "—",
            "не определено",
            "не найдено",
            "null",
            "none",
        }

        if (
            debtor.lower()
            not in invalid_debtor_values
        ):
            body_lines.append(
                f"Должник: {debtor}"
            )

    # --------------------------------------------------------
    # Сумма
    # --------------------------------------------------------

    if (
        document.amount is not None
        and document.amount >= 0
    ):
        body_lines.append(
            f"Сумма: "
            f"{document.amount:.2f} руб."
        )

    # --------------------------------------------------------
    # Причина передачи юристу
    # --------------------------------------------------------

    if document.legal_action_reason:
        body_lines.extend(
            [
                "",
                "Причина передачи юристу:",
                document.legal_action_reason,
            ]
        )

    # --------------------------------------------------------
    # Подтверждающий фрагмент
    # --------------------------------------------------------

    if document.evidence_fragment:
        evidence = (
            document.evidence_fragment
            .strip()
        )

        if evidence:
            body_lines.extend(
                [
                    "",
                    "Фрагмент документа:",
                    evidence,
                ]
            )

    body_lines.extend(
        [
            "",
            (
                "Оригинал документа "
                "прикреплён к письму."
            ),
            "",
            (
                "Сообщение сформировано "
                "автоматически."
            ),
        ]
    )

    body = "\n".join(
        body_lines
    )

    # ========================================================
    # SMTP-ОТПРАВКА
    # ========================================================

    try:
        send_document_email(
            recipient=recipient,
            subject=subject,
            body=body,
            attachment_path=file_path,
            attachment_name=(
                original_filename
            ),
        )

    except (
        ValueError,
        FileNotFoundError,
        OSError,
        smtplib.SMTPException,
    ) as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "Email sending failed: "
                f"{exc}"
            ),
        ) from exc

    # ========================================================
    # СТАТУС МЕНЯЕМ ТОЛЬКО ПОСЛЕ УСПЕШНОГО SMTP
    # ========================================================

    old_status = (
        document.status
    )

    document.status = "sent"
    document.needs_review = False
    document.review_reason = None

    history = DocumentHistory(
        document_id=document.id,
        event_type="email_sent",
        message=(
            "Document sent by email to "
            f"{recipient}. "
            f"Status changed from "
            f"{old_status} to sent"
        ),
    )

    db.add(history)

    db.commit()
    db.refresh(document)

    return {
        "success": True,
        "document_id":
            document.id,
        "status":
            document.status,
        "recipient":
            recipient,
        "message": (
            "Document successfully sent "
            "by email"
        ),
    }
# ============================================================
# ИЗМЕНЕНИЕ СТАТУСА
# ============================================================

@router.put(
    "/{document_id}/status",
    response_model=DocumentDetailResponse,
)
def update_document_status(
    document_id: int,
    status_data: StatusUpdate,
    db: Session = Depends(get_db),
):
    document = db.scalar(
        select(Document)
        .options(
            selectinload(
                Document.files
            ),
            selectinload(
                Document.history
            ),
        )
        .where(
            Document.id
            == document_id
        )
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    old_status = (
        document.status
    )

    document.status = (
        status_data.status
    )

    if status_data.status in (
        "processed",
        "sent",
    ):
        document.needs_review = False
        document.review_reason = None

    history = DocumentHistory(
        document_id=document.id,
        event_type="status_changed",
        message=(
            "Status changed from "
            f"{old_status} "
            f"to {document.status}"
        ),
    )

    db.add(history)
    db.commit()
    db.refresh(document)

    response = document_to_response(
        document
    )

    response["history"] = (
        document.history
    )

    return response