import logging

from email_agent import draft as draft_stage
from email_agent import triage as triage_stage
from email_agent.prefilter import should_skip

log = logging.getLogger(__name__)


async def process_message(
    message_id: str,
    *,
    gmail,
    state,
    provider,
    memory,
    cfg: dict,
    dry_run: bool,
    triage_model: str,
    draft_model: str,
    telegram=None,
) -> None:
    """Run one message through the full pipeline. Never raises."""
    try:
        if await state.already_processed(message_id):
            log.debug("skip %s: already processed", message_id)
            return

        email = await gmail.get_message(message_id)

        skip, reason = should_skip(email, cfg.get("prefilter", {}))
        if skip:
            log.info("prefilter skip %s: %s", message_id, reason)
            await state.record_skip(email, source="prefilter", reason=reason)
            return

        result = await triage_stage.classify(
            email, provider=provider, cfg=cfg, model=triage_model
        )
        log.info("triage %s: reply=%s (%s)", message_id, result.should_reply, result.reason)
        if not result.should_reply:
            await state.record_skip(email, source="triage", reason=result.reason)
            return

        thread = await gmail.fetch_thread(email.thread_id)
        body = await draft_stage.write(
            email, thread=thread, memory=memory, provider=provider,
            cfg=cfg, model=draft_model,
        )

        if dry_run:
            log.info("[dry-run] would draft reply to %s (%d chars)", message_id, len(body))
            return

        draft_id = await gmail.create_draft(
            to=email.sender, subject=f"Re: {email.subject}",
            body=body, thread_id=email.thread_id,
        )
        if telegram is not None:
            tg_id = await telegram.send_approval(
                sender=email.sender, subject=email.subject, body=body,
                message_id=email.message_id,
            )
            await state.set_pending(email, draft_id=draft_id, tg_message_id=tg_id, triage=result)
            log.info("pending approval %s -> draft %s (tg %s)", message_id, draft_id, tg_id)
        else:
            await state.record_drafted(email, draft_id=draft_id, triage=result)
            log.info("drafted %s -> %s", message_id, draft_id)

    except Exception as exc:  # fail loud, never silent
        log.exception("pipeline error on %s", message_id)
        await state.set_needs_attention(message_id, error=repr(exc))
