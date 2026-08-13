"""Tool call logs — persistent, queryable complement to the structlog
tool_completed event, not a replacement for it."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tool_call_logs",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("message_id", sa.Uuid(), nullable=True),
        sa.Column("tool_name", sa.Text(), nullable=False),
        sa.Column("tool_input", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("duration_ms", sa.Numeric(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_tool_call_logs_conversation_id", "tool_call_logs", ["conversation_id"]
    )


def downgrade() -> None:
    op.drop_table("tool_call_logs")
