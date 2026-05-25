# 03 — This Email Agent, explained

Now the fun part: our project is a real, working agent. Let's map the
[five ingredients from guide 02](02-how-to-build-an-agent.md) to actual files,
then walk a single email through the system.

## The five ingredients, in our code

| Ingredient | In this project | File |
|------------|-----------------|------|
| 1. **Model** (brain) | Two models: a cheap one to triage, a capable one to draft | configured in `config.yaml` / `.env` |
| 2. **Instructions** | A triage system prompt + a draft system prompt; emails fenced as untrusted data | [`triage.py`](../../src/email_agent/triage.py), [`draft.py`](../../src/email_agent/draft.py) |
| 3. **Tools** (hands) | Read inbox, fetch a thread, **create a draft** | [`gmail_client.py`](../../src/email_agent/gmail_client.py) |
| 4. **Control loop** | A poll trigger running inside a FastAPI service | [`trigger/poll.py`](../../src/email_agent/trigger/poll.py), [`app.py`](../../src/email_agent/app.py) |
| 5. **Memory / state** | A Postgres table tracking every message; pgvector reserved for future semantic memory | [`state.py`](../../src/email_agent/state.py) |
| + **The model seam** | One vendor-agnostic `complete()` call | [`provider.py`](../../src/email_agent/provider.py) |
| + **Guardrails** | Drafts-only, JSON validation, dead-letter, prefilter | throughout + [`pipeline.py`](../../src/email_agent/pipeline.py) |

## Following one email through the pipeline

This is the [architecture diagram](README.md#the-architecture-at-a-glance) in
words. The orchestration lives in
[`pipeline.py`](../../src/email_agent/pipeline.py).

1. **Poll trigger** asks Gmail "any new unread mail?" every ~60s. *(Perceive.)*
   Why polling and not a webhook? A laptop has no public URL for Google to call —
   polling works everywhere; webhooks switch on later when deployed.

2. **Idempotency check** — have we seen this `message_id` before? If yes, skip.
   This is **memory** preventing duplicate work.

3. **Ingest** parses the raw Gmail message into a clean `Email` object (sender,
   subject, body). No fancy quote-stripping — we keep it simple.

4. **Prefilter** applies *deterministic rules* (no AI): is it from `no-reply@`?
   Is it a promotion or bulk mail? If so, record "skipped" and stop. **This runs
   before the LLM on purpose** — most mail is machine noise, and rules are free,
   instant, and never hallucinate. Only plausible human mail reaches the model.

5. **Triage** (the cheap LLM) decides: *does this need a reply from me?* It must
   return strict JSON like `{"should_reply": true, "category": "...", "reason":
   "..."}`. We **validate** that JSON; if the model returns junk, we don't crash —
   we surface it. If `should_reply` is false, record "skipped" and stop. *(Think.)*

6. **Draft** (the capable LLM) writes the reply, using the whole email thread for
   context and your persona for voice. It's told to **never invent facts** —
   unknowns become `[BRACKETED PLACEHOLDERS]` for you to fill. *(Think → produce.)*

7. **Create Gmail draft** puts the reply in your Gmail as a **draft**. *(Act.)*
   It is **never sent automatically** — you review and send. *(Human-in-the-loop.)*

8. **Record** the outcome in Postgres. *(Observe / remember.)* Then back to step 1.

If anything throws along the way, the message is marked `needs_attention` instead
of crashing the loop or vanishing — that's the **fail-loud** guardrail.

## Two design choices worth understanding

**Why two different models?** Triage runs on *every* surviving email but only
needs a quick yes/no — so it uses a small, fast, cheap model. Drafting runs only
on the few emails that need a reply but needs to write *well* — so it uses a
bigger model. This keeps cost near zero. (Both are free on Groq to start.) This
is the **two-model routing** pattern.

**Why the "provider seam"?** Every model call goes through one tiny function,
`provider.complete(system, user, model)`. Nothing else in the codebase knows
which AI vendor we use. This isn't theoretical: during testing, Groq blocked our
region — and because of the seam, switching to another provider would have been a
change to `.env`, not a rewrite. *That* is why you isolate vendors behind a seam.

## The agentic ideas, made concrete

| Concept (guide 01) | Where it shows up here |
|--------------------|------------------------|
| The agent loop (perceive→think→act→observe) | the poll → triage → draft → record cycle |
| Tools / actions | `gmail_client.py` (fetch, create draft) |
| Hallucination guard | "never invent facts; use `[PLACEHOLDERS]`" in the draft prompt |
| Prompt-injection guard | emails fenced as `<<<EMAIL>>>…<<<END>>>`, rules only in system prompt |
| Levels of autonomy | starts Level 1 (drafts only), earns its way toward Level 3 |
| Validate model output | triage JSON is parsed + validated, or surfaced as unknown |
| Fail loud | `needs_attention` dead-letter state |

## Where to poke around next

- Run the offline tests to see each piece in isolation: `tests/`.
- Read the actual orchestration: [`pipeline.py`](../../src/email_agent/pipeline.py)
  — it's short and is the whole agent loop in one function.
- Read the prompts: [`triage.py`](../../src/email_agent/triage.py) and
  [`draft.py`](../../src/email_agent/draft.py).
- Tune behavior without touching code: `config.yaml` (persona, skip rules).

➡️ If a term tripped you up, see the [Glossary](04-glossary.md).
