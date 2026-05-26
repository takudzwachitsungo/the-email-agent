# Email Agent — Phase 2 (Telegram Approval Gate) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the pipeline creates a reply draft, notify the owner on Telegram with the proposed text and inline Approve / Edit / Skip buttons; Approve sends the Gmail draft, Skip deletes it, Edit rewrites it in-chat then sends after a confirm — all in the existing single FastAPI process via long-polling.

**Architecture:** Two new focused modules: `telegram_bot.py` (raw-httpx transport + approval-card formatting) and `approval.py` (a long-poll listener that routes button taps / edit replies to Gmail actions + state transitions). The pipeline gains an optional `telegram` collaborator; when present (and not dry-run) it sends an approval card and marks the row `pending` instead of terminal `drafted`. A second background task in the FastAPI lifespan runs the listener. Behind `TELEGRAM_ENABLED=false` the system behaves exactly as Phase 1.

**Tech Stack:** Same as Phase 1 (Python 3.11+, uv, FastAPI, SQLAlchemy async + asyncpg + Alembic, Pydantic, httpx, pytest). Telegram Bot API accessed directly via `httpx` — no bot framework.

**Design reference:** [docs/superpowers/specs/2026-05-26-email-agent-phase2-telegram-design.md](../specs/2026-05-26-email-agent-phase2-telegram-design.md).

---

## Conventions (carried from Phase 1)

- Run tools with the project venv: `.venv/Scripts/python.exe -m pytest ...` (uv installed everything into `.venv`; `python -m uv run` is unreliable on this machine).
- DB-backed tests use the dedicated `email_agent_test` database (see `tests/conftest.py`).
- Commits author as `takudzwa`; append the `Co-Authored-By` trailer.
- Async everywhere; the Google client is sync and wrapped in `asyncio.to_thread` inside `gmail_client.py`.

## File structure (Phase 2 additions/changes)

```
src/email_agent/
├── config.py            # + telegram_bot_token, telegram_chat_id, telegram_enabled
├── state.py             # + tg_message_id column; set_pending / set_sent / set_rejected
├── gmail_client.py      # + send_draft / delete_draft / update_draft
├── telegram_bot.py      # NEW: TelegramClient (httpx) + format_card / keyboards
├── approval.py          # NEW: ApprovalListener (getUpdates loop + routing)
├── pipeline.py          # notify + set pending when a telegram client is passed
└── app.py               # start the approval listener in the lifespan
alembic/versions/
└── 0002_tg_message_id.py   # NEW migration
tests/
├── test_telegram.py     # NEW
├── test_approval.py     # NEW
└── fixtures/
    ├── tg_callback.json  # NEW
    └── tg_message.json   # NEW
```

---

## Task 1: Telegram settings

**Files:**
- Modify: `src/email_agent/config.py`
- Test: `tests/test_config.py` (add a test)

- [ ] **Step 1: Add the failing test**

Append to `tests/test_config.py`:
```python
def test_settings_telegram_fields(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "55555")
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    s = Settings()
    assert s.telegram_bot_token == "123:abc"
    assert s.telegram_chat_id == "55555"
    assert s.telegram_enabled is True


def test_settings_telegram_defaults_off():
    s = Settings()
    assert s.telegram_enabled is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_config.py -q`
Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'telegram_bot_token'`

- [ ] **Step 3: Add the fields to `Settings`**

In `src/email_agent/config.py`, inside `class Settings`, after `log_level`:
```python
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_enabled: bool = False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_config.py -q`
Expected: PASS

- [ ] **Step 5: Update `.env.example`**

Append to `.env.example`:
```dotenv
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
TELEGRAM_ENABLED=false
```

- [ ] **Step 6: Commit**

```bash
git add src/email_agent/config.py tests/test_config.py .env.example
git commit -m "feat: telegram settings (token, chat id, enabled flag)"
```

---

## Task 2: State — `tg_message_id` column + pending/sent/rejected transitions

**Files:**
- Modify: `src/email_agent/state.py`
- Create: `alembic/versions/0002_tg_message_id.py`
- Test: `tests/test_state.py` (add tests)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_state.py`:
```python
@pytest.mark.asyncio
async def test_pending_then_sent(session):
    repo = StateRepository(session)
    await repo.set_pending(
        _email(), draft_id="d1", tg_message_id="tg99",
        triage=TriageResult(should_reply=True, reason="real"),
    )
    row = await repo.get("m1")
    assert row.status == "pending"
    assert row.draft_id == "d1"
    assert row.tg_message_id == "tg99"

    await repo.set_sent("m1")
    assert (await repo.get("m1")).status == "sent"


@pytest.mark.asyncio
async def test_pending_then_rejected(session):
    repo = StateRepository(session)
    await repo.set_pending(
        _email(), draft_id="d1", tg_message_id="tg99",
        triage=TriageResult(should_reply=True, reason="real"),
    )
    await repo.set_rejected("m1")
    assert (await repo.get("m1")).status == "rejected"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_state.py -q`
Expected: FAIL (`AttributeError: 'StateRepository' object has no attribute 'set_pending'`)

- [ ] **Step 3: Add the column and methods**

In `src/email_agent/state.py`, add the column to `ProcessedMessage` (after `draft_id`):
```python
    tg_message_id: Mapped[str | None] = mapped_column(default=None)
```

Add these methods to `StateRepository` (after `record_drafted`):
```python
    async def set_pending(self, email: Email, *, draft_id: str, tg_message_id: str | None,
                          triage: TriageResult) -> None:
        await self._upsert(
            email.message_id,
            thread_id=email.thread_id,
            sender=email.sender,
            subject=email.subject,
            triage_decision="reply",
            triage_reason=triage.reason,
            draft_id=draft_id,
            tg_message_id=tg_message_id,
            status="pending",
        )

    async def set_sent(self, message_id: str) -> None:
        await self._upsert(message_id, status="sent")

    async def set_rejected(self, message_id: str) -> None:
        await self._upsert(message_id, status="rejected")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose up -d db && .venv/Scripts/python.exe -m pytest tests/test_state.py -q`
Expected: PASS

- [ ] **Step 5: Write migration `0002`**

`alembic/versions/0002_tg_message_id.py`:
```python
"""add tg_message_id to processed_messages

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-26
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("processed_messages", sa.Column("tg_message_id", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("processed_messages", "tg_message_id")
```

- [ ] **Step 6: Apply the migration to the app DB**

Run:
```bash
DATABASE_URL=postgresql+asyncpg://agent:agent@localhost:5432/email_agent .venv/Scripts/alembic.exe upgrade head
```
Expected: `Running upgrade 0001 -> 0002`. Verify:
```bash
docker compose exec -T db psql -U agent -d email_agent -c "\d processed_messages" | grep tg_message_id
```
Expected: shows the `tg_message_id` column.

- [ ] **Step 7: Commit**

```bash
git add src/email_agent/state.py alembic/versions/0002_tg_message_id.py tests/test_state.py
git commit -m "feat: state pending/sent/rejected + tg_message_id (migration 0002)"
```

---

## Task 3: Gmail — send / delete / update draft

**Files:**
- Modify: `src/email_agent/gmail_client.py`
- Test: `tests/test_gmail_client.py` (add tests)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_gmail_client.py` (extend the fake service to record draft ops):
```python
class _Drafts:
    def __init__(self):
        self.sent = []
        self.deleted = []
        self.updated = []

    def send(self, userId, body):
        self.sent.append(body)
        return _Exec({"id": body.get("id"), "labelIds": ["SENT"]})

    def delete(self, userId, id):
        self.deleted.append(id)
        return _Exec("")

    def update(self, userId, id, body):
        self.updated.append((id, body))
        return _Exec({"id": id})


def _service_with_drafts():
    svc = _FakeService({})
    drafts = _Drafts()
    svc._users._drafts = drafts
    svc._users.drafts = lambda: drafts
    return svc, drafts


@pytest.mark.asyncio
async def test_send_draft_calls_api():
    svc, drafts = _service_with_drafts()
    client = GmailClient(service=svc)
    await client.send_draft("d1")
    assert drafts.sent == [{"id": "d1"}]


@pytest.mark.asyncio
async def test_delete_draft_calls_api():
    svc, drafts = _service_with_drafts()
    client = GmailClient(service=svc)
    await client.delete_draft("d1")
    assert drafts.deleted == ["d1"]


@pytest.mark.asyncio
async def test_update_draft_calls_api():
    svc, drafts = _service_with_drafts()
    client = GmailClient(service=svc)
    await client.update_draft(draft_id="d1", to="a@b.com", subject="Re: hi",
                              body="hello", thread_id="t1")
    assert drafts.updated[0][0] == "d1"
    assert "message" in drafts.updated[0][1]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_gmail_client.py -q`
Expected: FAIL (`AttributeError: 'GmailClient' object has no attribute 'send_draft'`)

- [ ] **Step 3: Implement the three methods**

In `src/email_agent/gmail_client.py`, add to `class GmailClient` (after `create_draft`):
```python
    async def send_draft(self, draft_id: str) -> None:
        def _call():
            self.service.users().drafts().send(userId="me", body={"id": draft_id}).execute()

        await asyncio.to_thread(_call)

    async def delete_draft(self, draft_id: str) -> None:
        def _call():
            self.service.users().drafts().delete(userId="me", id=draft_id).execute()

        await asyncio.to_thread(_call)

    async def update_draft(self, *, draft_id: str, to: str, subject: str, body: str,
                           thread_id: str) -> None:
        def _call():
            mime = MIMEText(body)
            mime["To"] = to
            mime["Subject"] = subject
            raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
            self.service.users().drafts().update(
                userId="me", id=draft_id,
                body={"message": {"raw": raw, "threadId": thread_id}},
            ).execute()

        await asyncio.to_thread(_call)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_gmail_client.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/email_agent/gmail_client.py tests/test_gmail_client.py
git commit -m "feat: gmail send/delete/update draft"
```

---

## Task 4: Telegram transport + card formatting

**Files:**
- Create: `src/email_agent/telegram_bot.py`
- Test: `tests/test_telegram.py`

- [ ] **Step 1: Write the failing test**

`tests/test_telegram.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_telegram.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'email_agent.telegram_bot'`)

- [ ] **Step 3: Implement `telegram_bot.py`**

`src/email_agent/telegram_bot.py`:
```python
import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

_API = "https://api.telegram.org/bot{token}/{method}"
_RETRYABLE = (httpx.TransportError,)


def approval_keyboard(message_id: str) -> dict:
    return {"inline_keyboard": [[
        {"text": "Approve", "callback_data": f"approve:{message_id}"},
        {"text": "Edit", "callback_data": f"edit:{message_id}"},
        {"text": "Skip", "callback_data": f"skip:{message_id}"},
    ]]}


def send_keyboard(message_id: str) -> dict:
    return {"inline_keyboard": [[
        {"text": "Send", "callback_data": f"send:{message_id}"},
        {"text": "Cancel", "callback_data": f"cancel:{message_id}"},
    ]]}


def format_card(*, sender: str, subject: str, body: str) -> str:
    return (
        f"New draft reply\n\nFrom: {sender}\nSubject: {subject}\n\n"
        f"{body[:3500]}"
    )


class TelegramClient:
    def __init__(self, token: str, chat_id: str, http: httpx.AsyncClient | None = None) -> None:
        self.token = token
        self.chat_id = str(chat_id)
        self._http = http or httpx.AsyncClient(timeout=40.0)

    @retry(retry=retry_if_exception_type(_RETRYABLE),
           stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, max=20), reraise=True)
    async def _call(self, method: str, payload: dict) -> dict:
        resp = await self._http.post(_API.format(token=self.token, method=method), json=payload)
        resp.raise_for_status()
        return resp.json().get("result", {})

    async def send_approval(self, *, sender: str, subject: str, body: str, message_id: str) -> str:
        result = await self._call("sendMessage", {
            "chat_id": self.chat_id,
            "text": format_card(sender=sender, subject=subject, body=body),
            "reply_markup": approval_keyboard(message_id),
        })
        return str(result["message_id"])

    async def send_message(self, text: str, *, reply_markup: dict | None = None) -> str:
        payload = {"chat_id": self.chat_id, "text": text}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        result = await self._call("sendMessage", payload)
        return str(result.get("message_id", ""))

    async def edit_message(self, message_id: str, text: str) -> None:
        await self._call("editMessageText", {
            "chat_id": self.chat_id, "message_id": int(message_id), "text": text,
        })

    async def answer_callback(self, callback_id: str, text: str = "") -> None:
        await self._call("answerCallbackQuery", {"callback_query_id": callback_id, "text": text})

    async def get_updates(self, offset: int) -> list[dict]:
        result = await self._call("getUpdates", {"offset": offset, "timeout": 25})
        return result if isinstance(result, list) else []
```

> Note: `get_updates` uses `result` directly because `getUpdates` returns a list, not an object. `_call` returns `json()["result"]`, which is a list for that method.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_telegram.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/email_agent/telegram_bot.py tests/test_telegram.py
git commit -m "feat: telegram transport (httpx) + approval card / keyboards"
```

---

## Task 5: Approval listener (routing, edit flow, security)

**Files:**
- Create: `src/email_agent/approval.py`
- Create: `tests/fixtures/tg_callback.json`, `tests/fixtures/tg_message.json`
- Test: `tests/test_approval.py`

- [ ] **Step 1: Add Telegram update fixtures**

`tests/fixtures/tg_callback.json`:
```json
{
  "update_id": 1001,
  "callback_query": {
    "id": "cb1",
    "data": "approve:m1",
    "message": {"message_id": 555, "chat": {"id": 42}}
  }
}
```

`tests/fixtures/tg_message.json`:
```json
{
  "update_id": 1002,
  "message": {"message_id": 556, "chat": {"id": 42}, "text": "My revised reply."}
}
```

- [ ] **Step 2: Write the failing test**

`tests/test_approval.py`:
```python
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
    # preview message carries a Send/Cancel keyboard
    assert tg.messages[-1][1]["inline_keyboard"][0][0]["callback_data"] == "send:m1"

    send_cb = json.loads((FIX / "tg_callback.json").read_text())
    send_cb["callback_query"]["data"] = "send:m1"
    await listener.handle_update(send_cb)
    assert gmail.sent == ["d1"]
    assert state.sent == ["m1"]


@pytest.mark.asyncio
async def test_foreign_chat_is_ignored():
    tg, gmail, state = FakeTelegram(), FakeGmail(), FakeState()
    listener = _listener(tg, gmail, state, chat_id="999")  # bot expects 999, update is from 42
    await listener.handle_update(json.loads((FIX / "tg_callback.json").read_text()))
    assert gmail.sent == [] and state.sent == [] and tg.edits == []


@pytest.mark.asyncio
async def test_already_actioned_is_not_resent():
    row = Row(); row.status = "sent"
    tg, gmail, state = FakeTelegram(), FakeGmail(), FakeState(row=row)
    listener = _listener(tg, gmail, state)
    await listener.handle_update(json.loads((FIX / "tg_callback.json").read_text()))
    assert gmail.sent == []  # not pending -> no send
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_approval.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'email_agent.approval'`)

- [ ] **Step 4: Implement `approval.py`**

`src/email_agent/approval.py`:
```python
import asyncio
import logging

from email_agent.telegram_bot import send_keyboard

log = logging.getLogger(__name__)


class ApprovalListener:
    """Long-polls Telegram and routes taps / edit replies to Gmail + state."""

    def __init__(self, *, telegram, gmail, repo_factory, chat_id: str) -> None:
        self.telegram = telegram
        self.gmail = gmail
        self.repo_factory = repo_factory
        self.chat_id = str(chat_id)
        self.awaiting_edit: dict[str, str] = {}
        self._offset = 0
        self._stop = asyncio.Event()

    # ---- routing -------------------------------------------------------
    async def handle_update(self, update: dict) -> None:
        if "callback_query" in update:
            await self._handle_callback(update["callback_query"])
        elif "message" in update:
            await self._handle_message(update["message"])

    async def _handle_callback(self, cq: dict) -> None:
        chat_id = str(cq["message"]["chat"]["id"])
        if chat_id != self.chat_id:
            log.warning("ignoring callback from foreign chat %s", chat_id)
            return
        await self.telegram.answer_callback(cq["id"])
        action, _, mid = cq["data"].partition(":")
        card_id = str(cq["message"]["message_id"])
        if action == "approve":
            await self._finish(mid, card_id, "Sent.")
        elif action == "skip":
            await self._skip(mid, card_id)
        elif action == "edit":
            self.awaiting_edit[chat_id] = mid
            await self.telegram.send_message("Send me the revised reply text.")
        elif action == "send":
            await self._finish(mid, card_id, "Sent (edited).")
        elif action == "cancel":
            await self.telegram.edit_message(card_id, "Cancelled. Draft left in Gmail.")

    async def _handle_message(self, msg: dict) -> None:
        chat_id = str(msg["chat"]["id"])
        if chat_id != self.chat_id:
            return
        text = msg.get("text", "")
        mid = self.awaiting_edit.get(chat_id)
        if mid and text and not text.startswith("/"):
            self.awaiting_edit.pop(chat_id, None)
            await self._apply_edit(mid, text)

    # ---- actions -------------------------------------------------------
    async def _finish(self, mid: str, card_id: str, done_text: str) -> None:
        async with self.repo_factory() as state:
            row = await state.get(mid)
            if not row or row.status != "pending":
                await self.telegram.edit_message(card_id, "This draft is no longer pending.")
                return
            await self.gmail.send_draft(row.draft_id)
            await state.set_sent(mid)
        await self.telegram.edit_message(card_id, done_text)

    async def _skip(self, mid: str, card_id: str) -> None:
        async with self.repo_factory() as state:
            row = await state.get(mid)
            if not row or row.status != "pending":
                await self.telegram.edit_message(card_id, "This draft is no longer pending.")
                return
            await self.gmail.delete_draft(row.draft_id)
            await state.set_rejected(mid)
        await self.telegram.edit_message(card_id, "Skipped (draft deleted).")

    async def _apply_edit(self, mid: str, text: str) -> None:
        async with self.repo_factory() as state:
            row = await state.get(mid)
            if not row or row.status != "pending":
                await self.telegram.send_message("That draft is no longer pending.")
                return
            await self.gmail.update_draft(
                draft_id=row.draft_id, to=row.sender,
                subject=f"Re: {row.subject}", body=text, thread_id=row.thread_id,
            )
        await self.telegram.send_message(
            f"Updated draft. Send it?\n\n{text[:1000]}", reply_markup=send_keyboard(mid)
        )

    # ---- loop ----------------------------------------------------------
    async def run(self) -> None:
        log.info("telegram approval listener started")
        while not self._stop.is_set():
            try:
                updates = await self.telegram.get_updates(self._offset)
                for u in updates:
                    self._offset = u["update_id"] + 1
                    await self.handle_update(u)
            except Exception:
                log.exception("approval listener iteration failed")
                await asyncio.sleep(3)

    def stop(self) -> None:
        self._stop.set()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_approval.py -q`
Expected: PASS (5 passed)

- [ ] **Step 6: Commit**

```bash
git add src/email_agent/approval.py tests/test_approval.py tests/fixtures/tg_callback.json tests/fixtures/tg_message.json
git commit -m "feat: telegram approval listener (routing, edit flow, single-owner guard)"
```

---

## Task 6: Pipeline — notify and set pending when a telegram client is present

**Files:**
- Modify: `src/email_agent/pipeline.py`
- Test: `tests/test_pipeline.py` (add a test)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_pipeline.py`:
```python
class FakeTelegramPipe:
    def __init__(self):
        self.approvals = []

    async def send_approval(self, *, sender, subject, body, message_id):
        self.approvals.append(message_id)
        return "tg-1"


@pytest.mark.asyncio
async def test_telegram_notify_sets_pending():
    state = FakeState()
    gmail = FakeGmail(_email())
    tg = FakeTelegramPipe()

    async def provider(system, user, *, model, json_mode=False):
        return '{"should_reply": true, "category": "request", "reason": "asks"}' if json_mode else "body"

    # extend FakeState with set_pending for this test
    state.pendings = []
    async def set_pending(email, *, draft_id, tg_message_id, triage):
        state.pendings.append((email.message_id, draft_id, tg_message_id))
    state.set_pending = set_pending

    from email_agent.memory import NullMemory
    await process_message("m1", gmail=gmail, state=state, provider=provider,
                          memory=NullMemory(), cfg=CFG, dry_run=False,
                          triage_model="t", draft_model="d", telegram=tg)
    assert tg.approvals == ["m1"]
    assert state.pendings == [("m1", "draft-123", "tg-1")]
    assert state.drafts == []  # used set_pending, not record_drafted
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_pipeline.py -q`
Expected: FAIL (`process_message() got an unexpected keyword argument 'telegram'`)

- [ ] **Step 3: Modify `process_message`**

In `src/email_agent/pipeline.py`, change the signature to add `telegram=None` (after `draft_model`):
```python
    triage_model: str,
    draft_model: str,
    telegram=None,
) -> None:
```

Replace the draft-creation/record block (the part after `if dry_run: ... return`) with:
```python
        draft_id = await gmail.create_draft(
            to=email.sender, subject=f"Re: {email.subject}",
            body=body, thread_id=email.thread_id,
        )
        if telegram is not None:
            tg_id = await telegram.send_approval(
                sender=email.sender, subject=email.subject, body=body,
                message_id=email.message_id,
            )
            await state.set_pending(email, draft_id=draft_id, tg_message_id=tg_id, triage=result)
            log.info("pending approval %s -> draft %s (tg %s)", message_id, draft_id, tg_id)
        else:
            await state.record_drafted(email, draft_id=draft_id, triage=result)
            log.info("drafted %s -> %s", message_id, draft_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_pipeline.py -q`
Expected: PASS (existing pipeline tests still pass — `telegram` defaults to `None`)

- [ ] **Step 5: Commit**

```bash
git add src/email_agent/pipeline.py tests/test_pipeline.py
git commit -m "feat: pipeline notifies telegram + sets pending when enabled"
```

---

## Task 7: Wire the listener into the FastAPI lifespan

**Files:**
- Modify: `src/email_agent/app.py`
- Test: `tests/test_app.py` (still passes; add a guard test)

- [ ] **Step 1: Modify `app.py`**

Replace `_run_agent` and the lifespan in `src/email_agent/app.py` with:
```python
import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from email_agent.approval import ApprovalListener
from email_agent.config import Settings, load_behavior
from email_agent.db import SessionLocal
from email_agent.gmail_client import GmailClient
from email_agent.logging_setup import configure_logging
from email_agent.memory import NullMemory
from email_agent.pipeline import process_message
from email_agent import provider as provider_module
from email_agent.state import StateRepository
from email_agent.telegram_bot import TelegramClient
from email_agent.trigger.poll import PollTrigger


async def _run_agent(settings: Settings, behavior: dict) -> None:
    gmail = GmailClient(settings=settings)
    memory = NullMemory()
    telegram = None
    if settings.telegram_enabled:
        telegram = TelegramClient(settings.telegram_bot_token, settings.telegram_chat_id)

        @asynccontextmanager
        async def repo_factory():
            async with SessionLocal() as session:
                yield StateRepository(session)

        listener = ApprovalListener(
            telegram=telegram, gmail=gmail, repo_factory=repo_factory,
            chat_id=settings.telegram_chat_id,
        )
        asyncio.create_task(listener.run())

    trigger = PollTrigger(gmail=gmail, interval=settings.poll_interval_seconds)

    async def handler(message_id: str) -> None:
        async with SessionLocal() as session:
            await process_message(
                message_id, gmail=gmail, state=StateRepository(session),
                provider=provider_module.complete, memory=memory, cfg=behavior,
                dry_run=settings.dry_run, triage_model=settings.triage_model,
                draft_model=settings.draft_model, telegram=telegram,
            )

    await trigger.run(handler)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    configure_logging(settings.log_level)
    behavior = load_behavior()
    task = None
    if os.environ.get("AGENT_AUTOSTART", "0") == "1":
        task = asyncio.create_task(_run_agent(settings, behavior))
    yield
    if task:
        task.cancel()


app = FastAPI(title="Email Agent", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "dry_run": Settings().dry_run}
```

- [ ] **Step 2: Verify `/health` still passes and the app imports**

Run: `.venv/Scripts/python.exe -m pytest tests/test_app.py -q`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/email_agent/app.py
git commit -m "feat: start telegram approval listener in the FastAPI lifespan"
```

---

## Task 8: Full suite + push

- [ ] **Step 1: Run the entire suite (DB up)**

Run: `docker compose up -d db && .venv/Scripts/python.exe -m pytest -q`
Expected: all pass (Phase 1 tests + new Telegram/approval tests); live triage corpus skipped without a key.

- [ ] **Step 2: Push**

```bash
git push origin dev
```

---

## Live verification (deferred — needs the bot token)

Once you have `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` in `.env` and set
`TELEGRAM_ENABLED=true`:

1. Find your chat id: message the bot once, then
   `https://api.telegram.org/bot<TOKEN>/getUpdates` and read `message.chat.id`.
2. Run the service non-dry-run:
   `DRY_RUN=false AGENT_AUTOSTART=1 .venv/Scripts/python.exe -m uvicorn email_agent.app:app`
3. Send yourself a question email. Within one poll interval you get a Telegram card.
   Tap **Approve** → the reply sends; **Skip** → the draft is deleted; **Edit** →
   reply with new text → **Send**.
4. Confirm `processed_messages.status` shows `sent` / `rejected` accordingly.

## Phase 2 done when

- A drafted reply (non-dry-run, telegram enabled) produces a Telegram card with
  working Approve / Edit / Skip.
- Approve sends, Skip deletes, Edit rewrites then sends after a confirm — each
  reflected in `processed_messages.status`.
- Updates from any other chat id are ignored.
- `TELEGRAM_ENABLED=false` reproduces Phase 1 behavior exactly.
- The full offline suite is green.
