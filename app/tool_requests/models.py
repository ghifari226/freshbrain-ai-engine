from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ToolRequest(Base):
    """PostgreSQL-owned record of demand for a new (or changed) tool
    capability. Deliberately separate from the Live Tool Catalog
    (app/chat/tools.py), which is code-owned — a request reaching `live`
    only records that it's been fulfilled; it never creates the capability
    itself. See project_ai_engine_build_order memory for the full
    source-of-truth split."""

    __tablename__ = "tool_requests"
    __table_args__ = (Index("idx_tool_requests_user_id", "user_id", text("created_at DESC")),)

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(index=False)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text)
    domain: Mapped[str] = mapped_column(String)
    # draft/posted/live — a plain field, not a state machine. No staging
    # state, no promote/fulfill actions; ToolRequestService.set_status()
    # can move it to any of the three directly. Content is frozen once
    # live (see update_content()), but reaching live isn't gated on any
    # prior status. Unrelated to the Live Tool Catalog's own
    # staging/production deploy status for the eventual tool (a separate,
    # code-owned concept, see app/chat/tools.py).
    status: Mapped[str] = mapped_column(String, default="draft", server_default=text("'draft'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
