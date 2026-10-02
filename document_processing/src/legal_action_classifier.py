from __future__ import annotations

import re
from typing import Optional


LEGAL_ACTION_PATTERNS = {
    "Отказ в возбуждении исполнительного производства": [
        r"отказ(?:ать)?\s+в\s+возбуждени[ие]\s+исполнительного\s+производства",
    ],
    "Возврат исполнительного документа": [
        r"возврат(?:ить|ается)?\s+исполнительн\w*\s+документ\w*",
        r"исполнительн\w*\s+документ\w*\s+возвращ",
    ],
    "Отмена судебного приказа": [
        r"отмен(?:ить|ен|ён)\s+судебн\w*\s+приказ",
        r"судебн\w*\s+приказ\s+отмен",
    ],
    "Отказ в требованиях": [
        r"отказ(?:ать|ано)?\s+в\s+удовлетворении\s+требован",
        r"в\s+удовлетворении\s+требован\w*\s+отказ",
    ],
    "Возврат заявления": [
        r"возврат(?:ить|ается)?\s+заявлен",
        r"заявлен\w*\s+подлежит\s+возврат",
    ],
    "Необходимо устранить недостатки": [
        r"устранить\s+недостатк",
        r"представить\s+дополнительн\w*\s+документ",
        r"предоставить\s+дополнительн\w*\s+документ",
    ],
    "Прекращение исполнительного производства": [
        r"прекрат(?:ить|ено)\s+исполнительн\w*\s+производств",
        r"исполнительн\w*\s+производств\w*\s+прекращ",
    ],
}


FULL_RECOVERY_PATTERNS = [
    r"требован\w*\s+исполнительн\w*\s+документ\w*\s+выполнен\w*\s+в\s+полн\w*\s+объ[её]м",
    r"взыскан\w*\s+произведен\w*\s+в\s+полн\w*\s+объ[её]м",
    r"задолженность\s+погашен\w*\s+в\s+полн\w*\s+объ[её]м",
]

ENDING_PROCEEDING_PATTERNS = [
    r"окончить\s+исполнительн\w*\s+производств",
    r"исполнительн\w*\s+производств\w*\s+окончено",
]


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _find_fragment(
    text: str,
    match_start: int,
    match_end: int,
    context: int = 180,
) -> str:
    start = max(0, match_start - context)
    end = min(len(text), match_end + context)

    fragment = text[start:end].strip()

    if start > 0:
        fragment = "..." + fragment

    if end < len(text):
        fragment = fragment + "..."

    return fragment


def _search_patterns(
    text: str,
    patterns: list[str],
) -> Optional[re.Match]:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match

    return None


def classify_legal_action(
    text: str,
    extracted_data: Optional[dict] = None,
) -> dict:
    """
    Определяет, требует ли документ действий юриста.

    Возвращает:
    {
        "requires_legal_action": bool,
        "legal_action_reason": str | None,
        "evidence_fragment": str | None,
    }
    """

    if not text or not text.strip():
        return {
            "requires_legal_action": False,
            "legal_action_reason": None,
            "evidence_fragment": None,
        }

    clean_text = _clean_text(text)

    # 1. Сначала проверяем явные основания для передачи юристу
    for reason, patterns in LEGAL_ACTION_PATTERNS.items():
        match = _search_patterns(clean_text, patterns)

        if match:
            return {
                "requires_legal_action": True,
                "legal_action_reason": reason,
                "evidence_fragment": _find_fragment(
                    clean_text,
                    match.start(),
                    match.end(),
                ),
            }

    # 2. Отдельно обрабатываем окончание исполнительного производства
    ending_match = _search_patterns(
        clean_text,
        ENDING_PROCEEDING_PATTERNS,
    )

    if ending_match:
        full_recovery_match = _search_patterns(
            clean_text,
            FULL_RECOVERY_PATTERNS,
        )

        # Производство окончено после полного взыскания:
        # дополнительная работа юриста не требуется
        if full_recovery_match:
            return {
                "requires_legal_action": False,
                "legal_action_reason": None,
                "evidence_fragment": _find_fragment(
                    clean_text,
                    full_recovery_match.start(),
                    full_recovery_match.end(),
                ),
            }

        return {
            "requires_legal_action": True,
            "legal_action_reason": (
                "Окончание исполнительного производства "
                "без подтверждения полного взыскания"
            ),
            "evidence_fragment": _find_fragment(
                clean_text,
                ending_match.start(),
                ending_match.end(),
            ),
        }

    # 3. Явных оснований не нашли
    return {
        "requires_legal_action": False,
        "legal_action_reason": None,
        "evidence_fragment": None,
    }