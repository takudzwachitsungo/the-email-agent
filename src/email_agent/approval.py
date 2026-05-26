import asyncio
import logging

from email_agent.telegram_bot import send_keyboard

log = logging.getLogger(__name__)


class ApprovalListener:
    """Long-polls Telegram and routes taps / edit replies to Gmail + state."""

    def __init__(self, *, telegram, gmail, repo_factory, chat_id: str) -> None:
        self.telegram = telegram
        self.gmail = gmail
        self.repo_factory = repo_factory
        self.chat_id = str(chat_id)
        self.awaiting_edit: dict[str, str] = {}
        self._offset = 0
        self._stop = asyncio.Event()

    # ---- routing -------------------------------------------------------
    async def handle_update(self, update: dict) -> None:
        if "callback_query" in update:
            await self._handle_callback(update["callback_query"])
        elif "message" in update:
            await self._handle_message(update["message"])

    async def _handle_callback(self, cq: dict) -> None:
        chat_id = str(cq["message"]["chat"]["id"])
        if chat_id != self.chat_id:
            log.warning("ignoring callback from foreign chat %s", chat_id)
            return
        await self.telegram.answer_callback(cq["id"])
        action, _, mid = cq["data"].partition(":")
        card_id = str(cq["message"]["message_id"])
        if action == "approve":
            await self._finish(mid, card_id, "Sent.")
        elif action == "skip":
            await self._skip(mid, card_id)
        elif action == "edit":
            self.awaiting_edit[chat_id] = mid
            await self.telegram.send_message("Send me the revised reply text.")
        elif action == "send":
            await self._finish(mid, card_id, "Sent (edited).")
        elif action == "cancel":
            await self.telegram.edit_message(card_id, "Cancelled. Draft left in Gmail.")

    async def _handle_message(self, msg: dict) -> None:
        chat_id = str(msg["chat"]["id"])
        if chat_id != self.chat_id:
            return
        text = msg.get("text", "")
        mid = self.awaiting_edit.get(chat_id)
        if mid and text and not text.startswith("/"):
            self.awaiting_edit.pop(chat_id, None)
            await self._apply_edit(mid, text)

    # ---- actions -------------------------------------------------------
    async def _finish(self, mid: str, card_id: str, done_text: str) -> None:
        async with self.repo_factory() as state:
            row = await state.get(mid)
            if not row or row.status != "pending":
                await self.telegram.edit_message(card_id, "This draft is no longer pending.")
                return
            await self.gmail.send_draft(row.draft_id)
            await state.set_sent(mid)
        await self.telegram.edit_message(card_id, done_text)

    async def _skip(self, mid: str, card_id: str) -> None:
        async with self.repo_factory() as state:
            row = await state.get(mid)
            if not row or row.status != "pending":
                await self.telegram.edit_message(card_id, "This draft is no longer pending.")
                return
            await self.gmail.delete_draft(row.draft_id)
            await state.set_rejected(mid)
        await self.telegram.edit_message(card_id, "Skipped (draft deleted).")

    async def _apply_edit(self, mid: str, text: str) -> None:
        async with self.repo_factory() as state:
            row = await state.get(mid)
            if not row or row.status != "pending":
                await self.telegram.send_message("That draft is no longer pending.")
                return
            await self.gmail.update_draft(
                draft_id=row.draft_id, to=row.sender,
                subject=f"Re: {row.subject}", body=text, thread_id=row.thread_id,
            )
        await self.telegram.send_message(
            f"Updated draft. Send it?\n\n{text[:1000]}", reply_markup=send_keyboard(mid)
        )

    # ---- loop ----------------------------------------------------------
    async def run(self) -> None:
        log.info("telegram approval listener started")
        while not self._stop.is_set():
            try:
                updates = await self.telegram.get_updates(self._offset)
                for u in updates:
                    self._offset = u["update_id"] + 1
                    await self.handle_update(u)
            except Exception:
                log.exception("approval listener iteration failed")
                await asyncio.sleep(3)

    def stop(self) -> None:
        self._stop.set()
