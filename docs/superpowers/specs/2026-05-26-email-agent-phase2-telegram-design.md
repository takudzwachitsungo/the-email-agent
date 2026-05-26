# Phase 2 — Telegram Approval Gate — Design

> Builds on Phase 1 (the core poll → triage → draft pipeline). This phase adds the
> human-in-the-loop **approval channel**: instead of finding drafts in Gmail, the
> owner approves/edits/skips them from Telegram, and approval **sends**.

## Goal

When the pipeline creates a reply draft, notify the owner on Telegram with the
proposed text and inline **[Approve] [Edit] [Skip]** buttons. Approve sends the
draft; Edit lets the owner rewrite it in-chat (with a final Send confirmation);
Skip deletes the draft. Everything runs in the existing single FastAPI process via
Telegram **long-polling** (`getUpdates`) — no public URL required.

## Scope

**In scope:**
- A Telegram transport client (raw HTTP via `httpx`).
- An approval listener (a second background task beside the poll trigger).
- Gmail draft `send` / `delete` / `update` operations.
- Pipeline change: drafted messages become `pending` and trigger a notification.
- The approval state machine and a schema migration for `tg_message_id`.

**Out of scope (YAGNI, later phases):**
- A general "command the agent from Telegram" interface.
- A daily digest / summaries.
- Webhook delivery (long-poll only for now; webhook is a future trigger swap).
- Long-term memory / earned autonomy (Phase 3).

## Decisions (settled during design)

| Decision | Choice |
|----------|--------|
| Telegram library | **Raw HTTP via `httpx`** — ~4 endpoints, transparent, light |
| Edit flow | **In-Telegram editing**: prompt → capture new text → preview → confirm Send |
| Skip behavior | **Delete** the Gmail draft (keeps the drafts folder clean) |
| Delivery | **Long-poll** `getUpdates` in-process (no public URL) |
| Trust | Listener ignores any chat that isn't the configured `TELEGRAM_CHAT_ID` |

## Components

Each is a focused unit with a clear boundary.

| Module | Responsibility | Depends on |
|--------|----------------|-----------|
| `telegram_bot.py` | **Transport only.** `send_approval()`, `send_message()`, `edit_message()`, `get_updates(offset)`, `answer_callback()`. Builds inline keyboards; formats the approval card. Knows the Bot API, nothing about pipeline/state. | httpx, config |
| `approval.py` | **The listener/orchestrator.** Long-polls `getUpdates`; routes callback taps and edit replies to state transitions + Gmail actions; tracks one in-progress edit per chat. | telegram_bot, gmail_client, state |
| `gmail_client.py` (extend) | `send_draft(draft_id)`, `delete_draft(draft_id)`, `update_draft(draft_id, to, subject, body, thread_id)`. | Gmail API |
| `pipeline.py` (change) | After `create_draft`, set status `pending`, store `tg_message_id`, and `send_approval()`. (Was: terminal `drafted`.) | telegram_bot, state |
| `state.py` (extend) | New `tg_message_id` column; `set_pending`, `set_sent`, `set_rejected`. | Postgres |
| `app.py` (change) | Start the approval listener as a lifespan background task (gated by `AGENT_AUTOSTART`). | approval |
| `config.py` (extend) | `telegram_bot_token`, `telegram_chat_id`, `telegram_enabled`. | pydantic-settings |

## Data flow

**Notification (end of pipeline, non-dry-run only):**
1. Pipeline creates the Gmail draft (as in Phase 1).
2. Pipeline calls `telegram.send_approval(email, body, message_id)` → Telegram returns a `message_id` for the sent card.
3. State row: `status = pending`, `tg_message_id = <card id>`.
   (In dry-run, no draft is created, so no notification — unchanged.)

**Approve:** callback `approve:<message_id>` → `gmail.send_draft(draft_id)` →
`state.set_sent` → `edit_message` to "✅ Sent".

**Skip:** callback `skip:<message_id>` → `gmail.delete_draft(draft_id)` →
`state.set_rejected` → `edit_message` to "🗑 Skipped".

**Edit (multi-step):**
1. callback `edit:<message_id>` → `answer_callback`; bot remembers
   `awaiting_edit[chat_id] = message_id`; sends "Send me the revised reply for:
   <subject>".
2. Next **plain text message** from that chat (while awaiting) → `gmail.update_draft(...)`
   with the new body → bot shows a **preview** with **[Send] [Cancel]**; clears the
   awaiting flag.
3. callback `send:<message_id>` → `gmail.send_draft(draft_id)` → `state.set_sent` →
   "✅ Sent (edited)". `cancel:<message_id>` → leaves the (updated) draft, status
   stays `pending` or → `rejected` per the Cancel; we keep it simple: Cancel →
   "Cancelled; draft left in Gmail", status unchanged (`pending`).

**callback_data format:** `"<action>:<message_id>"` where action ∈
`{approve, skip, edit, send, cancel}`. Gmail message ids are short hex; well within
Telegram's 64-byte callback_data limit.

## State machine

```
(drafted) ─notify─▶ pending ─approve─▶ sent
                       │
                       ├─edit─▶ (await text) ─Send─▶ sent
                       │
                       ├─skip────────────────────▶ rejected
                       │
                       └─error──────────────────▶ needs_attention
```

`pending` replaces Phase 1's terminal `drafted` when Telegram approval is enabled.
If `telegram_enabled` is false, behavior is exactly Phase 1 (`drafted` is terminal,
owner uses Gmail) — so Phase 1 mode still works.

## Schema change — migration `0002`

Add to `processed_messages`:

| Column | Type | Notes |
|--------|------|-------|
| `tg_message_id` | TEXT (nullable) | the Telegram card's message id, so we can edit it on action |

No other columns needed; the awaiting-edit state is in-memory in the listener.

## Configuration

`.env` / `Settings` additions:
- `TELEGRAM_BOT_TOKEN` — from @BotFather (secret, git-ignored).
- `TELEGRAM_CHAT_ID` — the owner's chat id (from `getUpdates` after messaging the bot).
- `TELEGRAM_ENABLED` — bool; when false, Phase 1 behavior (default false so tests/CI don't require a token).

## Security & robustness

- **Single-owner:** the listener processes updates **only** from `TELEGRAM_CHAT_ID`;
  all other chats are ignored and logged.
- **Send retries:** Telegram API calls use the same fail-fast retry policy as the
  LLM provider (retry transient/5xx/connection; not 4xx). If a notification fails
  after retries, the row → `needs_attention` (the Gmail draft remains as fallback).
- **Resilient listener:** the `getUpdates` loop catches and logs per-iteration
  errors and continues; `offset` is advanced past handled updates so none are
  reprocessed. Taps on unknown/expired/already-actioned messages get a polite
  "no longer pending" reply.
- **One edit at a time:** `awaiting_edit` is per-chat and in-memory; a process
  restart simply cancels an in-progress edit (owner re-taps Edit). No persistence
  needed, no corruption possible.
- **Never auto-sends:** every send is a tap (Approve, or Send after Edit).

## Error handling

- Gmail action failures (send/delete/update) → answer the callback with the error,
  set `needs_attention`, leave a visible trail; never crash the listener.
- Malformed/foreign updates → ignored + logged.
- Both background tasks (poller + listener) share the process; each DB write uses
  its own async session/transaction.

## Testing

All offline, with fakes — no live Telegram:
- **Routing:** fake Telegram client + fake Gmail + fake state. Assert:
  `approve:<id>` → `send_draft` + status `sent`; `skip:<id>` → `delete_draft` +
  `rejected`; `edit:<id>` → awaiting set, then a text update → `update_draft` +
  preview, then `send:<id>` → `send_draft` + `sent`.
- **Security:** an update from a non-owner chat id is ignored (no Gmail/state calls).
- **Formatting:** the approval card contains sender, subject, truncated body, and
  the three inline buttons with correct callback_data.
- **Transport:** `telegram_bot` methods build the right request payloads (assert
  against a mocked httpx client), mirroring the Phase 1 provider test style.
- **Fixtures:** sample Telegram `getUpdates` payloads (a callback_query and a text
  message) under `tests/fixtures/`.

## File structure (additions to Phase 1)

```
src/email_agent/
├── telegram_bot.py     # NEW: httpx transport + approval-card formatting
├── approval.py         # NEW: getUpdates listener + action routing
├── gmail_client.py     # +send_draft / delete_draft / update_draft
├── pipeline.py         # notify + set pending (when telegram_enabled)
├── state.py            # +tg_message_id, set_pending/sent/rejected
├── app.py              # start approval listener in lifespan
└── config.py           # telegram settings
alembic/versions/
└── 0002_tg_message_id.py   # NEW migration
tests/
├── test_telegram.py    # NEW: transport payloads + card formatting
├── test_approval.py    # NEW: routing, edit flow, security
└── fixtures/
    ├── tg_callback.json    # NEW
    └── tg_message.json     # NEW
```

## Done when

- A drafted reply produces a Telegram card with working Approve/Edit/Skip.
- Approve sends the Gmail draft; Skip deletes it; Edit rewrites then sends after a
  confirm — all reflected in `processed_messages.status`.
- Updates from any other chat are ignored.
- With `TELEGRAM_ENABLED=false`, the system behaves exactly as Phase 1.
- All new logic is covered by offline tests; the full suite stays green.
