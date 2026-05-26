# Email Agent — Documentation

A personal email chief-of-staff. It reads your incoming Gmail, decides what
deserves a reply, drafts one in your voice, and keeps you in the loop before
anything is sent — earning its way toward handling routine email on its own.

## Documents

| # | Document | What it covers |
|---|----------|----------------|
| 01 | [Product Vision](01-product-vision.md) | What we're building and why, goals/non-goals, guiding principles, user stories, the autonomy model |
| 02 | [Architecture](02-architecture.md) | System design, the pipeline and its stages, component responsibilities, data flow, project layout, robustness, security |
| 03 | [Tech Stack](03-tech-stack.md) | The stack and the reasoning behind each significant choice (decision records) |
| 04 | [Data Model](04-data-model.md) | PostgreSQL schema, the approval state machine, the three-layer memory model and its upgrade path |
| 05 | [Roadmap](05-roadmap.md) | Phased delivery: core loop → approval → memory & autonomy |

## New to AI agents? Start here

[**docs/guides/**](guides/README.md) — beginner-friendly explainers: what an AI
agent is, the five ingredients you need to build one, how this project maps to
them, and a glossary. The system architecture diagram is
[`docs/architecture.drawio`](architecture.drawio) (draw.io format).

## One-paragraph summary

The system is a **linear pipeline of swappable stages** — plain code for the agent
logic, not a framework-driven agent graph — built around two firm rules: **nothing
is sent without the owner's approval (early on)**, and **email is untrusted input**
(its content is never mixed with instructions). It runs as a single containerized
**FastAPI service** against one Gmail inbox, with a pluggable trigger (polling
locally, webhooks once deployed). It stores all state and memory in a
**PostgreSQL** database (with pgvector) and talks to its language model through one
thin provider seam so no vendor is hardcoded. It is designed to run cheaply (free tiers), survive
unattended operation for days, and grow — one earned, revocable step at a time —
from co-pilot toward autopilot.

## Status

Design phase. No implementation yet. These documents are the agreed design and
the basis for the implementation plan.
