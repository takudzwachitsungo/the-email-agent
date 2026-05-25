import pytest

from email_agent.models import Email
from email_agent.triage import classify

CFG = {"triage": {"surface_when_unsure": True}}


def _email():
    return Email(message_id="m", thread_id="t", sender="a@b.com",
                 subject="Q", body="Can you send the report?")


async def _fake_provider_ok(system, user, *, model, json_mode=False):
    return '{"should_reply": true, "category": "request", "reason": "asks for report"}'


async def _fake_provider_garbage(system, user, *, model, json_mode=False):
    return "not json at all"


@pytest.mark.asyncio
async def test_classify_parses_valid_json():
    result = await classify(_email(), provider=_fake_provider_ok, cfg=CFG, model="m")
    assert result.should_reply is True
    assert result.category == "request"


@pytest.mark.asyncio
async def test_classify_surfaces_on_unparseable_output():
    # surface_when_unsure=True -> default to should_reply when JSON is bad
    result = await classify(_email(), provider=_fake_provider_garbage, cfg=CFG, model="m")
    assert result.should_reply is True
    assert "unparseable" in result.reason.lower()
