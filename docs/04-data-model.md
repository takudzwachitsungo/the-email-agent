# 04 — Data Model

A single **PostgreSQL** database (with the **pgvector** extension) is the source
of truth for operational state, the approval lifecycle, and (later) long-term
memory. Accessed asynchronously via `asyncpg`; schema managed with `Alembic`. It
runs as a Docker Compose service with its data on a named volume.

## Operational state — `processed_messages`

The bookkeeping table. Prevents double-processing and provides an audit trail.

| Column | Type | Notes |
|--------|------|-------|
| `message_id` | TEXT PRIMARY KEY | Gmail message id — the **idempotency key** |
| `thread_id` | TEXT | Gmail thread id |
| `sender` | TEXT | from address |
| `subject` | TEXT | for logs/audit |
| `triage_decision` | TEXT | `reply` / `skip` |
| `triage_reason` | TEXT | why — for audit & prompt tuning |
| `skip_source` | TEXT | `prefilter` / `triage` (null if replied) |
| `draft_id` | TEXT | Gmail draft id, if one was created |
| `status` | TEXT | see state machine below |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

The `message_id` primary key is what guarantees **each message is handled
exactly once** — re-runs that re-see a message are no-ops.

## Approval state machine — the `status` field

```
                 ┌──skip────────────────────────► skipped   (terminal)
                 │
 (new) ─► pending ┤
                 │
                 ├──drafted──► drafted ─┐                    (Phase 1 terminal:
                 │                      │                     owner sends in Gmail)
                 │            (Phase 2) │
                 │                      ├─approve─► approved ─► sent
                 │                      ├─edit────► edited ───► sent
                 │                      └─reject──► rejected
                 │
                 └──error───► needs_attention   (dead-letter: visible, not retried forever)
```

| Status | Meaning | Phase |
|--------|---------|-------|
| `pending` | accepted, not yet decided | 1 |
| `skipped` | prefilter or triage said no reply — terminal | 1 |
| `drafted` | Gmail draft created; in Phase 1 the owner reviews & sends here | 1 |
| `needs_attention` | processing failed after retries — **dead-letter**, surfaced, never silently dropped or looped | 1 |
| `approved` / `edited` | owner accepted (as-is / after editing) → leads to `sent` | 2 |
| `rejected` | owner declined the draft | 2 |
| `sent` | dispatched via Gmail | 2 |

In **Phase 1**, `drafted` is effectively terminal (the owner finishes in Gmail);
the approve/edit/reject/sent transitions activate in **Phase 2** with the
Telegram approval gate. `skipped` is its own terminal state so re-runs ignore it.

## Memory model — three layers

Only the first two are needed early. All three live in the same Postgres database.

| Layer | What it is | Where | When |
|-------|-----------|-------|------|
| **Operational state** | what's processed; decisions | `processed_messages` (above) | now |
| **Thread context** | prior messages in the conversation | **fetched from Gmail by `threadId`, not stored** | now (free) |
| **Long-term memory** | voice, contact facts, corrections, exemplars | Postgres tables below | later |

- **Thread context is not stored.** Gmail already holds the full thread; the
  draft step fetches it on demand by `threadId`. No duplication, always current.
- **Long-term memory** is the moat ("sound more like me") and the layer most
  easily over-built. It is introduced behind the `memory.py` interface so the
  draft prompt has an obvious injection slot from day one, even while the store
  starts empty.

### Long-term memory tables (introduced in Phase 3)

**`contact_notes`** — facts the agent should remember per correspondent.

| Column | Type | Notes |
|--------|------|-------|
| `sender` | TEXT PK | email address |
| `notes` | TEXT | freeform facts/context, injected into the draft prompt |
| `updated_at` | TIMESTAMP | |

**`corrections`** — the learning signal: the delta between what was drafted and
what the owner actually sent.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `message_id` | TEXT | FK → `processed_messages` |
| `drafted_text` | TEXT | what the agent wrote |
| `sent_text` | TEXT | what the owner sent |
| `created_at` | TIMESTAMP | |

**`voice_profile`** — a distilled description of the owner's writing style
(greeting, sign-off, tone, characteristic phrasing), generated from sent mail and
refined from corrections. A single current row injected into the draft prompt.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `profile` | TEXT | the distilled style guide |
| `updated_at` | TIMESTAMPTZ | |

**`reply_embeddings`** — a vector index over the owner's past sent replies, for
semantic exemplar retrieval.

| Column | Type | Notes |
|--------|------|-------|
| `id` | BIGSERIAL PK | |
| `message_id` | TEXT | source message |
| `content` | TEXT | the reply text that was embedded |
| `embedding` | VECTOR(384) | `pgvector` column (dimension per the local model) |
| `created_at` | TIMESTAMPTZ | |

### Semantic memory — pgvector

`memory.find_similar_replies(text, k)` returns the owner's most similar past
replies, to inject as few-shot exemplars. It is introduced **behind the
interface** so callers never change:

1. **Phase 1:** no-op — the draft uses a hand-written persona only.
2. **Phase 3:** the `reply_embeddings` table above; nearest-neighbor queries in
   SQL (`ORDER BY embedding <=> :query LIMIT k`), adding an HNSW index once the
   corpus warrants one.

Embeddings are produced locally with `sentence-transformers` (CPU, free), so the
memory layer needs no embedding API. `pgvector` keeps relational state and vectors
in the **same database** — a dedicated vector DB is never needed at personal
scale.

> Note: the fastest near-term "sound like me" win is the **voice profile** plus a
> handful of hand-picked exemplars in the draft prompt — roughly 80% of the
> personalization benefit before any semantic retrieval is built.
