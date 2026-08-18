from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


# Permintaan tool adalah data bisnis; ia tidak otomatis mengaktifkan tool untuk model AI.
class ToolRequest(Base):
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
    status: Mapped[str] = mapped_column(String, default="draft", server_default=text("'draft'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
