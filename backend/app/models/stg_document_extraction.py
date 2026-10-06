from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.document import Document


class StgDocumentExtraction(Base):
    __tablename__ = "stg_document_extractions"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id"),
        nullable=False,
        index=True,
    )

    # Номер попытки обработки документа.
    # При retry можно будет хранить несколько результатов.
    attempt: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    # ========================================
    # Основные реквизиты документа
    # ========================================

    document_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    case_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    case_date: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    debt_period_start: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    debt_period_end: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    # ========================================
    # Должник
    # ========================================

    full_name: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    birth_date: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    passport: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    snils: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    inn: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    street: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    house: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    apartment: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    # ========================================
    # Суммы
    # ========================================

    principal_debt: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    penalty_amount: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    state_duty: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    postal_cost: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    # ========================================
    # Результат обработки
    # ========================================

    processing_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="processed",
    )

    missing_fields: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    warnings: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    # Полный исходный ответ processing pipeline.
    # Нужен для трассировки и повторной обработки.
    raw_result: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    # ========================================
    # Metadata / lineage
    # ========================================

    model_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    processor_version: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    processed_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    document: Mapped["Document"] = relationship()