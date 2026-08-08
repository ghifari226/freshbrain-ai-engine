"""Tool requests (PostgreSQL-owned demand pipeline, separate from the
code-owned Live Tool Catalog)."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tool_requests",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("domain", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default=sa.text("'draft'")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'posted', 'staging', 'live')",
            name="tool_requests_status_check",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_tool_requests_user_id", "tool_requests", ["user_id", sa.text("created_at DESC")]
    )


def downgrade() -> None:
    op.drop_table("tool_requests")
