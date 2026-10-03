import re
from typing import Any


# 10 фраз-маркеров из набора организаторов.
# Если такая фраза обнаружена в значимом контексте судебного акта,
# документ требует дополнительной работы юриста.
LAWYER_MARKERS: list[dict[str, str]] = [
    {
        "id": "marker_01",
        "label": "в удовлетворении остальной части…требований отказать",
        "pattern": r"в\s+удовлетворении\s+остальной\s+части.{0,300}?требован\w*\s+отказать",
    },
    {
        "id": "marker_02",
        "label": "заявление оставить без движения",
        "pattern": r"заявлени\w*\s+оставить\s+без\s+движения",
    },
    {
        "id": "marker_03",
        "label": "возвратить…из федерального бюджета…государственной пошлины",
        "pattern": (
            r"возврат\w*.{0,300}?"
            r"из\s+федерального\s+бюджета.{0,300}?"
            r"государственн\w*\s+пошлин\w*"
        ),
    },
    {
        "id": "marker_04",
        "label": "заявление возвратить заявителю",
        "pattern": r"заявлени\w*\s+возврат\w*\s+заявител\w*",
    },
    {
        "id": "marker_05",
        "label": "оставить… без рассмотрения",
        "pattern": r"оставить.{0,300}?без\s+рассмотрения",
    },
    {
        "id": "marker_06",
        "label": "в иске отказать",
        "pattern": r"в\s+иске\s+отказать",
    },
    {
        "id": "marker_07",
        "label": "решение…отменить",
        "pattern": r"решени\w*.{0,300}?отменить",
    },
    {
        "id": "marker_08",
        "label": "направить на новое рассмотрение",
        "pattern": r"направить\s+на\s+новое\s+рассмотрение",
    },
    {
        "id": "marker_09",
        "label": "производство по делу прекратить",
        "pattern": r"производство\s+по\s+делу\s+прекратить",
    },
    {
        "id": "marker_10",
        "label": "утвердить мировое соглашение",
        "pattern": r"утвердить\s+миров\w*\s+соглашени\w*",
    },
]


RESOLUTION_HEADERS = (
    "РЕШИЛ",
    "ОПРЕДЕЛИЛ",
    "ПОСТАНОВИЛ",
    "РЕШИЛА",
    "ОПРЕДЕЛИЛА",
    "ПОСТАНОВИЛА",
)


def normalize_text(text: str) -> str:
    """
    Нормализует текст для устойчивого поиска:
    - приводит к нижнему регистру;
    - заменяет неразрывные пробелы;
    - схлопывает повторные пробелы и переносы.
    """
    if not text:
        return ""

    text = text.replace("\xa0", " ")
    text = text.replace("ё", "е")
    text = text.lower()

    # Сохраняем общий порядок слов,
    # но убираем различия между пробелами/переносами.
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def extract_resolution_part(text: str) -> str:
    """
    Пытается выделить резолютивную часть судебного акта.

    Сначала ищем последние вхождения типичных заголовков:
    РЕШИЛ / ОПРЕДЕЛИЛ / ПОСТАНОВИЛ.

    Если заголовок не найден, берём последние 35% документа.
    """
    if not text:
        return ""

    upper_text = text.upper()

    positions: list[int] = []

    for header in RESOLUTION_HEADERS:
        # Ищем все вхождения, чтобы выбрать последнее.
        for match in re.finditer(rf"\b{re.escape(header)}\s*:?", upper_text):
            positions.append(match.start())

    if positions:
        start = max(positions)
        return text[start:]

    # Fallback: резолютивная часть обычно находится ближе к концу.
    start = int(len(text) * 0.65)
    return text[start:]


def make_fragment(
    text: str,
    start: int,
    end: int,
    context_chars: int = 180,
) -> str:
    """
    Возвращает фрагмент текста вокруг найденного маркера.
    """
    fragment_start = max(0, start - context_chars)
    fragment_end = min(len(text), end + context_chars)

    fragment = text[fragment_start:fragment_end]
    fragment = re.sub(r"\s+", " ", fragment).strip()

    if fragment_start > 0:
        fragment = "... " + fragment

    if fragment_end < len(text):
        fragment = fragment + " ..."

    return fragment


def find_markers_in_text(
    text: str,
    source: str,
) -> list[dict[str, Any]]:
    """
    Ищет все маркеры в указанном тексте.
    """
    normalized = normalize_text(text)

    if not normalized:
        return []

    matches: list[dict[str, Any]] = []

    for marker in LAWYER_MARKERS:
        regex = re.compile(
            marker["pattern"],
            flags=re.IGNORECASE | re.DOTALL,
        )

        for match in regex.finditer(normalized):
            matches.append(
                {
                    "marker_id": marker["id"],
                    "marker": marker["label"],
                    "source": source,
                    "matched_text": match.group(0),
                    "fragment": make_fragment(
                        normalized,
                        match.start(),
                        match.end(),
                    ),
                }
            )

    return matches


def remove_duplicate_matches(
    matches: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Если один и тот же маркер найден и в резолютивной части,
    и затем повторно при поиске по всему документу,
    оставляем более приоритетное совпадение.
    """
    unique: dict[str, dict[str, Any]] = {}

    for match in matches:
        marker_id = match["marker_id"]

        if marker_id not in unique:
            unique[marker_id] = match
            continue

        # Резолютивная часть приоритетнее полного текста.
        if (
            match["source"] == "resolution_part"
            and unique[marker_id]["source"] != "resolution_part"
        ):
            unique[marker_id] = match

    return list(unique.values())


def analyze_lawyer_markers(text: str) -> dict[str, Any]:
    """
    Основная функция модуля.

    Возвращает:
    {
        "requires_lawyer": bool,
        "matched_markers": [...],
        "matches": [...],
        "lawyer_reason": str | None
    }

    Логика:
    1. В первую очередь проверяется резолютивная часть.
    2. Затем выполняется fallback-поиск по всему документу.
    3. Совпадения дедуплицируются.
    """

    if not text or not text.strip():
        return {
            "requires_lawyer": False,
            "matched_markers": [],
            "matches": [],
            "lawyer_reason": None,
        }

    resolution_part = extract_resolution_part(text)

    # Приоритетный поиск.
    resolution_matches = find_markers_in_text(
        resolution_part,
        source="resolution_part",
    )

    # Дополнительный поиск по всему документу.
    full_text_matches = find_markers_in_text(
        text,
        source="full_text",
    )

    all_matches = remove_duplicate_matches(
        resolution_matches + full_text_matches
    )

    matched_markers = [
        match["marker"]
        for match in all_matches
    ]

    requires_lawyer = len(all_matches) > 0

    if not requires_lawyer:
        lawyer_reason = None

    elif len(all_matches) == 1:
        lawyer_reason = (
            f'Обнаружен маркер для передачи юристу: '
            f'"{all_matches[0]["marker"]}"'
        )

    else:
        lawyer_reason = (
            f"Обнаружено маркеров для передачи юристу: "
            f"{len(all_matches)}"
        )

    return {
        "requires_lawyer": requires_lawyer,
        "matched_markers": matched_markers,
        "matches": all_matches,
        "lawyer_reason": lawyer_reason,
    }


if __name__ == "__main__":
    # Минимальный smoke-test.
    test_text = """
    Арбитражный суд рассмотрел материалы дела.

    РЕШИЛ:

    Решение Арбитражного суда первой инстанции отменить.
    Дело направить на новое рассмотрение.
    """

    result = analyze_lawyer_markers(test_text)

    from pprint import pprint

    pprint(result)
    