import re
from typing import Optional


MONTHS = {
    "января": "01",
    "февраля": "02",
    "марта": "03",
    "апреля": "04",
    "мая": "05",
    "июня": "06",
    "июля": "07",
    "августа": "08",
    "сентября": "09",
    "октября": "10",
    "ноября": "11",
    "декабря": "12",
}


def normalize_text(text: str) -> str:
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_name_part(word: str) -> str:
    """
    Осторожно убирает приставшую OCR-букву в начале слова.

    Пример:
    ЕФорматникова -> Форматникова

    Исправляем только случай:
    - первая буква заглавная;
    - вторая буква тоже заглавная;
    - третья буква строчная.

    Более сложные OCR-ошибки здесь не угадываем.
    """

    word = word.strip()

    if len(word) >= 3:
        if (
            word[0].isupper()
            and word[1].isupper()
            and word[2].islower()
        ):
            word = word[1:]

    return word


def normalize_full_name(full_name: str) -> str:
    parts = full_name.split()

    if not parts:
        return full_name.strip()

    normalized_parts = [
        normalize_name_part(part)
        for part in parts
    ]

    return " ".join(normalized_parts)


def extract_document_type(text: str) -> Optional[str]:
    if "исполнительный лист" in text.lower():
        return "исполнительный лист"

    return None


def extract_case_number(text: str) -> Optional[str]:
    match = re.search(
        r"\b\d+-\d+/\d{4}\b",
        text
    )

    return match.group(0) if match else None


def extract_inn(text: str) -> Optional[str]:
    match = re.search(
        r"\bИНН\s*[:№]?\s*(\d{10}|\d{12})\b",
        text,
        re.IGNORECASE
    )

    return match.group(1) if match else None


def extract_effective_date(text: str) -> Optional[str]:
    pattern = (
        r"\b(\d{1,2})\s+"
        r"(января|февраля|марта|апреля|мая|июня|"
        r"июля|августа|сентября|октября|ноября|декабря)"
        r"\s+(\d{4})\s*(?:года|г\.?)?"
    )

    match = re.search(
        pattern,
        text,
        re.IGNORECASE
    )

    if not match:
        return None

    day, month_name, year = match.groups()

    month = MONTHS[
        month_name.lower()
    ]

    return (
        f"{int(day):02d}."
        f"{month}."
        f"{year}"
    )


def extract_creditor(text: str) -> Optional[str]:
    match = re.search(
        r'в пользу\s+(ОАО\s+"[^"]+")',
        text,
        re.IGNORECASE
    )

    if match:
        return match.group(1)

    match = re.search(
        r'Взыскатель.*?(ОАО\s+"[^"]+")',
        text,
        re.IGNORECASE
    )

    return (
        match.group(1)
        if match
        else None
    )


def extract_debt_amount(text: str) -> Optional[str]:
    match = re.search(
        r"задолженность.*?"
        r"в размере\s+"
        r"(\d+[.,]\d{2})\s*руб",
        text,
        re.IGNORECASE
    )

    if match:
        return (
            match.group(1)
            .replace(",", ".")
        )

    return None


def extract_penalty_amount(text: str) -> Optional[str]:
    match = re.search(
        r"пени.*?"
        r"размере\s+"
        r"(\d+[.,]\d{2})\s*руб",
        text,
        re.IGNORECASE
    )

    if match:
        return (
            match.group(1)
            .replace(",", ".")
        )

    return None


def extract_state_duty(text: str) -> Optional[str]:
    match = re.search(
        r"государственной пошлины.*?"
        r"(\d+[.,]\d{2})\s*руб",
        text,
        re.IGNORECASE
    )

    if match:
        return (
            match.group(1)
            .replace(",", ".")
        )

    return None


def extract_debtors(text: str) -> list[dict]:
    """
    Извлекает должников двух типов:

    1. ФИО + дата рождения:
       Иванов Иван Иванович, 01.01.1990 г.р.

    2. ФИО + указание, что дата рождения не читается:
       Иванов Иван Иванович, дата рождения неразборчива

    Во втором случае birth_date = None.
    """

    pattern = re.compile(
        r"("
        r"[А-ЯЁ][А-ЯЁа-яё]+ "
        r"[А-ЯЁ][А-ЯЁа-яё]+ "
        r"[А-ЯЁ][А-ЯЁа-яё]+"
        r")"
        r",\s*"
        r"(?:"
        r"(\d{2}\.\d{2}\.\d{4})"
        r"\s*г\.?\s*р\.?"
        r"|"
        r"дата\s+рождения\s+"
        r"(неразборчива|не\s+читается|не\s+установлена)"
        r")",
        re.IGNORECASE
    )

    matches = pattern.findall(
        text
    )

    result = []
    seen = set()

    for (
        full_name,
        birth_date,
        unreadable_status
    ) in matches:

        full_name = normalize_full_name(
            full_name
        )

        if birth_date:
            normalized_birth_date = (
                birth_date
            )
        else:
            normalized_birth_date = None

        key = (
            full_name.lower(),
            normalized_birth_date
        )

        if key in seen:
            continue

        seen.add(key)

        result.append(
            {
                "full_name": full_name,
                "birth_date": normalized_birth_date
            }
        )

    return result


def extract_fields(text: str) -> dict:
    normalized = normalize_text(
        text
    )

    return {
        "document_type":
            extract_document_type(
                normalized
            ),

        "case_number":
            extract_case_number(
                normalized
            ),

        "effective_date":
            extract_effective_date(
                normalized
            ),

        "creditor":
            extract_creditor(
                normalized
            ),

        "creditor_inn":
            extract_inn(
                normalized
            ),

        "debtors":
            extract_debtors(
                normalized
            ),

        "debt_amount":
            extract_debt_amount(
                normalized
            ),

        "penalty_amount":
            extract_penalty_amount(
                normalized
            ),

        "state_duty":
            extract_state_duty(
                normalized
            ),
    }