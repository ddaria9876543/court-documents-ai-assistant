from pathlib import Path

import os

import smtplib

import sys

import csv

import pymupdf

from io import BytesIO, StringIO



from fastapi.responses import StreamingResponse

from openpyxl import Workbook

from app.core.config import settings

from fastapi import APIRouter, Depends, File, UploadFile, Query

from fastapi import HTTPException

from fastapi.responses import FileResponse

from datetime import date, datetime, time

from sqlalchemy import select, func

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

def build_short_summary(

    document: Document,

) -> str:

    document_type = (

        document.document_type

        or "Документ"

    )



    document_type = (

        document_type

        .replace("\u0301", "")

        .strip()

    )



    type_map = {

        "судебный приказ":

            "Судебный приказ",

        "исполнительный лист":

            "Исполнительный лист",

        "постановление фссп":

            "Постановление ФССП",

        "определение":

            "Определение",

        "исполнительное производство":

            "Исполнительное производство",

        "исполнительное постановление":

            "Исполнительное постановление",

    }



    normalized_type = (

        document_type.lower()

    )



    display_type = type_map.get(

        normalized_type,

        (

            document_type[:1].upper()

            + document_type[1:]

        ),

    )



    if document.requires_legal_action:

        if document.legal_action_reason:

            reason = (

                document.legal_action_reason

                .strip()

                .rstrip(".")

            )



            return (

                f"{display_type}. "

                f"Требуется внимание юриста: "

                f"{reason.lower()}."

            )



        return (

            f"{display_type}. "

            "Документ требует внимания юриста."

        )



    return (

        f"{display_type}. "

        "Дополнительных действий юриста "

        "не требуется."

    )



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

            build_short_summary(document),



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

    files: list[UploadFile] = File(

        ...,

        description="Один или несколько PDF/XML документов",

    ),

    db: Session = Depends(get_db),

):

    """

    Загружает один или несколько документов.



    Поддерживаются:

    - один PDF;

    - один XML;

    - несколько PDF;

    - несколько XML;

    - смешанная загрузка PDF + XML.



    Каждый файл обрабатывается независимо.

    Ошибка одного файла не останавливает обработку остальных.

    """



    uploaded = []

    duplicates = []

    errors = []



    for file in files:

        saved_path = None



        try:

            # --------------------------------------------------

            # 1. Проверяем формат конкретного файла

            # --------------------------------------------------



            extension = validate_file_extension(

                file.filename or ""

            )



            # --------------------------------------------------

            # 2. Читаем конкретный файл

            # --------------------------------------------------



            content = await read_file(file)



            # --------------------------------------------------

            # 3. Считаем hash

            # --------------------------------------------------



            file_hash = calculate_sha256(

                content

            )



            # --------------------------------------------------

            # 4. Проверяем дубликат

            # --------------------------------------------------



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



                # ВАЖНО:

                # не завершаем весь запрос,

                # а переходим к следующему файлу.

                continue



            # --------------------------------------------------

            # 5. Сохраняем файл

            # --------------------------------------------------



            storage_filename = (

                generate_storage_filename(

                    extension

                )

            )



            saved_path = save_file(

                content,

                storage_filename,

            )



            # --------------------------------------------------

            # 6. Для каждого файла создаём свой Document

            # --------------------------------------------------



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



            # --------------------------------------------------

            # 7. Каждый файл отправляем в processing отдельно

            #

            # PDF -> PDF pipeline

            # XML -> XML pipeline

            #

            # build_api_result сам определяет формат

            # по переданному файлу.

            # --------------------------------------------------



            try:

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



            except Exception as processing_exc:

                # Ошибка обработки конкретного файла

                # НЕ должна ронять остальные файлы.



                db.rollback()



                try:

                    document.status = "error"



                    history = DocumentHistory(

                        document_id=document.id,

                        event_type="processing_error",

                        message=(

                            "Document processing failed: "

                            f"{processing_exc}"

                        ),

                    )



                    db.add(history)

                    db.commit()

                    db.refresh(document)



                except Exception:

                    db.rollback()



                errors.append(

                    UploadErrorResponse(

                        filename=(

                            file.filename or ""

                        ),

                        error=(

                            "Processing error: "

                            f"{processing_exc}"

                        ),

                    )

                )



                continue



            # --------------------------------------------------

            # 8. Успешно обработанный файл

            # --------------------------------------------------



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

            # Ошибка формата / валидации

            # только текущего файла.



            db.rollback()



            if (

                saved_path

                and Path(saved_path).exists()

            ):

                try:

                    Path(saved_path).unlink()

                except OSError:

                    pass



            errors.append(

                UploadErrorResponse(

                    filename=(

                        file.filename or ""

                    ),

                    error=str(exc),

                )

            )



            continue



        except OSError as exc:

            # Ошибка чтения / записи

            # только текущего файла.



            db.rollback()



            if (

                saved_path

                and Path(saved_path).exists()

            ):

                try:

                    Path(saved_path).unlink()

                except OSError:

                    pass



            errors.append(

                UploadErrorResponse(

                    filename=(

                        file.filename or ""

                    ),

                    error=(

                        "File read/write error: "

                        f"{exc}"

                    ),

                )

            )



            continue



        except Exception as exc:

            # Любая другая ошибка относится

            # только к текущему файлу.



            db.rollback()



            if (

                saved_path

                and Path(saved_path).exists()

            ):

                try:

                    Path(saved_path).unlink()

                except OSError:

                    pass



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



            continue



    # ----------------------------------------------------------

    # Возвращаем общий результат всей пачки.

    #

    # Например:

    # uploaded   = 3

    # duplicates = 1

    # errors     = 1

    #

    # При этом успешные документы не теряются.

    # ----------------------------------------------------------



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

# ЭКСПОРТ ДОКУМЕНТОВ В XLSX / CSV

# ============================================================



EXPORT_COLUMNS = [

    ("document_type", "тип документа"),

    ("filename", "Файл"),

    ("street", "улица"),

    ("house", "дом"),

    ("apartment", "кв"),

    ("last_name", "фамилия"),

    ("first_name", "имя"),

    ("patronymic", "отчество"),

    ("full_name", "фио"),

    ("birth_date", "дата рождения"),

    ("passport", "паспорт"),

    ("snils", "снилс"),

    ("inn", "инн"),

    ("case_number", "дело_номер"),

    ("case_date", "дело_дата"),

    ("debt_period_start", "период_дз_начало"),

    ("debt_period_end", "период_дз_оконч"),

    ("principal_debt", "дз_осн"),

    ("penalty_amount", "дз_пени"),

    ("state_duty", "дз_пошлина"),

    ("co_defendants_count", "соответчики_кол-во"),

    ("co_defendants_names", "соответчики_фио"),

    ("missing_fields", "Не извлечено"),

    ("requires_legal_action", "Требует работы юриста"),

    ("legal_action_reason", "Причина передачи юристу"),

]

MISSING_FIELD_LABELS = {

    "document_type": "тип документа",

    "street": "улица",

    "house": "дом",

    "apartment": "квартира",

    "last_name": "фамилия",

    "first_name": "имя",

    "patronymic": "отчество",

    "full_name": "ФИО",

    "birth_date": "дата рождения",

    "passport": "паспорт",

    "snils": "СНИЛС",

    "inn": "ИНН",

    "case_number": "номер дела",

    "case_date": "дата дела",

    "debt_period_start": "начало периода задолженности",

    "debt_period_end": "окончание периода задолженности",

    "principal_debt": "основной долг",

    "penalty_amount": "пени",

    "state_duty": "госпошлина",

    "co_defendants_count": "количество соответчиков",

    "co_defendants_names": "ФИО соответчиков",

}



def _get_extracted_field(

    extracted_data: dict,

    field_name: str,

):

    """

    Берёт значение реквизита из result["fields"].



    api_adapter хранит поля в формате:



    fields = {

        "street": {

            "value": "...",

            "status": "ok"

        }

    }

    """



    fields = extracted_data.get(

        "fields",

        {},

    )



    field_data = fields.get(

        field_name

    )



    if field_data is None:

        return ""



    # Основной формат api_adapter:

    # {"value": ..., "status": ...}

    if isinstance(field_data, dict):

        value = field_data.get("value")

    else:

        # fallback на случай изменения формата

        value = field_data



    if value is None:

        return ""



    if isinstance(value, list):

        return ", ".join(

            str(item)

            for item in value

            if item is not None

        )



    return value





def build_export_row(

    document: Document,

) -> dict:



    display_file = get_display_file(

        document

    )



    extracted_data = (

        document.extracted_data

        or {}

    )



    missing_fields = (

        extracted_data.get(

            "missing_fields",

            [],

        )

        or []

    )



    if isinstance(

        missing_fields,

        list,

    ):

        missing_fields_text = ", ".join(

            MISSING_FIELD_LABELS[field]

            for field in missing_fields

            if field in MISSING_FIELD_LABELS

        )

    else:

        missing_fields_text = ""



    return {

        "document_type": (

            document.document_type

            or _get_extracted_field(

                extracted_data,

                "document_type",

            )

            or ""

        ),



        "filename": (

            display_file.original_filename

            if display_file

            else ""

        ),



        "street": _get_extracted_field(

            extracted_data,

            "street",

        ),



        "house": _get_extracted_field(

            extracted_data,

            "house",

        ),



        "apartment": _get_extracted_field(

            extracted_data,

            "apartment",

        ),



        "last_name": _get_extracted_field(

            extracted_data,

            "last_name",

        ),



        "first_name": _get_extracted_field(

            extracted_data,

            "first_name",

        ),



        "patronymic": _get_extracted_field(

            extracted_data,

            "patronymic",

        ),



        "full_name": _get_extracted_field(

            extracted_data,

            "full_name",

        ),



        "birth_date": _get_extracted_field(

            extracted_data,

            "birth_date",

        ),



        "passport": _get_extracted_field(

            extracted_data,

            "passport",

        ),



        "snils": _get_extracted_field(

            extracted_data,

            "snils",

        ),



        "inn": _get_extracted_field(

            extracted_data,

            "inn",

        ),



        "case_number": (

            document.case_number

            or _get_extracted_field(

                extracted_data,

                "case_number",

            )

            or ""

        ),



        "case_date": _get_extracted_field(

            extracted_data,

            "case_date",

        ),



        "debt_period_start":

            _get_extracted_field(

                extracted_data,

                "debt_period_start",

            ),



        "debt_period_end":

            _get_extracted_field(

                extracted_data,

                "debt_period_end",

            ),



        "principal_debt":

            _get_extracted_field(

                extracted_data,

                "principal_debt",

            ),



        "penalty_amount":

            _get_extracted_field(

                extracted_data,

                "penalty_amount",

            ),



        "state_duty":

            _get_extracted_field(

                extracted_data,

                "state_duty",

            ),



        "co_defendants_count":

            _get_extracted_field(

                extracted_data,

                "co_defendants_count",

            ),



        "co_defendants_names":

            _get_extracted_field(

                extracted_data,

                "co_defendants_names",

            ),



        "missing_fields":

            missing_fields_text,



        "requires_legal_action": (

            "Да"

            if document.requires_legal_action

            else "Нет"

        ),



        "legal_action_reason": (

            document.legal_action_reason

            or ""

        ),

    }



@router.get("/exports/download")

def export_documents(

    format: str = "xlsx",



    date_from: date | None = Query(

        default=None

    ),



    date_to: date | None = Query(

        default=None

    ),



    document_type: str | None = Query(

        default=None

    ),



    status: str | None = Query(

        default=None

    ),

    document_ids: list[int] | None = Query(

        default=None

    ),



    db: Session = Depends(get_db),

):

    """

    Формирует XLSX/CSV выгрузку.



    Поддерживает фильтры:

    - период;

    - тип документа;

    - статус.



    По умолчанию выгружаются только

    целевые типы документов хакатона.

    """



    export_format = (

        format.strip().lower()

    )



    if export_format not in {

        "xlsx",

        "csv",

    }:

        raise HTTPException(

            status_code=400,

            detail=(

                "Supported formats: "

                "xlsx, csv"

            ),

        )



    # ---------------------------------------------------------

    # Базовый запрос

    # ---------------------------------------------------------



    query = (

        select(Document)

        .options(

            selectinload(

                Document.files

            )

        )

    )



    # ---------------------------------------------------------

    # Разрешённые статусы для выгрузки

    # ---------------------------------------------------------



    exportable_statuses = {

        "processed",

        "needs_review",

        "sent",

    }



    if status:

        normalized_status = (

            status.strip().lower()

        )



        if normalized_status not in (

            exportable_statuses

        ):

            raise HTTPException(

                status_code=400,

                detail=(

                    "Unsupported export status"

                ),

            )



        query = query.where(

            Document.status

            == normalized_status

        )



    else:

        query = query.where(

            Document.status.in_(

                exportable_statuses

            )

        )



    # ---------------------------------------------------------

    # Только три основных типа из задания

    # ---------------------------------------------------------



    allowed_types = {

        "судебный приказ",

        "исполнительный лист",

        "постановление фссп",

    }



    if document_type:

        normalized_type = (

            document_type

            .strip()

            .lower()

        )



        if normalized_type not in (

            allowed_types

        ):

            raise HTTPException(

                status_code=400,

                detail=(

                    "Unsupported document type"

                ),

            )



        query = query.where(

            func.lower(

                Document.document_type

            )

            == normalized_type

        )



    else:

        query = query.where(

            func.lower(

                Document.document_type

            ).in_(

                allowed_types

            )

        )



    # ---------------------------------------------------------

    # Фильтр по датам

    # ---------------------------------------------------------



    if date_from:

        start_datetime = (

            datetime.combine(

                date_from,

                time.min,

            )

        )



        query = query.where(

            Document.created_at

            >= start_datetime

        )



    if date_to:

        end_datetime = (

            datetime.combine(

                date_to,

                time.max,

            )

        )



        query = query.where(

            Document.created_at

            <= end_datetime

        )



    # ---------------------------------------------------------

    # Получаем документы

    # ---------------------------------------------------------

    # ---------------------------------------------------------

    # Ручной выбор конкретных документов

    # ---------------------------------------------------------



    if document_ids:

        query = query.where(

            Document.id.in_(

                document_ids

            )

        )

    documents = db.scalars(

        query.order_by(

            Document.created_at.desc()

        )

    ).all()



    rows = [

        build_export_row(document)

        for document in documents

    ]



    # =========================================================

    # CSV

    # =========================================================



    if export_format == "csv":



        output = StringIO()



        writer = csv.writer(

            output,

            delimiter=";",

            lineterminator="\n",

        )



        writer.writerow(

            [

                title

                for _, title

                in EXPORT_COLUMNS

            ]

        )



        for row in rows:



            writer.writerow(

                [

                    row.get(key, "")

                    for key, _

                    in EXPORT_COLUMNS

                ]

            )



        content = (

            "\ufeff"

            + output.getvalue()

        )



        return StreamingResponse(

            iter(

                [

                    content.encode(

                        "utf-8"

                    )

                ]

            ),

            media_type=(

                "text/csv; "

                "charset=utf-8"

            ),

            headers={

                "Content-Disposition":

                    (

                        'attachment; '

                        'filename="documents.csv"'

                    )

            },

        )



    # =========================================================

    # XLSX

    # =========================================================



    workbook = Workbook()



    worksheet = workbook.active



    worksheet.title = "Документы"



    worksheet.append(

        [

            title

            for _, title

            in EXPORT_COLUMNS

        ]

    )



    for row in rows:



        worksheet.append(

            [

                row.get(key, "")

                for key, _

                in EXPORT_COLUMNS

            ]

        )



    worksheet.freeze_panes = "A2"



    worksheet.auto_filter.ref = (

        worksheet.dimensions

    )



    output = BytesIO()



    workbook.save(output)



    output.seek(0)



    return StreamingResponse(

        output,

        media_type=(

            "application/"

            "vnd.openxmlformats-"

            "officedocument."

            "spreadsheetml.sheet"

        ),

        headers={

            "Content-Disposition":

                (

                    'attachment; '

                    'filename="documents.xlsx"'

                )

        },

    )

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
# ПРЕВЬЮ ПЕРВОЙ СТРАНИЦЫ PDF
# ============================================================

@router.get("/{document_id}/preview")
def get_document_preview(
    document_id: int,
    db: Session = Depends(get_db),
):
    document = db.scalar(
        select(Document)
        .options(selectinload(Document.files))
        .where(Document.id == document_id)
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    display_file = get_display_file(document)

    if display_file is None:
        raise HTTPException(
            status_code=404,
            detail="Document file not found",
        )

    if display_file.file_format.lower() != "pdf":
        raise HTTPException(
            status_code=400,
            detail="Preview is available only for PDF files",
        )

    file_path = Path(display_file.file_path)

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="File not found on disk",
        )

    try:
        with pymupdf.open(file_path) as pdf_document:
            if pdf_document.page_count == 0:
                raise HTTPException(
                    status_code=422,
                    detail="PDF has no pages",
                )

            page = pdf_document.load_page(0)
            pixmap = page.get_pixmap(
                matrix=pymupdf.Matrix(1.4, 1.4),
                alpha=False,
            )
            image_bytes = pixmap.tobytes("png")

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to render PDF preview: {exc}",
        ) from exc

    return StreamingResponse(
        BytesIO(image_bytes),
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=3600",
        },
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