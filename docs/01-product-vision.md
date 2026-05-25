# 01 — Product Vision

## What we're building

A **personal email chief-of-staff**. It runs continuously against a single Gmail
inbox. For each incoming message it answers two questions — *does this need a
reply from me?* and *if so, what should the reply say?* — and puts a
ready-to-send draft in front of the owner. It starts as a **co-pilot** (the owner
approves everything) and **earns its way** toward running routine email
autonomously.

The near-term wedge is reply-drafting. The long-term value — the reason this is
worth keeping over just reading your own email — is an assistant that **sounds
like you**, **knows your relationships and commitments**, and **gradually takes
work off your plate as it proves it can be trusted.**

## Who it's for

One person — the inbox owner. This is a **personal tool**, not a multi-user
product. That single fact keeps the architecture simple: voice can be tuned to
one person, secrets live on the owner's machine, and there is no multi-tenancy,
data-isolation, or billing surface to build.

## Goals

- Cut the time spent on routine email by drafting replies automatically.
- Surface only mail that genuinely needs a human reply; stay silent on noise.
- Draft in the owner's voice, never inventing facts or commitments.
- Keep a human in the loop on every send — until autonomy is *earned*.
- Run cheaply — ideally free — and stay vendor-neutral.

## Success criteria

- The large majority of "noise" mail (newsletters, receipts, notifications) is
  correctly skipped.
- Drafts are good enough to send with light or no editing most of the time.
- Nothing is ever sent without explicit approval (in the human-in-the-loop era).
- The agent runs unattended for days without dropping or duplicating work.

## Non-goals (early phases)

- No autonomous sending until it is earned per-segment (see autonomy model).
- No multi-inbox or multi-user support.
- No web dashboard.
- No agent framework (LangGraph etc.) — see [Architecture](02-architecture.md).

## Guiding principles

1. **Human-in-the-loop first; autonomy is earned.** The agent proposes; the
   human disposes. Auto-send is unlocked only narrowly, only from evidence, and
   is always revocable.
2. **Provider-agnostic.** No model vendor is hardcoded. One thin seam sits
   between the pipeline and whatever LLM answers.
3. **Right-sized.** Build the smallest thing that works. Defer vector memory,
   webhooks, frameworks, and a web app until there is a concrete reason for each.
4. **Email is untrusted input.** A message body may try to hijack the agent.
   Instructions and email content are never mixed.
5. **Fail loud, never silent.** A message that can't be processed lands in a
   visible "needs attention" state — never dropped, never retried forever.

## The autonomy model — how "earned" works

"Human-in-the-loop until it's good enough to go autonomous" is made concrete by
one rule: **autonomy is earned from evidence, granted narrowly, and always
revocable.**

- The agent **logs its own track record** — how often the owner approves its
  drafts *unedited*, broken down by sender and category.
- When that record is strong for a **narrow slice** (e.g. "20 straight routine
  replies to this client approved unedited"), it **offers** to handle that slice
  on its own.
- Trust expands **one trusted segment at a time** — never a global "autopilot
  ON" switch.
- The owner can **revoke any grant instantly** and always see everything the
  agent did on their behalf.

This makes "fully autonomous someday" a destination arrived at safely, not a
leap of faith.

## User stories

Grouped by theme. **🟢 = the wedge we build first. 🔵 = the vision we grow into.**

### A. Get the noise out of my way 🟢
- As the owner, I want obvious machine mail (newsletters, receipts, no-reply,
  bulk) filtered out automatically, so I only spend attention on mail that might
  actually need me.
- As the owner, I want the agent to judge which *human* emails genuinely need a
  reply from me, so I'm not drowning in the rest.
- As the owner, I want to see *why* it skipped or surfaced something, so I can
  trust its judgment and tune it.

### B. Draft replies in my voice 🟢
- As the owner, I want a ready-to-send reply drafted for anything that needs one,
  so I'm not writing from scratch.
- As the owner, I want drafts that sound like me — my tone, greeting, sign-off —
  so I can send them with little or no editing.
- As the owner, I want it to *never* invent facts or commitments, leaving clear
  `[placeholders]` for what it doesn't know, so I'm never embarrassed by a
  confident lie.
- As the owner, I want it to read the full prior thread as context, so the reply
  fits the conversation.

### C. Stay in control 🟢
- As the owner, I want nothing sent without my explicit approval (early on), so
  nothing goes out under my name that I didn't see.
- As the owner, I want to approve / edit / skip each draft quickly — first in
  Gmail, later one-tap on my phone — so reviewing doesn't become its own chore.
- As the owner, I want a kill switch and a dry-run mode, so I can pause the agent
  or safely test changes against my real inbox.

### D. It sounds more like me over time 🔵
- As the owner, I want my edits to its drafts captured as learning signals, so it
  gets closer to my voice the more I use it.
- As the owner, I want it to remember facts about my contacts and ongoing
  threads, so replies are personal and context-aware.
- As the owner, I want it to learn my writing style from my sent mail, so I don't
  have to hand-configure my "voice."

### E. It earns autonomy gradually 🔵
- As the owner, I want the agent to track its own record (how often I approve
  drafts unedited, per sender/category), so trust is based on evidence, not hope.
- As the owner, I want it to *offer* to handle a narrow slice on its own once
  it's proven reliable there, so autonomy expands one safe segment at a time.
- As the owner, I want to revoke any autonomy instantly and see everything it did
  on my behalf, so I'm never locked out of control.

### F. It grows into a chief-of-staff 🔵
- As the owner, I want a digest of what mattered in my inbox, so I get the gist
  without opening everything.
- As the owner, I want reminders when I haven't heard back on something I sent,
  so threads don't slip through the cracks.
- As the owner, I want to ask it to draft a net-new email ("email the landlord
  about the lease"), so it helps me initiate, not just react.

### G. It runs reliably and never loses my mail 🟢
- As the owner, I want every message handled exactly once, so I never get
  duplicate drafts or missed mail.
- As the owner, I want anything it can't process to land in a visible "needs
  attention" state, so failures surface loudly instead of vanishing.
- As the owner, I want it to never reply to itself, to auto-responders, or to
  bulk senders, so it can't get stuck in embarrassing loops.
