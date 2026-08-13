from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ToolCallLog(Base):
    __tablename__ = "tool_call_logs"
    __table_args__ = (Index("idx_tool_call_logs_conversation_id", "conversation_id"),)

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    conversation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("conversations.id"), nullable=True
    )
    message_id: Mapped[UUID | None] = mapped_column(nullable=True)
    tool_name: Mapped[str] = mapped_column(Text)
    tool_input: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(Text)
    duration_ms: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    user_id: Mapped[UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
