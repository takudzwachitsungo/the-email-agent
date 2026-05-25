# 02 — Architecture

## Shape of the system

The agent is a **linear pipeline of swappable stages** running in a **single
process**, backed by a **single SQLite file** and talking to its language model
through **one thin provider seam**.

It is deliberately *not* built on an agent framework. The pipeline looks like a
graph but mechanically it is a sequence of function calls with one branch and a
state table — a `for` loop with early returns. See
[Decision: no framework](#decision-no-agent-framework-langgraph-etc) below.

## The pipeline

```
Trigger  →  Ingest  →  Prefilter  →  Triage  →  Draft  →  (Approval)  →  (Send)
 (poll)    (parse)    (rules)      (cheap LLM) (capable LLM)  Phase 2     Phase 2
                          │            │
                          └─ skip ─────┴──────────────► record + stop
                          (any stage error) ──────────► needs_attention
```

Reduced to code, the core loop is:

```python
for msg in trigger.new_messages():           # poll Gmail for unread
    if state.already_processed(msg.id):       # idempotency
        continue
    email = ingest.parse(msg)                 # body + metadata, no quote-stripping
    if prefilter.should_skip(email):          # deterministic rules, no LLM
        state.record_skip(email, reason="prefilter"); continue
    decision = triage.classify(email)         # cheap LLM → validated JSON
    if not decision.should_reply:
        state.record_skip(email, decision.reason); continue
    thread = gmail.fetch_thread(email.thread_id)
    draft  = draft.write(email, thread, memory)   # capable LLM, in the owner's voice
    draft_id = gmail.create_draft(draft)
    state.record_drafted(email, draft_id, decision)
```

### Stage responsibilities

| Stage | Responsibility | Talks to |
|-------|----------------|----------|
| **Trigger** | Detect new unread mail. Polling in v1; `watch`+Pub/Sub later. | Gmail |
| **Ingest** | Fetch the message, extract plaintext body + headers/metadata. **No quote/signature parsing** — see decision below. | Gmail |
| **Prefilter** | Deterministic skip rules (no LLM): `no-reply@`, `List-Unsubscribe`, `Precedence: bulk`, `Auto-Submitted`, Gmail `promotions`/`social` categories, own sent mail, allow/deny list. | — |
| **Triage** | Cheap/fast LLM classifies *reply needed?* → strict validated JSON. The majority of surviving mail stops here. | Provider seam |
| **Draft** | Capable LLM writes the reply using the full thread context and the owner's persona/voice. Never invents facts. | Provider seam, Gmail (thread), Memory |
| **Approval** *(Phase 2)* | Push the draft to the owner with Approve / Edit / Skip; drive the state machine. | Telegram |
| **Send** *(Phase 2)* | On approval, create/send via Gmail. | Gmail |

In **Phase 1** there is no Approval/Send stage: the draft is created in Gmail and
the owner reviews and sends it there.

## Components and their boundaries

Each component is a focused module with a clear interface, understandable and
testable on its own.

| Module | Does | Depends on |
|--------|------|-----------|
| `main.py` | The single-process loop: trigger → pipeline. The kill switch and dry-run flag live here. | every stage |
| `gmail_client.py` | OAuth, fetch unread, fetch thread, create draft, (send), label. | Google APIs |
| `ingest.py` | Parse a raw message into a clean `Email` object (body + metadata). | — |
| `prefilter.py` | Deterministic skip rules. Returns skip + reason or "pass". | config |
| `triage.py` | Owns the triage system prompt + JSON schema; assembles `(system, user)`; validates output. | provider, config |
| `draft.py` | Owns the draft system prompt (persona); assembles thread + memory + email; returns reply text. | provider, memory, config |
| `provider.py` | `complete(system, user, model)` — vendor-agnostic. Knows nothing about email. | LLM SDK |
| `memory.py` | `get_voice_profile()`, `get_contact_notes(sender)`, `find_similar_replies(text, k)`, `record_correction(...)`. SQLite-backed. | state/SQLite |
| `state.py` | SQLite read/write; the approval state machine; idempotency. | SQLite |
| `telegram_bot.py` *(Phase 2)* | Notify + Approve/Edit/Skip + state transitions. | Telegram, state |
| `config.py` | Typed, validated settings (secrets + behavioral config). | pydantic-settings |

**The provider seam carries no prompts.** Each AI stage assembles its own
`(system, user)` pair and hands it to `provider.complete(...)`. The seam only
knows how to call a model.

## Data flow

1. **Trigger** polls Gmail; new unread message IDs flow in.
2. **Ingest** turns a raw message into a clean `Email` (body + metadata).
3. **State** is checked for idempotency; seen messages are skipped.
4. **Prefilter** drops machine mail deterministically → recorded as `skip`.
5. **Triage** (cheap LLM) classifies survivors; non-repliers → recorded as `skip`.
6. **Draft** (capable LLM) fetches the thread by `threadId`, pulls voice/contact
   memory, and writes the reply.
7. A **Gmail draft** is created; **State** records `pending`/`drafted`.
8. *(Phase 2)* **Approval** pushes to Telegram; the owner's choice drives the
   state machine; on approve/edit, **Send** dispatches via Gmail.

Both AI steps reach the model **only** through the provider seam. State and
memory share the single SQLite file.

## Prompts and instructions

Instructions are fired at the two AI steps and **only** there. Every model call
is two distinct parts:

- **System prompt — trusted, fixed.** Who the agent is, the rules, the required
  output format. Lives in code/config.
- **User message — untrusted, data.** The email itself, fenced clearly as content
  to process, never as commands.

Two separate instruction sets:

- **Triage system prompt** — short, classification-only. Output: strict JSON
  `{ "should_reply": bool, "category": str, "reason": str }`.
- **Draft system prompt** — the rich one: persona, tone, sign-off, and the
  "never invent commitments; leave `[BRACKETED PLACEHOLDERS]` for missing facts"
  rule. Includes an obvious **memory injection slot** (voice profile + contact
  notes + retrieved exemplars) that is empty in Phase 1 and filled later.

Editable behavior (persona, tone, skip rules, sign-off) lives in a **config
file**, not inline in prompt strings, so tuning means editing config, not code.

## Robustness pillars

Internal discipline — no new external API.

- **Retries + dead-letter.** All API calls wrapped in retry-with-backoff
  (`tenacity`). After retries are exhausted: `status = needs_attention`, never
  dropped or looped forever.
- **Idempotency.** The `message_id` primary key guarantees each message is
  handled once.
- **Loop & noise prevention.** Never reply to own sent mail, `no-reply@`, or
  auto-responders (`Auto-Submitted`, `Precedence: bulk`). Per-sender allow/deny
  list and a global kill switch.
- **Dry-run mode.** Runs the whole pipeline and logs decisions but creates no
  draft and sends nothing — for safe prompt tuning against the real inbox.
- **Structured logging.** Every triage decision (with reason) and every draft
  created is logged, so misbehavior is debuggable.
- **Offline fixtures.** A small corpus of sample emails with expected decisions
  (`tests/fixtures/`) lets prompt changes be regression-tested without the live
  inbox.

## Security & safety

- **Prompt injection.** Email bodies are fenced as data; instructions live only
  in the system prompt; model output (JSON) is validated before any action.
- **No auto-send (early).** Sending requires explicit approval. This single rule
  neutralizes most worst-case outcomes; auto-send is unlocked only per the
  earned, revocable autonomy model.
- **Least privilege.** A single Gmail scope (`gmail.modify`); no broader Google
  access.
- **Secrets hygiene.** All keys in `.env`/config, never in git; `credentials.json`
  and `token.json` git-ignored.

## Triggering & deployment — polling vs webhook

Webhooks are **not required**. Both integration points have a polling
alternative that needs no public infrastructure; the choice is a hosting
decision.

| Where it runs | Trigger | Approval listener | Public URL? |
|---------------|---------|-------------------|-------------|
| Laptop / home box (v1) | in-process poll loop | Telegram `getUpdates` long-poll | No |
| VPS / Cloud Run (later) | Gmail `watch` + Pub/Sub → HTTPS | Telegram webhook | Yes |

The owner is on **Windows**, where `cron` does not exist. v1 uses an in-process
`while True: process(); sleep(N)` loop (`python main.py`); Windows Task Scheduler
can wrap it for headless/boot operation later. The trigger and approval listener
sit behind small interfaces so flipping poll↔webhook later is a swap, not a
rewrite.

## Decision: no agent framework (LangGraph etc.)

**Decision:** Build with plain Python functions + a SQLite state machine. Do not
adopt LangGraph or any agent framework for the current scope.

**Why:**
- The pipeline is **linear with one branch and a state table** — a `for` loop
  with early returns, not a dynamic graph.
- Frameworks earn their keep on the *hard* cases — dynamic multi-tool branching,
  parallel fan-out, cyclic reasoning, multi-agent coordination. None of that
  exists here yet.
- A framework adds a heavy, fast-churning dependency tree (risky for an agent
  meant to run unattended for days) and indirection that fights two stated goals:
  *build the smallest thing that works* and *understand every line of the model
  call.*
- Human-in-the-loop pause/resume is handled by the **SQLite `status` state
  machine**, which the owner fully controls — no framework checkpointer needed.

**Reconsider when:** the chief-of-staff grows into genuine multi-agent
orchestration. Because stages are clean functions, adopting a framework then is a
refactor, not a rewrite. The door stays open; we don't walk through it for a
for-loop.

## Project layout

```
email-agent/
├── docs/                     # this documentation
├── pyproject.toml            # deps + project (managed by uv)
├── .env                      # secrets (git-ignored)
├── credentials.json          # Gmail OAuth client (git-ignored)
├── config.yaml               # persona, tone, skip rules, model-per-step
├── src/email_agent/
│   ├── main.py               # the single-process loop; kill switch; dry-run
│   ├── config.py             # typed settings (pydantic-settings)
│   ├── gmail_client.py       # auth, fetch, thread, draft, send, label
│   ├── ingest.py             # parse → Email object
│   ├── prefilter.py          # deterministic skip rules
│   ├── triage.py             # TRIAGE_SYSTEM prompt + JSON schema + validation
│   ├── draft.py              # DRAFT_SYSTEM persona + thread + memory slot
│   ├── provider.py           # complete(system, user, model) — vendor-agnostic
│   ├── memory.py             # voice profile, contact notes, corrections, exemplars
│   ├── telegram_bot.py       # (Phase 2) notify + approve/edit/skip
│   └── state.py              # SQLite read/write + state machine + idempotency
├── tests/
│   └── fixtures/             # sample emails + expected triage decisions
└── agent.db                  # SQLite store (git-ignored)
```
