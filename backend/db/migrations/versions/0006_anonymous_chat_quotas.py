"""Persist anonymous chat usage independently of the search cache.

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "anonymous_chat_quotas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("identity", sa.String(64), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("resets_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("identity"),
    )


def downgrade() -> None:
    op.drop_table("anonymous_chat_quotas")
