from pathlib import Path
from typing import Optional
import re

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
    Все XML ФССП из официального набора
    относятся к постановлениям ФССП.
    """

    return "постановление ФССП"


def normalize_date(
    value: Optional[str],
) -> Optional[str]:
    """
    DD.MM.YYYY -> YYYY-MM-DD.
    """

    if not value:
        return None

    value = value.strip()

    match = re.fullmatch(
        r"(\d{2})\.(\d{2})\.(\d{4})",
        value,
    )

    if match:

        day, month, year = match.groups()

        return f"{year}-{month}-{day}"

    return value


def normalize_amount(
    value: Optional[str],
) -> Optional[str]:
    """
    88 300,94 -> 88300.94
    """

    if not value:
        return None

    value = (
        value
        .replace("\xa0", "")
        .replace(" ", "")
        .replace(",", ".")
        .strip()
    )

    match = re.search(
        r"-?\d+(?:\.\d+)?",
        value,
    )

    if not match:
        return None

    return match.group(0)


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


def normalize_house_value(
    value: Optional[str],
) -> Optional[str]:
    """
    Нормализует дом/корпус.

    26 А  -> 26/А
    137а  -> 137/а
    62к1  -> 62 корп.1
    """

    if not value:
        return None

    value = value.strip()

    match = re.fullmatch(
        r"(\d+)\s+([А-Яа-яA-Za-z])",
        value,
    )

    if match:
        return (
            f"{match.group(1)}/"
            f"{match.group(2)}"
        )

    match = re.fullmatch(
        r"(\d+)([А-Яа-яA-Za-z])",
        value,
    )

    if match:
        return (
            f"{match.group(1)}/"
            f"{match.group(2)}"
        )

    match = re.fullmatch(
        r"(.+?)к(\d+)",
        value,
        flags=re.IGNORECASE,
    )

    if match:
        return (
            f"{match.group(1)} "
            f"корп.{match.group(2)}"
        )

    return value


def parse_address(
    address: Optional[str],
    debt_text: Optional[str] = None,
) -> tuple[
    Optional[str],
    Optional[str],
    Optional[str],
]:
    """
    Разбирает DbtrAdr ФССП.

    Если тип улицы отсутствует в DbtrAdr,
    дополнительно смотрит IdDebtText.
    """

    if not address:
        return None, None, None

    parts = [
        part.strip()
        for part in address.split(",")
    ]

    debt_text = debt_text or ""

    # ========================================================
    # Город
    # ========================================================

    city = None

    for part in parts:

        match = re.match(
            r"^г\.?\s+(.+)$",
            part,
            flags=re.IGNORECASE,
        )

        if match:
            city = match.group(1).strip()
            break

    if city is None:

        for index in (4, 5):

            if len(parts) <= index:
                continue

            candidate = parts[index].strip()

            if candidate:
                city = re.sub(
                    r"^г\.?\s*",
                    "",
                    candidate,
                    flags=re.IGNORECASE,
                ).strip()
                break

    # ========================================================
    # Улица
    # ========================================================

    street_raw = None
    street_type = None

    for part in parts:

        value = part.strip()

        patterns = [
            (
                r"^ул\.?\s+(.+)$",
                "ул.",
            ),
            (
                r"^пер\.?\s+(.+)$",
                "пер.",
            ),
            (
                r"^(?:пр-кт|проспект)\.?\s+(.+)$",
                "пр-кт",
            ),
            (
                r"^городок\.?\s+(.+)$",
                "городок.",
            ),
            (
                r"^(.+?)\s+ул\.?$",
                "ул.",
            ),
        ]

        found = False

        for pattern, prefix in patterns:

            match = re.match(
                pattern,
                value,
                flags=re.IGNORECASE,
            )

            if match:
                street_raw = (
                    match.group(1).strip()
                )
                street_type = prefix
                found = True
                break

        if found:
            break

    # Машинный DbtrAdr
    if street_raw is None and len(parts) > 6:

        candidate = parts[6].strip()

        if candidate:
            street_raw = candidate

    # ========================================================
    # Определяем тип улицы по IdDebtText
    # ========================================================

    if street_raw and not street_type:

        escaped = re.escape(
            street_raw.strip()
        )

        # пр-кт Макетчиков
        if re.search(
            rf"\b(?:пр-кт|проспект)\s+{escaped}\b",
            debt_text,
            flags=re.IGNORECASE,
        ):
            street_type = "пр-кт"

        # Примерный пер.
        elif re.search(
            rf"\b{escaped}\s+пер\.?",
            debt_text,
            flags=re.IGNORECASE,
        ):
            street_type = "пер."

        elif re.search(
            rf"\bпер\.?\s+{escaped}\b",
            debt_text,
            flags=re.IGNORECASE,
        ):
            street_type = "пер."

        # Учебный городок
        elif re.search(
            rf"\b{escaped}\s+городок\b",
            debt_text,
            flags=re.IGNORECASE,
        ):
            street_type = "городок."

        elif re.search(
            rf"\bгородок\.?\s+{escaped}\b",
            debt_text,
            flags=re.IGNORECASE,
        ):
            street_type = "городок."

        else:
            street_type = "ул."

    # ========================================================
    # Порядковые улицы
    # ========================================================

    if street_raw:

        # Явный формат:
        # 5-я Образцовая -> Образцовая 5-я
        match = re.match(
            r"^(\d+-[яйая])\s+(.+)$",
            street_raw,
            flags=re.IGNORECASE,
        )

        if match:

            ordinal = match.group(1)
            name = match.group(2)

            street_raw = (
                f"{name} {ordinal}"
            )

        else:

            # Неявный формат типа:
            # 11 Контурная.
            #
            # Если IdDebtText повторяет исходный
            # вариант "ул. 11 Контурная",
            # оставляем его как есть.
            bare_match = re.match(
                r"^(\d+)\s+(.+)$",
                street_raw,
                flags=re.IGNORECASE,
            )

            if bare_match:

                number = bare_match.group(1)
                name = bare_match.group(2)

                original_pattern = (
                    rf"ул\.?\s+"
                    rf"{re.escape(number)}\s+"
                    rf"{re.escape(name)}"
                )

                if not re.search(
                    original_pattern,
                    debt_text,
                    flags=re.IGNORECASE,
                ):
                    street_raw = (
                        f"{name} {number}-я"
                    )

    # ========================================================
    # Дом
    # ========================================================

    house = None

    for index, part in enumerate(parts):

        match = re.match(
            r"^д\.?\s*(.+)$",
            part,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        house = normalize_house_value(
            match.group(1)
        )

        if index + 1 < len(parts):

            next_part = parts[index + 1].strip()

            corpus_match = re.match(
                r"^корп\.?\s*(.+)$",
                next_part,
                flags=re.IGNORECASE,
            )

            if corpus_match:

                corpus = (
                    corpus_match
                    .group(1)
                    .strip()
                )

                if corpus:

                    if re.fullmatch(
                        r"[А-Яа-яA-Za-z]",
                        corpus,
                    ):
                        house = (
                            f"{house}/{corpus}"
                        )

                    else:
                        house = (
                            f"{house} корп.{corpus}"
                        )

        break

    if house is None and len(parts) > 7:

        house = normalize_house_value(
            parts[7]
        )

    # ========================================================
    # Квартира
    # ========================================================

    apartment = None

    for part in parts:

        match = re.match(
            r"^кв\.?\s*(.+)$",
            part,
            flags=re.IGNORECASE,
        )

        if match:
            apartment = (
                match.group(1).strip()
            )
            break

    if apartment is None and len(parts) > 8:

        candidate = parts[8].strip()

        if candidate:
            apartment = candidate

    # ========================================================
    # Результат
    # ========================================================

    street_parts = []

    if city:

        city_clean = re.sub(
            r"^г\.?\s*",
            "",
            city,
            flags=re.IGNORECASE,
        ).strip()

        if city_clean:
            street_parts.append(
                f"г {city_clean}"
            )

    if street_raw:

        street_parts.append(
            f"{street_type or 'ул.'} "
            f"{street_raw}"
        )

    street = (
        ", ".join(street_parts)
        if street_parts
        else None
    )

    return (
        street,
        house,
        apartment,
    )
def extract_debt_period(
    debt_text: Optional[str],
) -> tuple[
    Optional[str],
    Optional[str],
]:
    """
    Извлекает основной период задолженности.
    """

    if not debt_text:
        return None, None

    date_pattern = (
        r"(\d{2}\.\d{2}\.\d{4})"
        r"(?:\s*г\.?)?"
    )

    patterns = [
        (
            r"задолженн\w*"
            r".{0,500}?"
            r"за\s+период\s+с\s+"
            + date_pattern
            + r"\s+по\s+"
            + date_pattern
        ),
        (
            r"за\s+период\s+с\s+"
            + date_pattern
            + r"\s+по\s+"
            + date_pattern
        ),
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            debt_text,
            flags=(
                re.IGNORECASE
                | re.DOTALL
            ),
        )

        if match:

            return (
                normalize_date(
                    match.group(1)
                ),
                normalize_date(
                    match.group(2)
                ),
            )

    return None, None
def extract_principal_debt(
    debt_text: Optional[str],
) -> Optional[str]:
    """
    Извлекает именно основной долг,
    а не общую сумму задолженности ФССП.
    """

    if not debt_text:
        return None

    patterns = [
        (
            r"задолженн\w*"
            r".{0,500}?"
            r"в\s+размере\s+"
            r"([\d\s]+(?:[,.]\d{1,2})?)"
            r"\s*руб"
        ),
        (
            r"основн\w*\s+долг\w*"
            r".{0,100}?"
            r"(?:в\s+размере\s+)?"
            r"([\d\s]+(?:[,.]\d{1,2})?)"
            r"\s*руб"
        ),
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            debt_text,
            flags=(
                re.IGNORECASE
                | re.DOTALL
            ),
        )

        if match:

            return normalize_amount(
                match.group(1)
            )

    return None


def extract_penalty(
    debt_text: Optional[str],
) -> Optional[str]:
    """
    Извлекает пени.
    """

    if not debt_text:
        return None

    pattern = (
        r"\bпен(?:я|и|ей)\b"
        r".{0,150}?"
        r"(?:в\s+размере\s+)?"
        r"([\d\s]+(?:[,.]\d{1,2})?)"
        r"\s*руб"
    )

    match = re.search(
        pattern,
        debt_text,
        flags=(
            re.IGNORECASE
            | re.DOTALL
        ),
    )

    if not match:
        return None

    return normalize_amount(
        match.group(1)
    )


def extract_state_duty(
    debt_text: Optional[str],
) -> Optional[str]:
    """
    Извлекает государственную пошлину.
    """

    if not debt_text:
        return None

    patterns = [
        (
            r"государственн\w*\s+"
            r"пошлин\w*"
            r".{0,120}?"
            r"(?:в\s+размере\s+)?"
            r"([\d\s]+(?:[,.]\d{1,2})?)"
            r"\s*руб"
        ),
        (
            r"госпошлин\w*"
            r".{0,120}?"
            r"(?:в\s+размере\s+)?"
            r"([\d\s]+(?:[,.]\d{1,2})?)"
            r"\s*руб"
        ),
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            debt_text,
            flags=(
                re.IGNORECASE
                | re.DOTALL
            ),
        )

        if match:

            return normalize_amount(
                match.group(1)
            )

    return None


def extract_postal_cost(
    debt_text: Optional[str],
) -> Optional[str]:
    """
    Извлекает почтовые расходы.
    """

    if not debt_text:
        return None

    pattern = (
        r"почтов\w*\s+расход\w*"
        r".{0,120}?"
        r"(?:в\s+размере\s+)?"
        r"([\d\s]+(?:[,.]\d{1,2})?)"
        r"\s*руб"
    )

    match = re.search(
        pattern,
        debt_text,
        flags=(
            re.IGNORECASE
            | re.DOTALL
        ),
    )

    if not match:
        return None

    return normalize_amount(
        match.group(1)
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

    # ========================================
    # XML-теги
    # ========================================

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

    enforcement_number = find_text(
        root,
        "IpNo",
    )

    debt_text = find_text(
        root,
        "IdDebtText",
    )
    id_debt_sum = find_text(
    root,
    "IdDebtSum",
    )

    # ========================================
    # ФИО
    # ========================================

    (
        last_name,
        first_name,
        patronymic,
    ) = split_name(
        debtor_name
    )

    # ========================================
    # Адрес
    # ========================================

    (
        street,
        house,
        apartment,
    ) = parse_address(
        debtor_address,
        debt_text,
    )
    # ========================================
    # Период задолженности
    # ========================================

    (
        debt_period_start,
        debt_period_end,
    ) = extract_debt_period(
        debt_text
    )

    # ========================================
    # Суммы
    # ========================================

    principal_debt = (
        extract_principal_debt(
            debt_text
        )
    )

    if principal_debt is None:
        principal_debt = normalize_amount(
            id_debt_sum
        )
    penalty_amount = (
        extract_penalty(
            debt_text
        )
    )

    state_duty = (
        extract_state_duty(
            debt_text
        )
    )

    postal_cost = (
        extract_postal_cost(
            debt_text
        )
    )

    # ========================================
    # Итог
    # ========================================

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

        birth_date=(
            normalize_date(
                debtor_birth_date
            )
        ),

        passport=None,
        snils=debtor_snils,
        inn=debtor_inn,

        case_number=case_number,

        case_date=(
            normalize_date(
                case_date
            )
        ),

        enforcement_number=(
            enforcement_number
        ),

        debt_period_start=(
            debt_period_start
        ),

        debt_period_end=(
            debt_period_end
        ),

        principal_debt=(
            principal_debt
        ),

        penalty_amount=(
            penalty_amount
        ),

        state_duty=(
            state_duty
        ),

        postal_cost=(
            postal_cost
        ),

        co_defendants_count=1,

        co_defendants_names=(
            debtor_name
        ),

        warnings=[],
    )

    # ========================================
    # missing_fields
    # ========================================

    ignored_fields = {
        "missing_fields",
        "warnings",
        "status",
        "requires_legal_action",
        "legal_action_reason",
        "evidence_fragment",
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