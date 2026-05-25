# 05 — Roadmap

Three phases. Each is an independent slice with its own value, and (after this
design) its own implementation plan. We build **Phase 1 first**; Phases 2 and 3
are scoped here but planned later.

## Phase 1 — Core loop (Gmail-native) 🟢 *build first*

**Goal:** drafts appear in Gmail; the owner reviews and sends them there.

**Scope:**
- In-process poll loop against one Gmail inbox (`gmail.modify` scope).
- Ingest → clean `Email` object (body + metadata; **no quote-parser**).
- **Prefilter** — deterministic skip rules before any LLM (DR-7).
- **Triage** — cheap LLM, strict validated JSON, biased to surface-when-unsure.
- **Draft** — capable LLM, full thread context, owner persona, never invents
  facts; empty memory-injection slot.
- Create the reply as a **Gmail draft**.
- `processed_messages` table + idempotency + `needs_attention` dead-letter.
- **Dry-run mode**, **kill switch**, structured logging.
- `tests/fixtures/` corpus for offline triage regression testing.

**Out of scope here:** Telegram, auto-send, long-term memory.

**Done when:** noise is reliably skipped, repliers get a Gmail draft good enough
to send with light edits, nothing is sent automatically, and the agent runs
unattended without dropping or duplicating work.

## Phase 2 — Telegram approval 🟢/🔵

**Goal:** one-tap approval from the phone; the agent can send on approval.

**Scope:**
- Telegram bot (long-polling, no public URL): push the proposed reply with
  inline **Approve / Edit / Skip**.
- Activate the full approval **state machine** (`approved` / `edited` /
  `rejected` / `sent`).
- **Send-on-approve** via Gmail.
- Runs in the **same single process** as the loop (one SQLite writer).

**Known complexity:** **Edit** is the expensive button — inline buttons can't
capture free text. v1 of Edit should **deep-link to the Gmail draft** rather than
edit inside Telegram; build in-Telegram editing only if that chafes.

**Done when:** the owner can clear drafts from their phone and approved replies
send correctly, with every send still owner-initiated.

## Phase 3 — Memory & earned autonomy 🔵

**Goal:** it sounds more like the owner over time, and *earns* the right to
handle narrow slices on its own.

**Scope:**
- **Voice profile** distilled from sent mail → injected into the draft prompt.
- **Contact notes** per correspondent.
- **Corrections** captured at approval/edit time as learning signals.
- **Semantic exemplar retrieval** via `sqlite-vec` + local embeddings (only when
  the voice profile + hand-picked exemplars stop being enough).
- **Earned autonomy ladder:** track approval/edit rates per sender & category;
  *offer* auto-handling for a proven narrow slice; expand one segment at a time;
  always revocable; always auditable.
- Optionally move to a host and switch poll → `watch`/Pub/Sub if wanted.

**Done when:** drafts measurably need less editing over time, and the owner can
safely grant — and revoke — autonomy for specific trusted segments.

## Sequencing note

The phase boundaries are real product boundaries, not just convenience:
Phase 1 delivers value with zero new external surface beyond Gmail; Phase 2 adds
exactly one channel (Telegram) and the send capability; Phase 3 is where the moat
(voice + memory + earned autonomy) is built once the loop and approval are
trustworthy. Each phase gets its own spec → plan → implementation cycle.
