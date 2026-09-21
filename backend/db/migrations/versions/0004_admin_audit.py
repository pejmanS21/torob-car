"""add the admin audit trail

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ADMIN_ACTION = sa.Enum(
    "user_disabled",
    "user_enabled",
    "user_promoted",
    "user_demoted",
    "user_password_reset",
    "user_deleted",
    name="adminaction",
    native_enum=False,
    length=32,
)


def upgrade() -> None:
    op.create_table(
        "admin_audit",
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("actor_email", sa.String(length=320), nullable=False),
        sa.Column("action", _ADMIN_ACTION, nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=True),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_admin_audit_actor_id"), "admin_audit", ["actor_id"])
    op.create_index(op.f("ix_admin_audit_action"), "admin_audit", ["action"])
    op.create_index(op.f("ix_admin_audit_created_at"), "admin_audit", ["created_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_admin_audit_created_at"), table_name="admin_audit")
    op.drop_index(op.f("ix_admin_audit_action"), table_name="admin_audit")
    op.drop_index(op.f("ix_admin_audit_actor_id"), table_name="admin_audit")
    op.drop_table("admin_audit")
