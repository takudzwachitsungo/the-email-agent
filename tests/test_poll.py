import pytest

from email_agent.trigger.poll import PollTrigger


class FakeGmail:
    def __init__(self, ids):
        self._ids = ids

    async def fetch_unread_ids(self):
        return self._ids


@pytest.mark.asyncio
async def test_poll_once_dispatches_each_id():
    seen = []

    async def handler(mid):
        seen.append(mid)

    trigger = PollTrigger(gmail=FakeGmail(["a", "b", "c"]), interval=0)
    await trigger.poll_once(handler)
    assert seen == ["a", "b", "c"]
