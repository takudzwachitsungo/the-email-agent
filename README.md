# The Email Agent

A **personal email chief-of-staff**. It reads your incoming Gmail, decides what
deserves a reply, drafts one in your voice, and keeps you in the loop before
anything is sent — earning its way toward handling routine email on its own.

> Status: **design phase.** No application code yet — the design is documented
> and agreed; implementation follows.

## What it does

For each incoming message it answers two questions — *does this need a reply from
me?* and *if so, what should the reply say?* — and puts a ready-to-send draft in
front of you. It starts as a **co-pilot** (you approve everything) and
**earns its way** toward running routine email autonomously, one narrow,
revocable step at a time.

## Design at a glance

- **A linear pipeline of swappable stages**, not a framework-driven agent graph:
  `poll → prefilter → triage → draft → (approval) → (send)`.
- **Two firm rules:** nothing is sent without approval (early on), and email is
  untrusted input (content is never mixed with instructions).
- **Single Python process**, **single SQLite file** for state and memory, **one
  thin provider seam** so no LLM vendor is hardcoded.
- Designed to run **cheaply (free tiers)** and survive **unattended for days**.

## Documentation

Full design lives in [`docs/`](docs/):

| Document | Covers |
|----------|--------|
| [Product Vision](docs/01-product-vision.md) | Vision, goals, principles, user stories, autonomy model |
| [Architecture](docs/02-architecture.md) | Pipeline, components, data flow, security, project layout |
| [Tech Stack](docs/03-tech-stack.md) | The stack and the reasoning behind each choice |
| [Data Model](docs/04-data-model.md) | SQLite schema, state machine, memory model |
| [Roadmap](docs/05-roadmap.md) | Phased delivery: core loop → approval → memory & autonomy |

## Branches

- **`main`** — stable / reviewed.
- **`dev`** — active development.
