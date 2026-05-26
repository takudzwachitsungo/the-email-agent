import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

_API = "https://api.telegram.org/bot{token}/{method}"
_RETRYABLE = (httpx.TransportError,)


def approval_keyboard(message_id: str) -> dict:
    return {"inline_keyboard": [[
        {"text": "Approve", "callback_data": f"approve:{message_id}"},
        {"text": "Edit", "callback_data": f"edit:{message_id}"},
        {"text": "Skip", "callback_data": f"skip:{message_id}"},
    ]]}


def send_keyboard(message_id: str) -> dict:
    return {"inline_keyboard": [[
        {"text": "Send", "callback_data": f"send:{message_id}"},
        {"text": "Cancel", "callback_data": f"cancel:{message_id}"},
    ]]}


def format_card(*, sender: str, subject: str, body: str) -> str:
    return (
        f"New draft reply\n\nFrom: {sender}\nSubject: {subject}\n\n"
        f"{body[:3500]}"
    )


class TelegramClient:
    def __init__(self, token: str, chat_id: str, http: httpx.AsyncClient | None = None) -> None:
        self.token = token
        self.chat_id = str(chat_id)
        self._http = http or httpx.AsyncClient(timeout=40.0)

    @retry(retry=retry_if_exception_type(_RETRYABLE),
           stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, max=20), reraise=True)
    async def _call(self, method: str, payload: dict) -> dict:
        resp = await self._http.post(_API.format(token=self.token, method=method), json=payload)
        resp.raise_for_status()
        return resp.json().get("result", {})

    async def send_approval(self, *, sender: str, subject: str, body: str, message_id: str) -> str:
        result = await self._call("sendMessage", {
            "chat_id": self.chat_id,
            "text": format_card(sender=sender, subject=subject, body=body),
            "reply_markup": approval_keyboard(message_id),
        })
        return str(result["message_id"])

    async def send_message(self, text: str, *, reply_markup: dict | None = None) -> str:
        payload: dict = {"chat_id": self.chat_id, "text": text}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        result = await self._call("sendMessage", payload)
        return str(result.get("message_id", ""))

    async def edit_message(self, message_id: str, text: str) -> None:
        await self._call("editMessageText", {
            "chat_id": self.chat_id, "message_id": int(message_id), "text": text,
        })

    async def answer_callback(self, callback_id: str, text: str = "") -> None:
        await self._call("answerCallbackQuery", {"callback_query_id": callback_id, "text": text})

    async def get_updates(self, offset: int) -> list[dict]:
        result = await self._call("getUpdates", {"offset": offset, "timeout": 25})
        return result if isinstance(result, list) else []
