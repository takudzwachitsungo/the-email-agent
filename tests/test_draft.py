import pytest

from email_agent.draft import write
from email_agent.memory import NullMemory
from email_agent.models import Email

CFG = {"persona": {"name": "Tk", "sign_off": "Best,\nTk", "tone": "warm"}}


def _email():
    return Email(message_id="m", thread_id="t", sender="jane@example.com",
                 subject="Tuesday?", body="Are we still on for Tuesday?")


@pytest.mark.asyncio
async def test_write_passes_persona_and_email_and_returns_text():
    captured = {}

    async def fake_provider(system, user, *, model, json_mode=False):
        captured["system"] = system
        captured["user"] = user
        return "Hi Jane,\n\nYes, Tuesday works.\n\nBest,\nTk"

    out = await write(_email(), thread=[], memory=NullMemory(),
                      provider=fake_provider, cfg=CFG, model="m")
    assert "Tuesday" in out
    assert "Tk" in captured["system"]          # persona injected into system prompt
    assert "Are we still on" in captured["user"]  # email body fenced into user msg


def test_draft_prompt_guides_descriptive_placeholders():
    from email_agent.draft import _build_system
    from email_agent.memory import NullMemory
    system = _build_system(CFG, NullMemory())
    assert "square brackets" in system
    assert "[confirm the exact time]" in system  # a concrete, descriptive example
