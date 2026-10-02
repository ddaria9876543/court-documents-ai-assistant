from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.document_file import DocumentFile
    from app.models.document_history import DocumentHistory


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="new"
    )

    document_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    case_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    debtor: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    amount: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    # ========================================
    # Техническая ручная проверка
    # ========================================

    needs_review: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )

    review_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # ========================================
    # Юридическая маршрутизация
    # ========================================

    # Требует ли содержание акта действий юриста.
    # Не путать с needs_review:
    # needs_review = техническая проблема распознавания/извлечения.
    requires_legal_action: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )

    # Причина передачи документа юристу.
    legal_action_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # Фрагмент документа,
    # подтверждающий необходимость действий.
    evidence_fragment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    extracted_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    files: Mapped[list["DocumentFile"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan"
    )

    history: Mapped[list["DocumentHistory"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan"
    )