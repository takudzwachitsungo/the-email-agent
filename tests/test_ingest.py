import json
from pathlib import Path

from email_agent.ingest import parse_message

FIX = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIX / name).read_text())


def test_parse_plaintext_human():
    email = parse_message(_load("raw_human_question.json"))
    assert email.message_id == "m-human"
    assert email.thread_id == "t-human"
    assert email.sender == "Jane Doe <jane@example.com>"
    assert email.subject == "Are we still on for Tuesday?"
    assert "Tuesday" in email.body
    assert email.header("To") == "me@example.com"


def test_parse_multipart_extracts_text_part():
    email = parse_message(_load("raw_newsletter.json"))
    assert email.body == "Lots of news"
    assert "CATEGORY_PROMOTIONS" in email.label_ids
    assert email.header("Precedence") == "bulk"
