"""Simplify tool_requests status to draft/posted/live — no staging, no
promote/fulfill ceremony. Superseded design; see 0004's original
draft/posted/staging/live shape."""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("tool_requests_status_check", "tool_requests", type_="check")
    op.create_check_constraint(
        "tool_requests_status_check",
        "tool_requests",
        "status IN ('draft', 'posted', 'live')",
    )


def downgrade() -> None:
    op.drop_constraint("tool_requests_status_check", "tool_requests", type_="check")
    op.create_check_constraint(
        "tool_requests_status_check",
        "tool_requests",
        "status IN ('draft', 'posted', 'staging', 'live')",
    )
