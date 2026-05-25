import pytest

from email_agent.models import Email, TriageResult
from email_agent.state import StateRepository


def _email() -> Email:
    return Email(message_id="m1", thread_id="t1", sender="a@b.com", subject="Hi")


@pytest.mark.asyncio
async def test_idempotency_and_skip(session):
    repo = StateRepository(session)
    assert await repo.already_processed("m1") is False

    await repo.record_skip(_email(), source="prefilter", reason="bulk")
    assert await repo.already_processed("m1") is True

    row = await repo.get("m1")
    assert row.status == "skipped"
    assert row.skip_source == "prefilter"


@pytest.mark.asyncio
async def test_record_drafted_and_needs_attention(session):
    repo = StateRepository(session)
    await repo.record_drafted(
        _email(), draft_id="d1", triage=TriageResult(should_reply=True, reason="real")
    )
    row = await repo.get("m1")
    assert row.status == "drafted"
    assert row.draft_id == "d1"

    await repo.set_needs_attention("m2", error="boom")
    row2 = await repo.get("m2")
    assert row2.status == "needs_attention"
    assert "boom" in row2.error
