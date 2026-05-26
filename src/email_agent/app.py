import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from email_agent.approval import ApprovalListener
from email_agent.config import Settings, load_behavior
from email_agent.db import SessionLocal
from email_agent.gmail_client import GmailClient
from email_agent.logging_setup import configure_logging
from email_agent.memory import NullMemory
from email_agent.pipeline import process_message
from email_agent import provider as provider_module
from email_agent.state import StateRepository
from email_agent.telegram_bot import TelegramClient
from email_agent.trigger.poll import PollTrigger


async def _run_agent(settings: Settings, behavior: dict) -> None:
    gmail = GmailClient(settings=settings)
    memory = NullMemory()
    telegram = None
    if settings.telegram_enabled:
        telegram = TelegramClient(settings.telegram_bot_token, settings.telegram_chat_id)

        @asynccontextmanager
        async def repo_factory():
            async with SessionLocal() as session:
                yield StateRepository(session)

        listener = ApprovalListener(
            telegram=telegram, gmail=gmail, repo_factory=repo_factory,
            chat_id=settings.telegram_chat_id,
        )
        asyncio.create_task(listener.run())

    trigger = PollTrigger(gmail=gmail, interval=settings.poll_interval_seconds)

    async def handler(message_id: str) -> None:
        async with SessionLocal() as session:
            await process_message(
                message_id, gmail=gmail, state=StateRepository(session),
                provider=provider_module.complete, memory=memory, cfg=behavior,
                dry_run=settings.dry_run, triage_model=settings.triage_model,
                draft_model=settings.draft_model, telegram=telegram,
            )

    await trigger.run(handler)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    configure_logging(settings.log_level)
    behavior = load_behavior()
    task = None
    if os.environ.get("AGENT_AUTOSTART", "0") == "1":
        task = asyncio.create_task(_run_agent(settings, behavior))
    yield
    if task:
        task.cancel()


app = FastAPI(title="Email Agent", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "dry_run": Settings().dry_run}
