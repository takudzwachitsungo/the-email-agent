from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from email_agent.db import Base
from email_agent.models import Email, TriageResult


class ProcessedMessage(Base):
    __tablename__ = "processed_messages"

    message_id: Mapped[str] = mapped_column(primary_key=True)
    thread_id: Mapped[str | None] = mapped_column(default=None)
    sender: Mapped[str | None] = mapped_column(default=None)
    subject: Mapped[str | None] = mapped_column(default=None)
    triage_decision: Mapped[str | None] = mapped_column(default=None)
    triage_reason: Mapped[str | None] = mapped_column(default=None)
    skip_source: Mapped[str | None] = mapped_column(default=None)
    draft_id: Mapped[str | None] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(default="pending")
    error: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class StateRepository:
    """All reads/writes for the processed_messages table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def already_processed(self, message_id: str) -> bool:
        return (await self.get(message_id)) is not None

    async def get(self, message_id: str) -> ProcessedMessage | None:
        return await self.session.get(ProcessedMessage, message_id)

    async def _upsert(self, message_id: str, **fields) -> None:
        row = await self.get(message_id)
        if row is None:
            row = ProcessedMessage(message_id=message_id)
            self.session.add(row)
        for key, value in fields.items():
            setattr(row, key, value)
        row.updated_at = datetime.now(timezone.utc)
        await self.session.commit()

    async def record_skip(self, email: Email, *, source: str, reason: str) -> None:
        await self._upsert(
            email.message_id,
            thread_id=email.thread_id,
            sender=email.sender,
            subject=email.subject,
            triage_decision="skip",
            triage_reason=reason,
            skip_source=source,
            status="skipped",
        )

    async def record_drafted(self, email: Email, *, draft_id: str, triage: TriageResult) -> None:
        await self._upsert(
            email.message_id,
            thread_id=email.thread_id,
            sender=email.sender,
            subject=email.subject,
            triage_decision="reply",
            triage_reason=triage.reason,
            draft_id=draft_id,
            status="drafted",
        )

    async def set_needs_attention(self, message_id: str, *, error: str) -> None:
        await self._upsert(message_id, status="needs_attention", error=error)
