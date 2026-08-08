"""Rolling conversation summaries and background jobs."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("rolling_summary", sa.Text(), nullable=True))
    op.add_column(
        "conversations",
        sa.Column(
            "summarized_through_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_table(
        "background_jobs",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("job_type", sa.String(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "status", sa.String(), nullable=False, server_default=sa.text("'pending'")
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'done', 'failed')",
            name="background_jobs_status_check",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_background_jobs_status_created_at", "background_jobs", ["status", "created_at"]
    )
    op.create_index(
        "idx_background_jobs_pending_dedup",
        "background_jobs",
        ["job_type", sa.text("(payload->>'conversation_id')")],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_table("background_jobs")
    op.drop_column("conversations", "summarized_through_count")
    op.drop_column("conversations", "rolling_summary")
