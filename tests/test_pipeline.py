import pytest

from email_agent.models import Email, TriageResult
from email_agent.pipeline import process_message


class FakeGmail:
    def __init__(self, email):
        self._email = email
        self.created = []

    async def get_message(self, mid):
        return self._email

    async def fetch_thread(self, tid):
        return []

    async def create_draft(self, *, to, subject, body, thread_id):
        self.created.append(body)
        return "draft-123"


class FakeState:
    def __init__(self, seen=()):
        self.seen = set(seen)
        self.skips = []
        self.drafts = []
        self.attention = []

    async def already_processed(self, mid):
        return mid in self.seen

    async def record_skip(self, email, *, source, reason):
        self.skips.append((email.message_id, source, reason))

    async def record_drafted(self, email, *, draft_id, triage):
        self.drafts.append((email.message_id, draft_id))

    async def set_needs_attention(self, mid, *, error):
        self.attention.append((mid, error))


def _email(**kw):
    base = dict(message_id="m1", thread_id="t1", sender="jane@example.com",
                subject="Q", body="Can you send it?")
    base.update(kw)
    return Email(**base)


CFG = {"prefilter": {"deny_sender_substrings": ["no-reply"]}, "persona": {"name": "Tk"},
       "triage": {"surface_when_unsure": True}}


@pytest.mark.asyncio
async def test_idempotent_skip_when_already_processed():
    state = FakeState(seen={"m1"})
    gmail = FakeGmail(_email())
    await process_message("m1", gmail=gmail, state=state, provider=None,
                          memory=None, cfg=CFG, dry_run=False,
                          triage_model="t", draft_model="d")
    assert state.skips == [] and state.drafts == []  # nothing happened


@pytest.mark.asyncio
async def test_prefilter_skip_records_skip_and_no_llm():
    state = FakeState()
    gmail = FakeGmail(_email(sender="no-reply@x.com"))
    await process_message("m1", gmail=gmail, state=state, provider=None,
                          memory=None, cfg=CFG, dry_run=False,
                          triage_model="t", draft_model="d")
    assert state.skips[0][1] == "prefilter"
    assert gmail.created == []


@pytest.mark.asyncio
async def test_full_path_creates_draft():
    state = FakeState()
    gmail = FakeGmail(_email())

    async def provider(system, user, *, model, json_mode=False):
        if json_mode:
            return '{"should_reply": true, "category": "request", "reason": "asks"}'
        return "Hi Jane,\n\nSending now.\n\nBest,\nTk"

    from email_agent.memory import NullMemory
    await process_message("m1", gmail=gmail, state=state, provider=provider,
                          memory=NullMemory(), cfg=CFG, dry_run=False,
                          triage_model="t", draft_model="d")
    assert gmail.created and "Jane" in gmail.created[0]
    assert state.drafts == [("m1", "draft-123")]


@pytest.mark.asyncio
async def test_dry_run_creates_no_draft():
    state = FakeState()
    gmail = FakeGmail(_email())

    async def provider(system, user, *, model, json_mode=False):
        return '{"should_reply": true, "category": "request", "reason": "x"}' if json_mode else "body"

    from email_agent.memory import NullMemory
    await process_message("m1", gmail=gmail, state=state, provider=provider,
                          memory=NullMemory(), cfg=CFG, dry_run=True,
                          triage_model="t", draft_model="d")
    assert gmail.created == []           # no draft in dry-run
    assert state.drafts == []


@pytest.mark.asyncio
async def test_error_sets_needs_attention():
    state = FakeState()

    class BoomGmail(FakeGmail):
        async def get_message(self, mid):
            raise RuntimeError("api down")

    await process_message("m1", gmail=BoomGmail(_email()), state=state, provider=None,
                          memory=None, cfg=CFG, dry_run=False,
                          triage_model="t", draft_model="d")
    assert state.attention and state.attention[0][0] == "m1"
