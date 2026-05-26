import json
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from email_agent.approval import ApprovalListener

FIX = Path(__file__).parent / "fixtures"


class FakeTelegram:
    def __init__(self):
        self.edits = []
        self.messages = []
        self.answered = []

    async def answer_callback(self, callback_id, text=""):
        self.answered.append(callback_id)

    async def edit_message(self, message_id, text):
        self.edits.append((message_id, text))

    async def send_message(self, text, *, reply_markup=None):
        self.messages.append((text, reply_markup))
        return "900"


class FakeGmail:
    def __init__(self):
        self.sent = []
        self.deleted = []
        self.updated = []

    async def send_draft(self, draft_id):
        self.sent.append(draft_id)

    async def delete_draft(self, draft_id):
        self.deleted.append(draft_id)

    async def update_draft(self, *, draft_id, to, subject, body, thread_id):
        self.updated.append((draft_id, body))


class Row:
    def __init__(self):
        self.draft_id = "d1"
        self.status = "pending"
        self.tg_message_id = "555"
        self.sender = "jane@x.com"
        self.subject = "Tuesday?"
        self.thread_id = "t1"


class FakeState:
    def __init__(self, row=None):
        self._row = row if row is not None else Row()
        self.sent = []
        self.rejected = []

    async def get(self, mid):
        return self._row

    async def set_sent(self, mid):
        self.sent.append(mid)
        if self._row:
            self._row.status = "sent"

    async def set_rejected(self, mid):
        self.rejected.append(mid)
        if self._row:
            self._row.status = "rejected"


def _listener(tg, gmail, state, chat_id="42"):
    @asynccontextmanager
    async def repo_factory():
        yield state
    return ApprovalListener(telegram=tg, gmail=gmail, repo_factory=repo_factory, chat_id=chat_id)


@pytest.mark.asyncio
async def test_approve_sends_and_marks_sent():
    tg, gmail, state = FakeTelegram(), FakeGmail(), FakeState()
    listener = _listener(tg, gmail, state)
    await listener.handle_update(json.loads((FIX / "tg_callback.json").read_text()))
    assert gmail.sent == ["d1"]
    assert state.sent == ["m1"]
    assert tg.edits and "Sent" in tg.edits[-1][1]


@pytest.mark.asyncio
async def test_skip_deletes_and_rejects():
    tg, gmail, state = FakeTelegram(), FakeGmail(), FakeState()
    update = json.loads((FIX / "tg_callback.json").read_text())
    update["callback_query"]["data"] = "skip:m1"
    listener = _listener(tg, gmail, state)
    await listener.handle_update(update)
    assert gmail.deleted == ["d1"]
    assert state.rejected == ["m1"]


@pytest.mark.asyncio
async def test_edit_flow_prompt_then_apply_then_send():
    tg, gmail, state = FakeTelegram(), FakeGmail(), FakeState()
    listener = _listener(tg, gmail, state)

    edit_cb = json.loads((FIX / "tg_callback.json").read_text())
    edit_cb["callback_query"]["data"] = "edit:m1"
    await listener.handle_update(edit_cb)
    assert listener.awaiting_edit.get("42") == "m1"
    assert tg.messages  # prompted for new text

    await listener.handle_update(json.loads((FIX / "tg_message.json").read_text()))
    assert gmail.updated and gmail.updated[0][1] == "My revised reply."
    assert tg.messages[-1][1]["inline_keyboard"][0][0]["callback_data"] == "send:m1"

    send_cb = json.loads((FIX / "tg_callback.json").read_text())
    send_cb["callback_query"]["data"] = "send:m1"
    await listener.handle_update(send_cb)
    assert gmail.sent == ["d1"]
    assert state.sent == ["m1"]


@pytest.mark.asyncio
async def test_foreign_chat_is_ignored():
    tg, gmail, state = FakeTelegram(), FakeGmail(), FakeState()
    listener = _listener(tg, gmail, state, chat_id="999")
    await listener.handle_update(json.loads((FIX / "tg_callback.json").read_text()))
    assert gmail.sent == [] and state.sent == [] and tg.edits == []


@pytest.mark.asyncio
async def test_already_actioned_is_not_resent():
    row = Row()
    row.status = "sent"
    tg, gmail, state = FakeTelegram(), FakeGmail(), FakeState(row=row)
    listener = _listener(tg, gmail, state)
    await listener.handle_update(json.loads((FIX / "tg_callback.json").read_text()))
    assert gmail.sent == []
