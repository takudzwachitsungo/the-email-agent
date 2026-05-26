import pytest

from email_agent.gmail_client import GmailClient


class _Exec:
    def __init__(self, result):
        self._result = result

    def execute(self):
        return self._result


class _Messages:
    def __init__(self, store):
        self.store = store

    def list(self, userId, q=None, labelIds=None, maxResults=None):
        return _Exec({"messages": [{"id": "m1"}, {"id": "m2"}]})

    def get(self, userId, id, format=None):
        return _Exec(self.store[id])


class _Users:
    def __init__(self, store):
        self._messages = _Messages(store)

    def messages(self):
        return self._messages


class _FakeService:
    def __init__(self, store):
        self._users = _Users(store)

    def users(self):
        return self._users


@pytest.mark.asyncio
async def test_fetch_unread_ids():
    svc = _FakeService({})
    client = GmailClient(service=svc)
    ids = await client.fetch_unread_ids()
    assert ids == ["m1", "m2"]


class _Drafts:
    def __init__(self):
        self.sent = []
        self.deleted = []
        self.updated = []

    def send(self, userId, body):
        self.sent.append(body)
        return _Exec({"id": body.get("id"), "labelIds": ["SENT"]})

    def delete(self, userId, id):
        self.deleted.append(id)
        return _Exec("")

    def update(self, userId, id, body):
        self.updated.append((id, body))
        return _Exec({"id": id})


def _service_with_drafts():
    svc = _FakeService({})
    drafts = _Drafts()
    svc._users.drafts = lambda: drafts
    return svc, drafts


@pytest.mark.asyncio
async def test_send_draft_calls_api():
    svc, drafts = _service_with_drafts()
    await GmailClient(service=svc).send_draft("d1")
    assert drafts.sent == [{"id": "d1"}]


@pytest.mark.asyncio
async def test_delete_draft_calls_api():
    svc, drafts = _service_with_drafts()
    await GmailClient(service=svc).delete_draft("d1")
    assert drafts.deleted == ["d1"]


@pytest.mark.asyncio
async def test_update_draft_calls_api():
    svc, drafts = _service_with_drafts()
    await GmailClient(service=svc).update_draft(
        draft_id="d1", to="a@b.com", subject="Re: hi", body="hello", thread_id="t1")
    assert drafts.updated[0][0] == "d1"
    assert "message" in drafts.updated[0][1]


@pytest.mark.asyncio
async def test_get_message_returns_parsed_email():
    raw = {"id": "m1", "threadId": "t1",
            "payload": {"headers": [{"name": "From", "value": "a@b.com"}],
                        "mimeType": "text/plain", "body": {"data": "aGk="}}}
    client = GmailClient(service=_FakeService({"m1": raw}))
    email = await client.get_message("m1")
    assert email.sender == "a@b.com"
    assert email.body == "hi"
