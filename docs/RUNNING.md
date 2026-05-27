# Running the Email Agent yourself

A step-by-step guide to running the agent **independently** — on your own machine,
without anyone driving it for you. Commands are **PowerShell** (Windows).

## What you're actually running

The agent is a small background **service**. While it's running it:
- polls your Gmail inbox every ~60s for new unread mail,
- prefilters noise, triages with a cheap LLM, drafts replies with a capable LLM,
- creates a Gmail **draft** and pings you on **Telegram** with Approve / Edit / Skip,
- sends only when **you** tap Approve. It never sends on its own.

It stops when its process stops. There are three ways to run it (pick one):

| Option | Best for | Survives closing the terminal? | Survives reboot? |
|--------|----------|-------------------------------|------------------|
| **A — Local** (`run.ps1`) | development, quick use | No | No |
| **B — Docker** (`docker compose up`) | set-and-forget on this machine | Yes | Yes (auto-restart) |
| **C — Task Scheduler** | laptop that should auto-start it on login | Yes | Yes |

---

## Part 1 — One-time setup (do this once)

### 1. Prerequisites

Check each is installed (install if missing):

```powershell
python --version      # need 3.11+
uv --version          # if "not found": py -m pip install uv   (then reopen the shell)
docker --version      # Docker Desktop
docker compose version
git --version
```

Start **Docker Desktop** and leave it running (the database runs in Docker).

### 2. Get the code and install dependencies

```powershell
git clone https://github.com/takudzwachitsungo/the-email-agent.git
cd the-email-agent
uv sync                # creates .venv and installs everything
```

### 3. Create your secrets file

```powershell
Copy-Item .env.example .env
notepad .env
```

Fill in these values (leave the rest at defaults):

| Variable | What to put | Where it comes from |
|----------|-------------|---------------------|
| `GROQ_API_KEY` | your Groq key | console.groq.com (free, no card) |
| `TELEGRAM_BOT_TOKEN` | your bot token | @BotFather (step 5) |
| `TELEGRAM_CHAT_ID` | your chat id | step 5 |
| `TELEGRAM_ENABLED` | `true` to use Telegram, `false` for Gmail-only | — |
| `DRY_RUN` | `false` to act for real, `true` to only log decisions | — |

`.env` is git-ignored — your secrets never get committed.

### 4. External accounts

**Gmail (so the agent can read your inbox and create drafts):**
1. In Google Cloud Console, create a project, enable the **Gmail API**, configure the
   OAuth consent screen (**External**), and add the Gmail account you want it to run
   on under **Test users**. Add the scope `https://www.googleapis.com/auth/gmail.modify`.
2. Create an **OAuth client ID → Desktop app**, download the JSON, and save it as
   **`credentials.json`** in the project root. (Full detail:
   [docs/03-tech-stack.md → Gmail setup](03-tech-stack.md).)

**Groq (the LLM):** sign up at console.groq.com, create an API key, put it in `.env`.

**Telegram (the approval channel):** see step 5.

### 5. Create your Telegram bot and find your chat id

1. In Telegram, message **@BotFather** → `/newbot` → choose a name and a username
   ending in `bot`. Copy the **token** into `.env` as `TELEGRAM_BOT_TOKEN`.
2. Open your new bot and tap **Start** (send it any message).
3. Find your chat id:
   ```powershell
   $t = (Select-String '^TELEGRAM_BOT_TOKEN=' .env).Line.Split('=')[1]
   (Invoke-RestMethod "https://api.telegram.org/bot$t/getUpdates").result.message.chat.id
   ```
   Put the number it prints into `.env` as `TELEGRAM_CHAT_ID`, and set
   `TELEGRAM_ENABLED=true`.

### 6. Authorize Gmail once (creates `token.json`)

This opens a browser to grant access and caches the login. Do it **on this machine**
(it needs a browser), and **before** the Docker option:

```powershell
.\.venv\Scripts\python.exe -c "from email_agent.gmail_client import bootstrap_auth; bootstrap_auth()"
```

A browser opens → pick the Gmail account you added as a test user → click through the
"unverified app" warning (**Advanced → Go to … (unsafe)**) → **Allow**. It writes
`token.json`. (See Troubleshooting about the 7-day expiry.)

You're set up. Now pick a way to run it.

---

## Part 2 — Option A: Run locally (simplest)

From the project folder:

```powershell
.\run.ps1
```

That script starts Postgres, applies database migrations, and launches the agent on
`http://127.0.0.1:8000`. Leave the window open — it runs as long as the window is open.
**Ctrl+C** stops the agent (Postgres keeps running in Docker).

- To run **for real** (create drafts, send Telegram cards): set `DRY_RUN=false` in `.env`.
- To just **watch decisions** without touching anything: set `DRY_RUN=true`.

> Prefer the raw commands? `run.ps1` is equivalent to:
> ```powershell
> docker compose up -d --wait db
> .\.venv\Scripts\alembic.exe upgrade head
> $env:AGENT_AUTOSTART = "1"
> .\.venv\Scripts\python.exe -m uvicorn email_agent.app:app
> ```

---

## Part 3 — Option B: Run in Docker (set-and-forget)

This runs the database **and** the agent as containers that keep running in the
background and **auto-restart on reboot**. Make sure `credentials.json`, `token.json`
(from step 6), and a filled-in `.env` exist first.

```powershell
docker compose up -d --build      # build + start db and app in the background
docker compose logs -f app        # watch the agent's logs (Ctrl+C just stops watching)
```

- The container applies migrations automatically on start, then runs the agent with
  polling on.
- It reads `.env` for your keys and `DRY_RUN` / `TELEGRAM_ENABLED`.
- **Stop it:** `docker compose down` (your data persists in the `pgdata` volume).
- **Update after a code change:** `git pull; docker compose up -d --build`.

> Note: `token.json` must exist on disk before `docker compose up` (the container
> mounts it). If you skipped step 6, Docker will create a *folder* named `token.json`
> by mistake — delete it and run step 6.

---

## Part 4 — Option C: Auto-start on login (Windows Task Scheduler)

To have Option A start automatically when you log in:

1. Open **Task Scheduler** → **Create Task**.
2. **Triggers:** New → *At log on*.
3. **Actions:** New → Program: `powershell.exe`; Arguments:
   `-ExecutionPolicy Bypass -File "C:\Users\cni.alad\Desktop\EmailAgent\run.ps1"`;
   Start in: `C:\Users\cni.alad\Desktop\EmailAgent`.
4. Save. (For a truly always-on box, Option B with Docker is usually simpler.)

---

## Part 5 — Verify it's working

```powershell
# Is it up?
Invoke-RestMethod http://127.0.0.1:8000/health      # -> status=ok, dry_run=...
```

Then **send a test email** to the Gmail account it watches — something a person would
reply to, e.g. subject "Quick question", body "Are we still on for Tuesday at 3pm?".
Within ~one poll interval you should get a Telegram card. Tap **Approve** to send,
**Edit** to rewrite (reply with new text, then **Send**), or **Skip** to discard.

Check the database to see what it did:
```powershell
docker compose exec db psql -U agent -d email_agent -c "select substr(message_id,1,10) as msg, status, skip_source from processed_messages order by updated_at desc limit 10;"
```

---

## Part 6 — Troubleshooting

**Nothing shows up on Telegram after sending email.**
Usually one of:
- *The agent isn't running* — check `Invoke-RestMethod http://127.0.0.1:8000/health`.
- *Triage decided "no reply needed"* — vague/blank or statement-like emails are
  skipped by design. Send something that clearly invites a reply. Check the logs for
  `triage … reply=False (…)`.
- *Already processed* — each email is handled exactly once (idempotency). Re-sending
  the *same* message won't re-trigger; send a **new** email.

**Groq error: `403 Access denied. Please check your network settings.`**
Groq blocks some regions. **Turn your VPN off** (or set it to a Groq-supported
country). Alternatively switch providers in `.env` (e.g. point `LLM_BASE_URL` at
OpenRouter/OpenAI and use that key) — the provider seam makes this a config change.

**Gmail: "Access blocked / app not verified" during step 6.**
The Gmail account you signed in with isn't a **Test user**. Add it in Google Cloud
Console → OAuth consent screen → Test users, then retry.

**It stops working after ~a week.**
In OAuth "Testing" mode, refresh tokens expire after **7 days**. Either re-run step 6
to re-authorize, or publish the app to "Production" in the consent screen.

**`docker compose` errors / DB connection refused.**
Make sure **Docker Desktop is running**, then `docker compose up -d --wait db`.

**`uv` not found.**
Install it with `py -m pip install uv` and reopen the shell, or replace `uv ...` with
`py -m uv ...`.

---

## Part 7 — Good to know

- **It never auto-sends.** Every send is a tap (Approve, or Send after Edit).
- **Single owner.** The bot only obeys your `TELEGRAM_CHAT_ID`; it ignores everyone else.
- **Exactly once.** Each email maps to one row in `processed_messages`; failures land
  in a visible `needs_attention` state rather than being lost.
- **Your secrets stay local.** `.env`, `credentials.json`, and `token.json` are all
  git-ignored. If you ever paste a key into a chat or screen-share, rotate it.
- **Backups.** All state lives in the Postgres `pgdata` Docker volume; `docker compose
  down` keeps it, `docker compose down -v` deletes it.
