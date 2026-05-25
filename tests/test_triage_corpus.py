import os
from pathlib import Path

import pytest
import yaml

from email_agent.config import load_behavior
from email_agent.models import Email
from email_agent.provider import complete
from email_agent.triage import classify

CASES = yaml.safe_load((Path(__file__).parent / "fixtures" / "triage_cases.yaml").read_text())


@pytest.mark.skipif(not os.environ.get("GROQ_API_KEY"), reason="needs GROQ_API_KEY (live LLM)")
@pytest.mark.parametrize("case", CASES, ids=[c["subject"] for c in CASES])
@pytest.mark.asyncio
async def test_triage_matches_expectation(case):
    from email_agent.config import Settings
    email = Email(message_id="x", thread_id="x", sender=case["sender"],
                  subject=case["subject"], body=case["body"])
    result = await classify(email, provider=complete, cfg=load_behavior(),
                            model=Settings().triage_model)
    assert result.should_reply == case["expect_reply"], result.reason
