from pathlib import Path

import pymupdf

from field_extractor import extract_fields
from llm_extractor import extract_fields_with_llm

from models import (
    ParsedDocument,
    ParsedPage,
    ExtractedFields,
    OfficialExtractedFields,
)

from pdf_parser import ocr_pdf

from xml_parser import (
    parse_fssp_xml,
    extract_official_fields_from_xml,
)

from validators import (
    validate_official_fields,
)


SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".xml",
}


def extract_text_from_pdf(
    pdf_path: Path,
) -> list[ParsedPage]:
    """
    Извлекает текст напрямую из PDF,
    если в документе есть текстовый слой.
    """

    document = pymupdf.open(
        pdf_path
    )

    pages = []

    try:
        for index, page in enumerate(
            document
        ):
            text = (
                page.get_text("text")
                or ""
            ).strip()

            pages.append(
                ParsedPage(
                    page_number=index + 1,
                    text=text,
                    source="pdf_text",
                    ocr_used=False,
                )
            )

    finally:
        document.close()

    return pages


def has_enough_text(
    pages: list[ParsedPage],
) -> bool:
    """
    Определяет, есть ли в PDF
    нормальный текстовый слой.

    Не требуем текст на каждой странице:
    часть страниц может быть пустой.
    """

    full_text = "\n".join(
        page.text
        for page in pages
        if page.text
    )

    letters = sum(
        1
        for char in full_text
        if char.isalpha()
    )

    return letters >= 100


def convert_ocr_pages(
    ocr_pages: list[dict],
) -> list[ParsedPage]:
    """
    Переводит результат pdf_parser.py
    в единый формат ParsedPage.
    """

    pages = []

    for page in ocr_pages:

        warnings = []

        if (
            page.get("ocr_score") is not None
            and page["ocr_score"] < 25
        ):
            warnings.append(
                "Низкое качество OCR"
            )

        pages.append(
            ParsedPage(
                page_number=page["page"],
                text=page["text"],
                source="ocr",
                ocr_used=True,
                ocr_psm=page["psm"],
                warnings=warnings,
            )
        )

    return pages


def build_extracted_fields(
    text: str,
) -> ExtractedFields:
    """
    Преобразует обычный dict
    из field_extractor.py
    в Pydantic-модель.
    """

    fields_dict = extract_fields(
        text
    )

    return ExtractedFields(
        **fields_dict
    )


def process_pdf(
    pdf_path: Path,
) -> ParsedDocument:
    """
    Универсальная предварительная
    обработка PDF.

    1. Пробуем получить текст напрямую.
    2. Если текста недостаточно —
       запускаем OCR.
    3. Собираем ParsedDocument.
    """

    warnings = []

    text_pages = extract_text_from_pdf(
        pdf_path
    )

    if has_enough_text(
        text_pages
    ):
        pages = text_pages
        extraction_method = "pdf_text"

    else:
        warnings.append(
            "Текстовый слой отсутствует "
            "или содержит слишком мало текста. "
            "Использован OCR."
        )

        ocr_pages = ocr_pdf(
            str(pdf_path)
        )

        pages = convert_ocr_pages(
            ocr_pages
        )

        extraction_method = "ocr"

    full_text = "\n\n".join(
        page.text
        for page in pages
        if page.text.strip()
    )

    # Старый extractor пока оставляем
    # для ParsedDocument и обратной
    # совместимости.
    fields = build_extracted_fields(
        full_text
    )

    status = "ok"

    if not full_text.strip():
        status = "error"

        warnings.append(
            "Не удалось извлечь текст "
            "из документа."
        )

    elif (
        fields.document_type is None
        and fields.case_number is None
    ):
        status = "warning"

        warnings.append(
            "Основные поля документа "
            "не были распознаны."
        )

    return ParsedDocument(
        file_name=pdf_path.name,
        file_path=str(pdf_path),
        file_type="pdf",
        extraction_method=extraction_method,
        pages=pages,
        full_text=full_text,
        fields=fields,
        warnings=warnings,
        status=status,
    )


def process_xml(
    xml_path: Path,
) -> ParsedDocument:
    """
    Предварительная обработка XML ФССП.

    OCR и LLM здесь не используются.
    """

    return parse_fssp_xml(
        xml_path
    )


def process_document(
    file_path: str | Path,
) -> ParsedDocument:
    """
    Единая техническая точка входа.

    Возвращает ParsedDocument.

    Используется, когда нужен:
    - распознанный текст;
    - страницы;
    - метод извлечения;
    - warnings;
    - техническая информация.
    """

    path = Path(
        file_path
    )

    if not path.exists():
        raise FileNotFoundError(
            f"Файл не найден: {path}"
        )

    extension = path.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            "Неподдерживаемый формат файла: "
            f"{extension}"
        )

    if extension == ".pdf":
        return process_pdf(
            path
        )

    if extension == ".xml":
        return process_xml(
            path
        )

    raise ValueError(
        f"Неизвестный формат: {extension}"
    )


def process_document_official(
    file_path: str | Path,
) -> OfficialExtractedFields:
    """
    Финальная точка входа для получения
    полей официального шаблона организаторов.

    PDF:
    PDF
    -> PyMuPDF / Tesseract
    -> ParsedDocument
    -> Qwen3-8B
    -> validators
    -> OfficialExtractedFields

    XML:
    XML
    -> lxml
    -> структурированные теги
    -> validators
    -> OfficialExtractedFields
    """

    path = Path(
        file_path
    )

    if not path.exists():
        raise FileNotFoundError(
            f"Файл не найден: {path}"
        )

    extension = path.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            "Неподдерживаемый формат файла: "
            f"{extension}"
        )

    # ========================================
    # PDF
    # ========================================

    if extension == ".pdf":

        document = process_pdf(
            path
        )

        if not document.full_text.strip():
            raise ValueError(
                "Не удалось получить текст "
                "из PDF-документа."
            )

        fields = extract_fields_with_llm(
            document
        )

        fields = validate_official_fields(
            fields
        )

        return fields

    # ========================================
    # XML
    # ========================================

    if extension == ".xml":

        fields = (
            extract_official_fields_from_xml(
                path
            )
        )

        fields = validate_official_fields(
            fields
        )

        return fields

    raise ValueError(
        f"Неизвестный формат: {extension}"
    )