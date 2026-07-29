from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.conversations.models import Conversation, Message


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (
        CheckConstraint("rating IN ('up', 'down')", name="feedback_rating_check"),
        CheckConstraint(
            "reason IS NULL OR reason IN "
            "('reasonWrongData', 'reasonIncomplete', 'reasonMisunderstood', 'reasonOther')",
            name="feedback_reason_check",
        ),
        CheckConstraint(
            "rating = 'up' OR reason IS NOT NULL",
            name="feedback_down_reason_check",
        ),
        Index("idx_feedback_message_id", "message_id"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    message_id: Mapped[UUID] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"))
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    user_id: Mapped[UUID]
    role: Mapped[str] = mapped_column(String)
    rating: Mapped[str] = mapped_column(String)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    message: Mapped["Message"] = relationship(back_populates="feedback")
    conversation: Mapped["Conversation"] = relationship(back_populates="feedback")
