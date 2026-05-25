from typing import Protocol

from email_agent.models import Email


class Memory(Protocol):
    def get_voice_profile(self) -> str | None: ...
    def get_contact_notes(self, sender: str) -> str | None: ...
    async def find_similar_replies(self, text: str, k: int) -> list[str]: ...
    def record_correction(self, email: Email, drafted: str, sent: str) -> None: ...


class NullMemory:
    """Phase 1: no long-term memory. The injection slot stays empty."""

    def get_voice_profile(self) -> str | None:
        return None

    def get_contact_notes(self, sender: str) -> str | None:
        return None

    async def find_similar_replies(self, text: str, k: int) -> list[str]:
        return []

    def record_correction(self, email: Email, drafted: str, sent: str) -> None:
        return None
