from pathlib import Path
from typing import Optional

from lxml import etree

from models import (
    ParsedDocument,
    ParsedPage,
    ExtractedFields,
    OfficialExtractedFields,
)


def local_name(tag: str) -> str:
    """
    Возвращает имя XML-тега без namespace.
    """

    if "}" in tag:
        return tag.split("}", 1)[1]

    return tag


def find_text(
    root: etree._Element,
    tag_name: str,
) -> Optional[str]:
    """
    Ищет первый тег по локальному имени,
    независимо от namespace.
    """

    for element in root.iter():

        if local_name(element.tag) != tag_name:
            continue

        if element.text is None:
            return None

        value = element.text.strip()

        return value or None

    return None


def build_flat_text(
    root: etree._Element,
) -> str:
    """
    Собирает XML в плоский текст.
    """

    lines = []

    for element in root.iter():

        value = (
            element.text.strip()
            if element.text
            else ""
        )

        if not value:
            continue

        lines.append(
            f"{local_name(element.tag)}: {value}"
        )

    return "\n".join(lines)


def normalize_document_type(
    doc_name: Optional[str],
) -> Optional[str]:
    """
    Приводит название документа ФССП
    к официальному типу проекта.
    """

    if not doc_name:
        return None

    return "постановление ФССП"


def parse_address(
    address: Optional[str],
) -> tuple[
    Optional[str],
    Optional[str],
    Optional[str],
]:
    """
    Пока безопасно не угадываем структуру адреса.

    XML ФССП может хранить адрес одной строкой,
    поэтому street / house / apartment
    заполняются только если позже будет
    надёжный parser.
    """

    return None, None, None


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


def extract_official_fields_from_xml(
    xml_path: str | Path,
) -> OfficialExtractedFields:
    """
    Извлекает поля официального шаблона
    напрямую из XML ФССП.

    OCR и LLM здесь не используются.
    """

    path = Path(xml_path)

    if not path.exists():
        raise FileNotFoundError(
            f"XML-файл не найден: {path}"
        )

    parser = etree.XMLParser(
        recover=True,
        remove_blank_text=True,
    )

    tree = etree.parse(
        str(path),
        parser,
    )

    root = tree.getroot()

    # ---------------------------------
    # Основные поля
    # ---------------------------------

    doc_name = find_text(
        root,
        "DocName",
    )

    debtor_name = find_text(
        root,
        "DbtrName",
    )

    debtor_birth_date = find_text(
        root,
        "idDbtrBorn",
    )

    debtor_address = find_text(
        root,
        "DbtrAdr",
    )

    debtor_inn = find_text(
        root,
        "DbtrInn",
    )

    debtor_snils = find_text(
        root,
        "IdDbtrSNILS",
    )

    case_number = find_text(
        root,
        "IdDeloNo",
    )

    case_date = find_text(
        root,
        "IdDeloDate",
    )

    debt_amount = find_text(
        root,
        "IdDebtSum",
    )

    # ---------------------------------
    # ФИО
    # ---------------------------------

    (
        last_name,
        first_name,
        patronymic,
    ) = split_name(
        debtor_name
    )

    # ---------------------------------
    # Адрес
    # ---------------------------------

    (
        street,
        house,
        apartment,
    ) = parse_address(
        debtor_address
    )

    # ---------------------------------
    # Итог
    # ---------------------------------

    fields = OfficialExtractedFields(
        document_type=(
            normalize_document_type(
                doc_name
            )
        ),

        street=street,
        house=house,
        apartment=apartment,

        last_name=last_name,
        first_name=first_name,
        patronymic=patronymic,
        full_name=debtor_name,

        birth_date=debtor_birth_date,

        passport=None,
        snils=debtor_snils,
        inn=debtor_inn,

        case_number=case_number,
        case_date=case_date,

        debt_period_start=None,
        debt_period_end=None,

        principal_debt=debt_amount,
        penalty_amount=None,
        state_duty=None,

        co_defendants_count=1,
        co_defendants_names=debtor_name,

        warnings=[],
    )

    # ---------------------------------
    # missing_fields
    # ---------------------------------

    ignored_fields = {
        "missing_fields",
        "warnings",
    }

    missing = []

    for (
        field_name,
        value,
    ) in fields.model_dump().items():

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


def parse_fssp_xml(
    xml_path: str | Path,
) -> ParsedDocument:
    """
    Формирует ParsedDocument для XML ФССП.
    """

    path = Path(xml_path)

    if not path.exists():
        raise FileNotFoundError(
            f"XML-файл не найден: {path}"
        )

    parser = etree.XMLParser(
        recover=True,
        remove_blank_text=True,
    )

    tree = etree.parse(
        str(path),
        parser,
    )

    root = tree.getroot()

    full_text = build_flat_text(
        root
    )

    # Старую модель оставляем,
    # чтобы не ломать ParsedDocument.
    old_fields = ExtractedFields(
        document_type=find_text(
            root,
            "DocName",
        ),

        case_number=find_text(
            root,
            "IdDeloNo",
        ),

        effective_date=find_text(
            root,
            "IdDeloDate",
        ),

        creditor=find_text(
            root,
            "IdCrdrName",
        ),

        debt_amount=find_text(
            root,
            "IdDebtSum",
        ),
    )

    page = ParsedPage(
        page_number=1,
        text=full_text,
        source="xml",
        ocr_used=False,
    )

    warnings = []

    if not full_text:
        warnings.append(
            "XML не содержит извлекаемого текста."
        )

    return ParsedDocument(
        file_name=path.name,
        file_path=str(path),
        file_type="xml",
        extraction_method="xml",
        pages=[page],
        full_text=full_text,
        fields=old_fields,
        warnings=warnings,
        status=(
            "ok"
            if full_text
            else "error"
        ),
    )