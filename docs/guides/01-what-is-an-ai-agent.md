# 01 — What is an AI agent?

## The one-sentence version

> An **AI agent** is a program that uses a language model (an "LLM") to **decide
> what to do**, then **actually does it** using tools — repeating that
> decide-then-act loop until a goal is met.

The key words are **decide** and **do**. A chatbot only talks. An agent *acts* —
it reads your email, writes a file, calls an API, books a meeting — and it
chooses those actions itself rather than following a fixed script.

## A useful comparison

| Thing | What it does | Who decides the steps? |
|-------|--------------|------------------------|
| **Plain script** | Always does the exact same steps | The programmer, in advance |
| **Chatbot** | Talks back to you; no real-world actions | n/a (it just generates text) |
| **Workflow / automation** | Fixed pipeline ("if email, then label") | The programmer, in advance |
| **AI agent** | Looks at the situation, *picks* actions, does them, checks the result | The **model**, at run time |

Our Email Agent sits between a workflow and a full agent: the pipeline is fixed,
but the **decisions inside it** — "does this email need a reply?", "what should
the reply say?" — are made by an LLM at run time. That's the agentic part.

## The "agent loop" (the heartbeat of every agent)

Almost every agent, no matter how fancy, is some version of this loop:

```
   ┌─────────────────────────────────────────────┐
   │                                             │
   ▼                                             │
PERCEIVE ──▶  THINK / DECIDE  ──▶  ACT  ──▶  OBSERVE
(get input)   (LLM reasons)      (use a tool)  (see the result)
```

1. **Perceive** — gather input (a new email, a user message, a sensor reading).
2. **Think / decide** — the LLM reasons about what to do next.
3. **Act** — the agent performs an action with a *tool* (send a request, write to
   a database, create a draft).
4. **Observe** — it looks at the result, and loops again if the goal isn't met.

A chatbot stops after "think". An agent continues into "act" and "observe", and
loops. In our project the loop is: *poll the inbox → decide reply-or-not →
write a draft → record what happened → poll again.*

## Levels of autonomy (how much leash the agent has)

Agents aren't all-or-nothing. There's a spectrum:

| Level | Name | The agent… | Example |
|-------|------|------------|---------|
| 1 | **Assistant / co-pilot** | suggests; a human approves every action | drafts an email, you hit send |
| 2 | **Supervised** | acts, but a human can veto / is notified | auto-labels mail, you can undo |
| 3 | **Autonomous** | acts on its own within set limits | replies to routine mail by itself |
| 4 | **Fully autonomous** | sets its own sub-goals and acts freely | rare, risky, mostly research |

**Our Email Agent deliberately starts at Level 1** (it only ever creates a
*draft*; you send it) and is designed to *earn* its way toward Level 3 for narrow,
trusted cases. Starting low and earning trust is a core safety principle — see
the [autonomy model](../01-product-vision.md#the-autonomy-model--how-earned-works).

## Why agents are powerful (and where they fail)

**Powerful because:** an LLM can handle messy, unstructured input (real emails,
free text, ambiguous requests) that a fixed `if/else` script could never cope
with. You describe the *goal*, not every step.

**They fail when:**
- The model **hallucinates** — confidently makes something up. (Our fix: forbid
  inventing facts; leave `[PLACEHOLDERS]`; keep a human in the loop.)
- The input tries to **hijack** them — "ignore your instructions and…" hidden in
  an email. (Our fix: never mix instructions with data — see guide 02.)
- They're given **too much autonomy too soon** — acting irreversibly before
  they're trustworthy. (Our fix: drafts-only, earn autonomy gradually.)

## Common misconceptions

- *"An agent is just a smart chatbot."* No — the defining feature is **taking
  actions** via tools, in a loop, not just chatting.
- *"You need to train your own AI."* No — you **use** an existing model (Groq,
  OpenAI, Anthropic) through an API. You write the loop and tools around it.
- *"More autonomy is better."* No — autonomy should match how much you trust the
  agent and how reversible its actions are.

➡️ Next: [How to build an agent](02-how-to-build-an-agent.md) — the five
ingredients you actually need.
