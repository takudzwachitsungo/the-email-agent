from email_agent.models import Email
from email_agent.prefilter import should_skip

CFG = {
    "deny_sender_substrings": ["no-reply", "noreply"],
    "deny_categories": ["CATEGORY_PROMOTIONS"],
    "allow_senders": ["vip@example.com"],
}


def _email(**kw) -> Email:
    base = dict(message_id="m", thread_id="t", sender="jane@example.com")
    base.update(kw)
    return Email(**base)


def test_pass_normal_human():
    skip, reason = should_skip(_email(), CFG)
    assert skip is False and reason is None


def test_skip_no_reply_sender():
    skip, reason = should_skip(_email(sender="no-reply@x.com"), CFG)
    assert skip is True and "no-reply" in reason


def test_skip_promotions_category():
    skip, reason = should_skip(_email(label_ids=["CATEGORY_PROMOTIONS"]), CFG)
    assert skip is True and "PROMOTIONS" in reason


def test_skip_bulk_precedence():
    skip, reason = should_skip(_email(headers={"Precedence": "bulk"}), CFG)
    assert skip is True and "bulk" in reason


def test_allowlist_overrides():
    skip, reason = should_skip(
        _email(sender="vip@example.com", headers={"Precedence": "bulk"}), CFG
    )
    assert skip is False
