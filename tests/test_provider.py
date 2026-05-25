import pytest

from email_agent import provider


class _FakeMessage:
    def __init__(self, content):
        self.message = type("M", (), {"content": content})


class _FakeCompletions:
    def __init__(self, content):
        self._content = content
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return type("R", (), {"choices": [_FakeMessage(self._content)]})


class _FakeClient:
    def __init__(self, content):
        self.chat = type("C", (), {"completions": _FakeCompletions(content)})


@pytest.mark.asyncio
async def test_complete_returns_text_and_passes_messages(monkeypatch):
    fake = _FakeClient("hello world")
    monkeypatch.setattr(provider, "_client", lambda: fake)

    out = await provider.complete("SYS", "USER", model="m1")
    assert out == "hello world"
    sent = fake.chat.completions.calls[0]
    assert sent["model"] == "m1"
    assert sent["messages"][0] == {"role": "system", "content": "SYS"}
    assert sent["messages"][1] == {"role": "user", "content": "USER"}


@pytest.mark.asyncio
async def test_complete_json_mode_sets_response_format(monkeypatch):
    fake = _FakeClient("{}")
    monkeypatch.setattr(provider, "_client", lambda: fake)
    await provider.complete("S", "U", model="m1", json_mode=True)
    sent = fake.chat.completions.calls[0]
    assert sent["response_format"] == {"type": "json_object"}
