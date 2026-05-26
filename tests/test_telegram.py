import pytest

from email_agent import telegram_bot as tb


def test_approval_keyboard_has_three_buttons():
    kb = tb.approval_keyboard("m1")
    row = kb["inline_keyboard"][0]
    datas = [b["callback_data"] for b in row]
    assert datas == ["approve:m1", "edit:m1", "skip:m1"]


def test_send_keyboard_has_send_cancel():
    kb = tb.send_keyboard("m1")
    datas = [b["callback_data"] for b in kb["inline_keyboard"][0]]
    assert datas == ["send:m1", "cancel:m1"]


def test_format_card_includes_sender_subject_body():
    text = tb.format_card(sender="jane@x.com", subject="Tuesday?", body="See you then")
    assert "jane@x.com" in text and "Tuesday?" in text and "See you then" in text


@pytest.mark.asyncio
async def test_send_approval_builds_payload(monkeypatch):
    client = tb.TelegramClient(token="t", chat_id="42")
    calls = []

    async def fake_call(method, payload):
        calls.append((method, payload))
        return {"message_id": 987}

    monkeypatch.setattr(client, "_call", fake_call)
    tg_id = await client.send_approval(sender="a@b.com", subject="hi", body="yo", message_id="m1")
    assert tg_id == "987"
    method, payload = calls[0]
    assert method == "sendMessage"
    assert payload["chat_id"] == "42"
    assert payload["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == "approve:m1"
