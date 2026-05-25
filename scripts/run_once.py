"""Process the current unread inbox once, in dry-run, and print decisions.

Usage: uv run python scripts/run_once.py
Requires: token.json (run bootstrap_auth first), GROQ_API_KEY, running Postgres.
"""
import asyncio

from email_agent.config import Settings, load_behavior
from email_agent.db import SessionLocal
from email_agent.gmail_client import GmailClient
from email_agent.logging_setup import configure_logging
from email_agent.memory import NullMemory
from email_agent.pipeline import process_message
from email_agent.provider import complete
from email_agent.state import StateRepository
from email_agent.trigger.poll import PollTrigger


async def main() -> None:
    settings = Settings()
    configure_logging(settings.log_level)
    behavior = load_behavior()
    gmail = GmailClient(settings=settings)
    trigger = PollTrigger(gmail=gmail, interval=0)

    async def handler(mid: str) -> None:
        async with SessionLocal() as session:
            await process_message(
                mid, gmail=gmail, state=StateRepository(session),
                provider=complete, memory=NullMemory(), cfg=behavior,
                dry_run=True,  # force dry-run for this script
                triage_model=settings.triage_model, draft_model=settings.draft_model,
            )

    await trigger.poll_once(handler)


if __name__ == "__main__":
    asyncio.run(main())
