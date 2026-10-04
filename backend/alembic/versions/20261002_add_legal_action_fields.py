"""add legal action fields

Revision ID: 20261002_add_legal_action_fields
Revises: 20261001_add_doc_fields
Create Date: 2026-10-02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261002_add_legal_action_fields"
down_revision: Union[str, Sequence[str], None] = "20261001_add_doc_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "requires_legal_action",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "legal_action_reason",
            sa.Text(),
            nullable=True,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "evidence_fragment",
            sa.Text(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "documents",
        "evidence_fragment",
    )

    op.drop_column(
        "documents",
        "legal_action_reason",
    )

    op.drop_column(
        "documents",
        "requires_legal_action",
    )