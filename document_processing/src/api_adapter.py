from pathlib import Path
from typing import Any

from pipeline import process_document_official


def _field_status(value: Any) -> str:
    if value is None:
        return "not_found"

    if isinstance(value, str) and not value.strip():
        return "not_found"

    if isinstance(value, list) and not value:
        return "not_found"

    return "ok"


def _source_type(file_path: Path) -> str:
    suffix = file_path.suffix.lower()

    if suffix == ".xml":
        return "xml"

    if suffix == ".pdf":
        return "scan"

    return suffix.lstrip(".") or "unknown"


def _build_summary(data: dict) -> str:
    parts = []

    document_type = data.get("document_type")
    case_number = data.get("case_number")
    debtor = (
        data.get("full_name")
        or data.get("co_defendants_names")
    )
    amount = data.get("principal_debt")

    if document_type:
        parts.append(
            f"Тип документа: {document_type}"
        )

    if case_number:
        parts.append(
            f"дело № {case_number}"
        )

    if debtor:
        parts.append(
            f"должник: {debtor}"
        )

    if amount:
        parts.append(
            f"основная задолженность: {amount} руб"
        )

    if not parts:
        return "Не удалось сформировать краткое описание документа."

    return ". ".join(parts) + "."


def _document_status(data: dict) -> str:
    extraction_status = data.get("status")

    if extraction_status == "ok":
        return "processed"

    if extraction_status == "unclear":
        return "needs_review"

    return "needs_review"


def _to_float_or_none(value: Any) -> float | None:
    if value is None:
        return None

    try:
        return float(
            str(value)
            .replace(" ", "")
            .replace(",", ".")
        )
    except (TypeError, ValueError):
        return None


def build_api_result(file_path: str | Path) -> dict:
    path = Path(file_path)

    fields_model = process_document_official(path)
    data = fields_model.model_dump()

    debtor = (
        data.get("full_name")
        or data.get("co_defendants_names")
    )

    principal_debt_raw = data.get(
        "principal_debt"
    )

    principal_debt = _to_float_or_none(
        principal_debt_raw
    )

    amounts = [
        value
        for value in [
            data.get("principal_debt"),
            data.get("penalty_amount"),
            data.get("state_duty"),
        ]
        if value is not None
    ]

    fields = {}

    excluded_fields = {
        "missing_fields",
        "warnings",
        "status",
    }

    for field_name, value in data.items():
        if field_name in excluded_fields:
            continue

        fields[field_name] = {
            "value": value,
            "status": _field_status(value),
        }

    fields["amount"] = {
        "value": amounts,
        "status": _field_status(amounts),
    }

    return {
        "filename": path.name,
        "source_type": _source_type(path),
        "document_type": data.get("document_type"),
        "summary": _build_summary(data),
        "debtor": debtor,
        "amount": principal_debt,
        "status": _document_status(data),
        "fields": fields,
        "warnings": data.get("warnings", []),
        "extraction_status": data.get("status"),
    }