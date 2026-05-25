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
| State + memory | **SQLite via stdlib `sqlite3`** (no ORM) | One file. `sqlite-vec` is the named upgrade for semantic memory. |
| Embeddings (later) | **`sentence-transformers`** (local, CPU, free) | Keeps the memory layer free and offline. |
| Scheduling | **In-process loop** (`while True: …; sleep(N)`) | Windows has no `cron`; Task Scheduler can wrap it later. |
| Approval (Phase 2) | **Telegram Bot API** (raw HTTP via `requests`, or `python-telegram-bot`) | Long-polling; no public URL. |
| Testing | **`pytest`** over `tests/fixtures/` | Offline regression tests for prompt changes. |

## Decision records

The reasoning behind the choices that had real alternatives.

### DR-1 — No agent framework
Covered in [Architecture](02-architecture.md#decision-no-agent-framework-langgraph-etc).
Plain functions + SQLite state machine. The pipeline is a `for` loop with one
branch, not a dynamic graph; a framework would add churn and indirection against
the "right-sized" and "understand every line" goals. Revisit only if the system
grows into genuine multi-agent orchestration.

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

### DR-4 — SQLite for all memory (incl. semantic, via `sqlite-vec`)
**Chosen** over a dedicated vector DB (Pinecone/Chroma/Qdrant).

- Voice profile, contact notes, and corrections are structured/text lookups —
  SQLite is the obvious fit.
- Semantic exemplar retrieval needs vector search, and **SQLite does that too**
  via the `sqlite-vec` extension. At personal scale (thousands–tens of thousands
  of emails) a dedicated vector DB is unjustified; brute-force cosine over a few
  thousand vectors is also viable.
- Keeps the whole system in **one local file**, free and offline (local
  `sentence-transformers` embeddings). Detail behind the `memory.py` interface,
  so the upgrade is invisible to callers. See [Data Model](04-data-model.md).

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

### DR-6 — Single process + in-process loop
One process runs both the poll loop and (later) the Telegram listener, so there
is a single writer to the SQLite file — no cross-process write-lock contention.
Scheduling is an in-process `while True: process(); sleep(N)` loop because the
owner is on **Windows** (no `cron`); Task Scheduler can wrap `python main.py` for
headless/boot operation later.

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
