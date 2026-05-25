# Beginner Guides — The World of AI Agents

These guides are for someone new to AI agents. They explain what an agent *is*,
what you need to build one, and how **this** project (the Email Agent) is a
real, working example of those ideas. No prior AI experience assumed.

Read them in order:

| # | Guide | What you'll learn |
|---|-------|-------------------|
| 01 | [What is an AI agent?](01-what-is-an-ai-agent.md) | The big picture: agent vs chatbot vs script, the "agent loop", levels of autonomy |
| 02 | [How to build an agent](02-how-to-build-an-agent.md) | The 5 ingredients every agent needs, and how you supply each one |
| 03 | [This Email Agent, explained](03-this-email-agent-explained.md) | How our project maps those 5 ingredients to real files and the pipeline |
| 04 | [Glossary](04-glossary.md) | Plain-English definitions of the jargon (LLM, token, prompt, RAG, MCP…) |

## The architecture at a glance

The system architecture diagram (also openable/editable on Excalidraw):

> **Editable diagram:** https://excalidraw.com/#json=PE3dr7wh2dwVPGzW10p4x,DHC7KShWaN1whRo4mcpMhw

```
                          FastAPI service (one container)
   Gmail inbox  ──poll──▶  Poll trigger ▶ Ingest ▶ Prefilter ▶ Triage ▶ Draft ▶ Create draft
        ▲                                              │          │        │           │
        └──────────── draft (never auto-sent) ─────────┘ (skip)   ▼        ▼           ▼
                                                        Triage & Draft ──▶ Provider seam ──▶ LLM (Groq)
                                                                           every step ──▶ PostgreSQL + pgvector
```

For the full technical design (not beginner-focused) see the docs one level up:
[architecture](../02-architecture.md), [tech stack](../03-tech-stack.md),
[data model](../04-data-model.md).
