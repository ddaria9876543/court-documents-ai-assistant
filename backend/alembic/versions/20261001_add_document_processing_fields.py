"""add document processing fields

Revision ID: 20261001_add_doc_fields
Revises: cf759a92580c
Create Date: 2026-10-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261001_add_doc_fields"
down_revision: Union[str, Sequence[str], None] = "cf759a92580c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "case_number",
            sa.String(length=100),
            nullable=True,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "summary",
            sa.Text(),
            nullable=True,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "debtor",
            sa.Text(),
            nullable=True,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "amount",
            sa.Float(),
            nullable=True,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "needs_review",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "review_reason",
            sa.Text(),
            nullable=True,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "extracted_data",
            sa.JSON(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "documents",
        "extracted_data",
    )

    op.drop_column(
        "documents",
        "review_reason",
    )

    op.drop_column(
        "documents",
        "needs_review",
    )

    op.drop_column(
        "documents",
        "amount",
    )

    op.drop_column(
        "documents",
        "debtor",
    )

    op.drop_column(
        "documents",
        "summary",
    )

    op.drop_column(
        "documents",
        "case_number",
    )