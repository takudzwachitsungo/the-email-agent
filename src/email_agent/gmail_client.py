import asyncio
import base64
import os
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from email_agent.config import Settings
from email_agent.ingest import parse_message
from email_agent.models import Email

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def _load_service(settings: Settings):
    """Build an authenticated Gmail service from cached token / OAuth flow."""
    creds = None
    if os.path.exists(settings.gmail_token_path):
        creds = Credentials.from_authorized_user_file(settings.gmail_token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                settings.gmail_credentials_path, SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(settings.gmail_token_path, "w") as f:
            f.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def bootstrap_auth() -> None:
    """One-shot: run the OAuth flow to create token.json. Run manually once."""
    _load_service(Settings())
    print("token.json written.")


class GmailClient:
    def __init__(self, service=None, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self.service = service or _load_service(self.settings)

    async def fetch_unread_ids(self) -> list[str]:
        def _call():
            resp = (
                self.service.users()
                .messages()
                .list(userId="me", q="is:unread -in:chats", labelIds=["INBOX"], maxResults=25)
                .execute()
            )
            return [m["id"] for m in resp.get("messages", [])]

        return await asyncio.to_thread(_call)

    async def get_message(self, message_id: str) -> Email:
        def _call():
            return (
                self.service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )

        raw = await asyncio.to_thread(_call)
        return parse_message(raw)

    async def fetch_thread(self, thread_id: str) -> list[Email]:
        def _call():
            resp = self.service.users().threads().get(userId="me", id=thread_id, format="full").execute()
            return [parse_message(m) for m in resp.get("messages", [])]

        return await asyncio.to_thread(_call)

    async def create_draft(self, *, to: str, subject: str, body: str, thread_id: str) -> str:
        def _call():
            mime = MIMEText(body)
            mime["To"] = to
            mime["Subject"] = subject
            raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
            draft = (
                self.service.users()
                .drafts()
                .create(userId="me", body={"message": {"raw": raw, "threadId": thread_id}})
                .execute()
            )
            return draft["id"]

        return await asyncio.to_thread(_call)

    async def send_draft(self, draft_id: str) -> None:
        def _call():
            self.service.users().drafts().send(userId="me", body={"id": draft_id}).execute()

        await asyncio.to_thread(_call)

    async def delete_draft(self, draft_id: str) -> None:
        def _call():
            self.service.users().drafts().delete(userId="me", id=draft_id).execute()

        await asyncio.to_thread(_call)

    async def update_draft(self, *, draft_id: str, to: str, subject: str, body: str,
                           thread_id: str) -> None:
        def _call():
            mime = MIMEText(body)
            mime["To"] = to
            mime["Subject"] = subject
            raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
            self.service.users().drafts().update(
                userId="me", id=draft_id,
                body={"message": {"raw": raw, "threadId": thread_id}},
            ).execute()

        await asyncio.to_thread(_call)
