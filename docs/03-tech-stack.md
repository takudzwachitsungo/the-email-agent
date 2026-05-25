# 03 — Tech Stack

## Summary

| Concern | Choice | Notes |
|---------|--------|-------|
| Language | **Python 3.11+** | Best ecosystem for Gmail + LLM SDKs. |
| Runtime / deps | **`uv`** | Fast, handles the venv, great on Windows. (`pip` + venv is a fine fallback.) |
| Gmail | **`google-api-python-client`, `google-auth-oauthlib`** | The official path. Verbose but correct. |
| LLM access | **`openai` SDK + `base_url` swap**, wrapped in `provider.py` | One SDK reaches Groq / OpenAI / OpenRouter / Together by changing `base_url` + key. |
| LLM output | **Pydantic** + SDK JSON mode (`response_format={"type":"json_object"}`) | Guarantee valid JSON or fail loud — never "hope it parses." |
| Retries | **`tenacity`** | Decorator-based retry-with-backoff; don't hand-roll. |
| Config + secrets | **`pydantic-settings` + `python-dotenv`** | Typed, validated; misconfig fails at startup with a clear message. |
| State + memory | **PostgreSQL + pgvector** (async via `asyncpg`; `Alembic` migrations) | One store for relational state *and* vectors. Runs as a compose service. |
| Embeddings (later) | **`sentence-transformers`** (local, CPU, free) | Keeps the memory layer free and offline. |
| Web service | **FastAPI + Uvicorn** | The app is a deployable ASGI service from day one — hosts the pipeline and (when deployed) webhook endpoints. |
| Trigger | **Pluggable: poll (default) or webhook** | Poll loop runs as a FastAPI background task locally; Gmail Pub/Sub + Telegram webhooks once deployed. A config flag, not a rewrite. |
| Containerization | **Docker + docker-compose** | Built deployment-ready; secrets + DB mounted as volumes, never baked into the image. |
| Approval (Phase 2) | **Telegram Bot API** (raw HTTP via `requests`, or `python-telegram-bot`) | Long-polling locally; webhook once deployed. |
| Testing | **`pytest`** over `tests/fixtures/` | Offline regression tests for prompt changes. |

## Decision records

The reasoning behind the choices that had real alternatives.

### DR-1 — No agent-orchestration framework (FastAPI is the web shell, though)
Plain functions + a database-backed state machine for the pipeline. It is a `for`
loop with one branch, not a dynamic graph; an **agent** framework (LangGraph etc.) would add
churn and indirection against the "right-sized" and "understand every line" goals.
Revisit only if the system grows into genuine multi-agent orchestration.

**This is distinct from the web framework.** FastAPI *is* used (DR-9) — not to
orchestrate the agent, but to package it as a standard, deployable service.
Orchestration stays plain code; hosting uses a real framework. The two choices are
independent and not in tension. See
[Architecture](02-architecture.md#decision-fastapi-shell-no-agent-framework).

### DR-2 — Provider seam: OpenAI SDK + `base_url` swap
**Chosen** over LiteLLM and hand-rolled per-provider `if/else`.

- The OpenAI SDK speaks to **Groq, OpenAI, OpenRouter, Together** (and local
  Ollama) just by changing `base_url` + API key. Groq's free tier works out of
  the box, satisfying the "free + vendor-neutral" goal at near-zero complexity.
- Wrapped in a thin `provider.complete(system, user, model)` so call sites stay
  clean and the seam owns no prompts.
- **LiteLLM** (one call, 100+ providers, built-in fallbacks/cost tracking) was
  rejected as a *now* dependency: heavier surface area and occasional breaking
  changes — magic we wouldn't fully control. It remains the graduation path if
  true multi-provider fallback is ever needed.
- **Anthropic**, if ever wanted, becomes the single special adapter behind the
  same seam.

### DR-3 — Two-model routing (cost)
Triage runs on **every** surviving email but needs only a quick classification;
drafting runs on the **small subset** that needs a reply but benefits from
quality. So the steps use different models, configured per-step:

| Step | Volume | Needs | Model (free default) |
|------|--------|-------|----------------------|
| Triage | every survivor | fast yes/no + tag | small/cheap (e.g. Llama 3.1 8B on Groq) |
| Draft | repliers only | nuanced writing | capable (e.g. Llama 3.3 70B on Groq) |

The expensive model is invoked rarely, keeping cost near zero inside the free
tier. **Start fully free (Groq); upgrade the draft model to Claude/GPT only after
feeling a quality gap** — the seam (DR-2) makes that a config change.

### DR-4 — PostgreSQL + pgvector for state and memory
**Chosen** over SQLite (the simpler option) and over a dedicated vector DB
(Pinecone/Qdrant).

- **Why not SQLite:** it would work fine at this scale, but we've committed to a
  deploy-first shape (FastAPI + Docker, a server, a likely Phase 3 dashboard).
  That means concurrent access — SQLite's weak spot — and starting on Postgres
  avoids a later SQLite→Postgres migration.
- **Why not a dedicated vector DB:** unjustified at personal scale. `pgvector` (a
  Postgres extension) keeps relational state *and* vectors in **one store**;
  retrieval over thousands–tens-of-thousands of vectors is single-digit
  milliseconds — the same as a file-based vector index. The speed gap only appears
  at millions of vectors + high QPS, which a single inbox never reaches.
- **Not about speed; about consistency.** At this scale Postgres is not faster
  than SQLite — it is the conventional, deployable datastore that matches the rest
  of the stack and removes future rework.
- Accessed async via `asyncpg`, schema managed with `Alembic`. Embeddings are
  produced locally with `sentence-transformers` (free, offline) and stored in a
  `pgvector` column. All behind the `state.py` / `memory.py` interfaces, so the
  backend stays swappable. See [Data Model](04-data-model.md).

### DR-5 — No quote/signature parser
**Decision:** Ingest extracts the plaintext body + metadata only; it does **not**
strip quoted history or signatures.

- There is no reliable cross-client standard; even mature libraries (`talon`) are
  imperfect — a tar pit for marginal benefit.
- **Triage** classifies fine with quoted text present.
- **Draft** uses Gmail's `threadId` to fetch prior messages as discrete
  structured items, rather than un-quoting one flattened body.
- Light heuristic stripping (cut at `On <date> … wrote:`) is a possible
  nice-to-have, not a pillar.

### DR-6 — Single process (one FastAPI / Uvicorn service)
One Uvicorn process hosts the FastAPI app, which runs the poll trigger as a
background task (FastAPI lifespan) and serves the webhook/`/health` endpoints.
Keeping it to one process keeps the design simple — one owner of the poll loop and
the DB writes, with no need to coordinate multiple workers yet. This background
task replaces `cron` (the owner is on
**Windows**, which has none); everything starts with `uvicorn` — `uv run` locally,
the container entrypoint in Docker.

### DR-7 — Rule prefilter before the triage LLM
A deterministic prefilter stage runs **before** any LLM call, dropping obvious
machine mail by header/category rules. Most inboxes are majority machine mail, so
this (a) cuts cost, (b) protects the Groq free-tier rate limits, and (c) is more
reliable than an LLM for the easy cases (rules don't hallucinate).

### DR-8 — Bias toward under-skipping; offline fixtures
Triage is the hardest judgment ("does this need a reply *from me*"). Two
mitigations: the triage prompt is instructed to **surface when unsure** (a missed
real email costs more than an ignored junk draft), and a small `tests/fixtures/`
corpus of sample emails with expected decisions enables offline regression
testing of prompt changes. Tighten skip aggressiveness later from logs.

### DR-9 — Deployment-ready from day one (FastAPI + Docker + pluggable trigger)
**Decision:** Build the app as a containerized FastAPI service from the start,
rather than a bare script that gets re-architected for deployment later.

**Why:** the goal is the standard, deployable shape up front — no repeated rework
as it moves laptop → server. The structure that makes this zero-rework is a
**pluggable trigger** behind one interface, with two implementations:
- **Poll** (default) — a FastAPI background task that polls Gmail; Telegram via
  long-poll. Works anywhere, including the laptop. Used now.
- **Webhook** — FastAPI endpoints receiving Gmail `watch`+Pub/Sub push and
  Telegram webhooks. Used once deployed behind a public HTTPS URL.

The pipeline, state, and provider seam are **identical** in both modes; switching
is a **config flag**, not a rewrite.

**Honest caveat:** webhooks need a public URL, which a laptop behind NAT lacks. So
locally we run in **poll mode**; webhook endpoints are exercised once deployed (or
via a `cloudflared`/`ngrok` tunnel for local testing). This is the one thing that
genuinely differs local vs deployed — and only the trigger *config* changes, never
the code.

**Docker:** a uv-based `Dockerfile` + `docker-compose.yml` from the start. Secrets
(`.env`, `credentials.json`, `token.json`) and `agent.db` are **mounted as
volumes**, never baked into the image. First-run OAuth is done once to generate
`token.json` (on the host or via a one-shot `auth` command), then the token is
mounted — avoiding browser-in-container friction.

## External services & credentials

Three external dependencies. All free to start; none committed to git.

| Service | What's needed | How to get it |
|---------|---------------|---------------|
| Gmail API | OAuth client (`credentials.json`) | Google Cloud Console |
| Model provider | API key | Groq (free, no card) / Anthropic / OpenAI |
| Telegram *(Phase 2)* | Bot token + chat ID | `@BotFather` + `getUpdates` |

### Gmail setup
1. Create a Google Cloud project at `console.cloud.google.com`.
2. APIs & Services → Library → enable the **Gmail API**.
3. OAuth consent screen → app name + support email → Audience **External** → add
   yourself under **Test users**.
4. Data Access → add scope `https://www.googleapis.com/auth/gmail.modify`
   (covers read, draft, label, send).
5. Credentials → Create Credentials → OAuth client ID → **Desktop app** →
   download JSON as `credentials.json`. First run generates a cached
   `token.json`.

> ⚠️ **Known operational landmine — 7-day token expiry.** While the OAuth consent
> screen is in **Testing** mode, refresh tokens for unverified apps **expire after
> 7 days**, and the agent will silently stop. Decide up front: accept weekly
> re-auth, or **publish the app to Production** (no Google verification needed for
> a single user with restricted scopes — it just dismisses the warning).

### Telegram setup *(Phase 2)*
1. Message `@BotFather` → `/newbot` → name + a username ending in `bot`.
2. Save the returned HTTP API token.
3. Message the new bot, open `https://api.telegram.org/bot<TOKEN>/getUpdates`,
   read `chat.id`.

### Secrets at runtime
- `credentials.json` (+ generated `token.json`) — project folder, git-ignored.
- `GROQ_API_KEY` (and/or `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`) — in `.env`.
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` — in `.env` (Phase 2).
