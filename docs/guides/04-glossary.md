# 04 — Glossary

Plain-English definitions of the jargon you'll meet. Terms are grouped roughly
from "core" to "advanced". Where it helps, we note how the term shows up in this
project.

## Core terms

**AI agent** — a program that uses an LLM to decide what to do and then does it
with tools, in a loop, toward a goal. (Not just a chatbot — it *acts*.)

**LLM (Large Language Model)** — the "brain". A model trained on huge amounts of
text that, given some text, predicts useful text back. Examples: Llama (via
Groq), GPT (OpenAI), Claude (Anthropic). You *call* one; you don't train it.

**Prompt** — the text you send the model to steer it. See *system prompt* and
*user message*.

**System prompt** — the trusted instructions you (the developer) write: the
agent's role, rules, and required output format. In this project, the triage and
draft system prompts live in `triage.py` and `draft.py`.

**User message** — the actual data to process (an email, a question). Treated as
**untrusted** — it must never be allowed to act as instructions.

**Token** — the unit an LLM reads/writes in — roughly a word-piece (~4 characters
of English). Models have limits and pricing measured in tokens.

**Context window** — the maximum number of tokens a model can consider at once
(its "short-term memory" for a single call). Anything outside it is forgotten.

**Tool / function calling** — giving the model the ability to trigger real
actions (functions). In simple agents you just call functions yourself; in
advanced ones, the model chooses which tool to call.

**Agent loop** — the perceive → think → act → observe cycle that repeats. In this
project it's the poll → triage → draft → record cycle.

## Behavior & quality terms

**Hallucination** — when a model confidently states something false or made-up.
Mitigated here by forbidding invented facts (use `[PLACEHOLDERS]`) and keeping a
human in the loop.

**Prompt injection** — an attack where malicious text *inside the data* tries to
override the agent's instructions (e.g. an email saying "ignore your rules and…").
Mitigated by never mixing instructions with data and fencing the data.

**Human-in-the-loop (HITL)** — a person approves consequential actions before
they happen. This agent only creates *drafts*; you send them.

**Temperature** — a knob (0–1+) controlling randomness of model output. Low =
focused/consistent; high = creative/varied.

**JSON mode / structured output** — asking the model to return strictly formatted
JSON so your code can parse it reliably. Triage uses this and validates the
result.

**Idempotency** — doing the same operation twice has the same effect as once.
Here, the `message_id` primary key means an email is processed exactly once, even
if the loop re-sees it.

**Dead-letter / needs-attention** — a visible "this failed, look at it" state, so
problems surface loudly instead of being dropped or retried forever.

## Memory & retrieval terms

**State** — data the agent stores to remember across steps/runs (what's been
processed, what failed). Lives in Postgres here.

**Embedding** — a list of numbers representing the *meaning* of a piece of text,
so similar meanings have similar numbers. The basis of semantic search.

**Vector / vector search** — storing embeddings and finding the "nearest" ones to
a query — i.e. *semantically* similar text. Used for "find my most similar past
replies".

**pgvector** — a PostgreSQL extension that stores embeddings and does vector
search *inside the same database*, so you don't need a separate vector database
at small/personal scale. Reserved for this project's future memory features.

**RAG (Retrieval-Augmented Generation)** — fetch relevant facts/examples (often
via vector search) and put them into the prompt so the model answers from real,
specific information instead of guessing. A planned later feature here.

## Architecture & tooling terms

**Provider / provider seam** — the thin layer that hides *which* AI vendor you
use behind one function (`provider.complete()`), so vendors are swappable. Saved
us when Groq was geo-blocked.

**Two-model routing** — using a cheap model for the high-volume cheap task
(triage) and a capable model for the rare expensive task (drafting), to keep cost
and latency low.

**Polling vs webhook** — two ways to learn "something happened". *Polling* = you
periodically ask ("any new mail?"); *webhook* = the other service calls you when
it happens. Polling needs no public URL (works on a laptop); webhooks are
instant but need a reachable address.

**MCP (Model Context Protocol)** — an open standard for connecting external tools
and data sources to an AI agent in a uniform way (the Excalidraw connector used
to draw this project's diagram is an MCP server, for example).

**Agent framework** — a library (e.g. LangGraph) that provides scaffolding for
building agents. Useful for complex multi-step/multi-agent systems; often
unnecessary overhead for a simple linear agent like this one, which uses plain
Python instead.

**FastAPI / Uvicorn** — the Python web-service framework (and the server that runs
it) hosting this agent. It runs the poll loop as a background task and can serve
webhook endpoints once deployed.

⬅️ Back to the [guides index](README.md).
