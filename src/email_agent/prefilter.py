from email_agent.models import Email


def should_skip(email: Email, cfg: dict) -> tuple[bool, str | None]:
    """Deterministic, no-LLM skip rules. Returns (skip, reason)."""
    sender = email.sender.lower()

    for allowed in cfg.get("allow_senders", []):
        if allowed.lower() in sender:
            return False, None

    for bad in cfg.get("deny_sender_substrings", []):
        if bad.lower() in sender:
            return True, f"sender matches deny substring '{bad}'"

    for cat in cfg.get("deny_categories", []):
        if cat in email.label_ids:
            return True, f"label {cat}"

    if (email.header("Precedence") or "").lower() == "bulk":
        return True, "Precedence: bulk"
    if email.header("Auto-Submitted") and email.header("Auto-Submitted") != "no":
        return True, "Auto-Submitted header"
    if email.header("List-Unsubscribe"):
        return True, "List-Unsubscribe header (bulk mail)"

    return False, None
