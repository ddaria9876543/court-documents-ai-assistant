import sys
from pathlib import Path

sys.path.append("src")

from api_adapter import build_api_result


XML_PATH = Path(
    r"C:\Users\baigina\inter-rao-court-docs\data\raw_part3\courts_anonymized\fssp\O_IP_ACT_RETURN\fssp_016.xml"
)


result = build_api_result(
    XML_PATH
)

print(
    "requires_legal_action:",
    result["requires_legal_action"],
)

print(
    "legal_action_reason:",
    result["legal_action_reason"],
)

print(
    "evidence_fragment:",
    result["evidence_fragment"],
)

print(
    "status:",
    result["status"],
)

print(
    "missing_fields:",
    result["missing_fields"],
)