import base64

from email_agent.models import Email


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data.encode()).decode("utf-8", errors="replace")


def _extract_text(payload: dict) -> str:
    """Return the first text/plain body, searching nested parts."""
    mime = payload.get("mimeType", "")
    body = payload.get("body", {})
    if mime == "text/plain" and body.get("data"):
        return _decode(body["data"])
    for part in payload.get("parts", []):
        text = _extract_text(part)
        if text:
            return text
    # Fallback: a bare body on the top level
    if body.get("data"):
        return _decode(body["data"])
    return ""


def parse_message(raw: dict) -> Email:
    """Turn a Gmail `users.messages.get` dict into a cleaned Email."""
    payload = raw.get("payload", {})
    headers = {h["name"]: h["value"] for h in payload.get("headers", [])}
    return Email(
        message_id=raw["id"],
        thread_id=raw["threadId"],
        sender=headers.get("From", ""),
        to=headers.get("To", ""),
        subject=headers.get("Subject", ""),
        body=_extract_text(payload),
        snippet=raw.get("snippet", ""),
        label_ids=raw.get("labelIds", []),
        headers=headers,
    )
