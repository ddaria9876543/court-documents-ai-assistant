from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_file import DocumentFile
from app.models.processing_event import ProcessingEvent
from app.models.stg_document_extraction import StgDocumentExtraction


DOCUMENT_STATUSES = {
    "new",
    "processing",
    "processed",
    "needs_review",
    "error",
    "sent",
}

PROCESSING_STATUSES = {
    "ok",
    "unclear",
    "invalid",
    "conflict",
    "multiple_values",
    "not_found",
    "warning",
    "needs_review",
    "error",
}


@dataclass
class DQResult:
    check_name: str
    passed: bool
    failed_rows: int
    description: str


def check_duplicate_file_hashes(
    db: Session,
) -> DQResult:
    duplicate_count = db.scalar(
        select(func.count())
        .select_from(
            select(
                DocumentFile.file_hash
            )
            .group_by(
                DocumentFile.file_hash
            )
            .having(
                func.count(DocumentFile.id) > 1
            )
            .subquery()
        )
    ) or 0

    return DQResult(
        check_name="duplicate_file_hashes",
        passed=duplicate_count == 0,
        failed_rows=duplicate_count,
        description=(
            "file_hash должен быть уникальным "
            "для защиты от повторной загрузки файлов"
        ),
    )


def check_invalid_document_statuses(
    db: Session,
) -> DQResult:
    failed_rows = db.scalar(
        select(
            func.count(Document.id)
        ).where(
            Document.status.not_in(
                DOCUMENT_STATUSES
            )
        )
    ) or 0

    return DQResult(
        check_name="invalid_document_statuses",
        passed=failed_rows == 0,
        failed_rows=failed_rows,
        description=(
            "documents.status должен содержать "
            "только допустимые значения"
        ),
    )


def check_processed_documents_without_type(
    db: Session,
) -> DQResult:
    failed_rows = db.scalar(
        select(
            func.count(Document.id)
        ).where(
            Document.status == "processed",
            Document.document_type.is_(None),
        )
    ) or 0

    return DQResult(
        check_name="processed_documents_without_type",
        passed=failed_rows == 0,
        failed_rows=failed_rows,
        description=(
            "Обработанный документ должен иметь document_type"
        ),
    )


def check_negative_amounts(
    db: Session,
) -> DQResult:
    failed_rows = db.scalar(
        select(
            func.count(
                StgDocumentExtraction.id
            )
        ).where(
            (
                StgDocumentExtraction.principal_debt < 0
            )
            | (
                StgDocumentExtraction.penalty_amount < 0
            )
            | (
                StgDocumentExtraction.state_duty < 0
            )
            | (
                StgDocumentExtraction.postal_cost < 0
            )
        )
    ) or 0

    return DQResult(
        check_name="negative_amounts",
        passed=failed_rows == 0,
        failed_rows=failed_rows,
        description=(
            "Денежные значения не должны быть отрицательными"
        ),
    )


def check_invalid_processing_statuses(
    db: Session,
) -> DQResult:
    failed_rows = db.scalar(
        select(
            func.count(
                StgDocumentExtraction.id
            )
        ).where(
            StgDocumentExtraction.processing_status.not_in(
                PROCESSING_STATUSES
            )
        )
    ) or 0

    return DQResult(
        check_name="invalid_processing_statuses",
        passed=failed_rows == 0,
        failed_rows=failed_rows,
        description=(
            "processing_status должен содержать "
            "только допустимые значения"
        ),
    )


def check_duplicate_processing_attempts(
    db: Session,
) -> DQResult:
    duplicate_count = db.scalar(
        select(func.count())
        .select_from(
            select(
                StgDocumentExtraction.document_id,
                StgDocumentExtraction.attempt,
            )
            .group_by(
                StgDocumentExtraction.document_id,
                StgDocumentExtraction.attempt,
            )
            .having(
                func.count(
                    StgDocumentExtraction.id
                ) > 1
            )
            .subquery()
        )
    ) or 0

    return DQResult(
        check_name="duplicate_processing_attempts",
        passed=duplicate_count == 0,
        failed_rows=duplicate_count,
        description=(
            "Для одного document_id номер attempt "
            "не должен повторяться"
        ),
    )


def check_negative_event_duration(
    db: Session,
) -> DQResult:
    failed_rows = db.scalar(
        select(
            func.count(
                ProcessingEvent.id
            )
        ).where(
            ProcessingEvent.duration_ms < 0
        )
    ) or 0

    return DQResult(
        check_name="negative_event_duration",
        passed=failed_rows == 0,
        failed_rows=failed_rows,
        description=(
            "duration_ms не может быть отрицательным"
        ),
    )


def check_errors_without_message(
    db: Session,
) -> DQResult:
    failed_rows = db.scalar(
        select(
            func.count(
                ProcessingEvent.id
            )
        ).where(
            ProcessingEvent.status == "error",
            ProcessingEvent.error_message.is_(None),
        )
    ) or 0

    return DQResult(
        check_name="errors_without_message",
        passed=failed_rows == 0,
        failed_rows=failed_rows,
        description=(
            "Processing event со статусом error "
            "должен содержать error_message"
        ),
    )
import re
from datetime import datetime


def check_invalid_inn(
    db: Session,
) -> DQResult:
    values = db.scalars(
        select(
            StgDocumentExtraction.inn
        ).where(
            StgDocumentExtraction.inn.is_not(None)
        )
    ).all()

    failed_rows = 0

    for value in values:
        normalized = re.sub(
            r"\D",
            "",
            value,
        )

        if len(normalized) not in (10, 12):
            failed_rows += 1

    return DQResult(
        check_name="invalid_inn",
        passed=failed_rows == 0,
        failed_rows=failed_rows,
        description=(
            "ИНН должен содержать "
            "10 или 12 цифр"
        ),
    )


def check_invalid_snils(
    db: Session,
) -> DQResult:
    values = db.scalars(
        select(
            StgDocumentExtraction.snils
        ).where(
            StgDocumentExtraction.snils.is_not(None)
        )
    ).all()

    failed_rows = 0

    for value in values:
        normalized = re.sub(
            r"\D",
            "",
            value,
        )

        if len(normalized) != 11:
            failed_rows += 1

    return DQResult(
        check_name="invalid_snils",
        passed=failed_rows == 0,
        failed_rows=failed_rows,
        description=(
            "СНИЛС должен содержать 11 цифр"
        ),
    )


def is_valid_iso_date(
    value: str | None,
) -> bool:
    if value is None:
        return True

    try:
        datetime.strptime(
            value,
            "%Y-%m-%d",
        )
        return True
    except ValueError:
        return False


def check_invalid_dates(
    db: Session,
) -> DQResult:
    rows = db.scalars(
        select(
            StgDocumentExtraction
        )
    ).all()

    failed_rows = 0

    for row in rows:
        dates = [
            row.case_date,
            row.birth_date,
            row.debt_period_start,
            row.debt_period_end,
        ]

        if any(
            not is_valid_iso_date(value)
            for value in dates
        ):
            failed_rows += 1

    return DQResult(
        check_name="invalid_dates",
        passed=failed_rows == 0,
        failed_rows=failed_rows,
        description=(
            "Дата должна быть в формате YYYY-MM-DD"
        ),
    )


def check_debt_period_consistency(
    db: Session,
) -> DQResult:
    rows = db.scalars(
        select(
            StgDocumentExtraction
        ).where(
            StgDocumentExtraction.debt_period_start.is_not(None),
            StgDocumentExtraction.debt_period_end.is_not(None),
        )
    ).all()

    failed_rows = 0

    for row in rows:
        if (
            not is_valid_iso_date(row.debt_period_start)
            or not is_valid_iso_date(row.debt_period_end)
        ):
            continue

        start = datetime.strptime(
            row.debt_period_start,
            "%Y-%m-%d",
        )

        end = datetime.strptime(
            row.debt_period_end,
            "%Y-%m-%d",
        )

        if start > end:
            failed_rows += 1

    return DQResult(
        check_name="invalid_debt_period",
        passed=failed_rows == 0,
        failed_rows=failed_rows,
        description=(
            "Начало периода задолженности "
            "не может быть позже окончания"
        ),
    )


def check_missing_case_number(
    db: Session,
) -> DQResult:
    failed_rows = db.scalar(
        select(
            func.count(
                StgDocumentExtraction.id
            )
        ).where(
            StgDocumentExtraction.processing_status
            == "ok",
            StgDocumentExtraction.case_number.is_(None),
        )
    ) or 0

    return DQResult(
        check_name="missing_case_number",
        passed=failed_rows == 0,
        failed_rows=failed_rows,
        description=(
            "У успешно обработанного документа "
            "должен быть номер дела"
        ),
    )

def run_data_quality_checks(
    db: Session,
) -> list[DQResult]:
    checks = [
        check_duplicate_file_hashes,
        check_invalid_document_statuses,
        check_processed_documents_without_type,
        check_negative_amounts,
        check_invalid_processing_statuses,
        check_duplicate_processing_attempts,
        check_negative_event_duration,
        check_errors_without_message,
        check_invalid_inn,
        check_invalid_snils,
        check_invalid_dates,
        check_debt_period_consistency,
        check_missing_case_number,
    ]

    return [
        check(db)
        for check in checks
    ]