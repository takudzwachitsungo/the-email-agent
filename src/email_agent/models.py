from pydantic import BaseModel, Field


class Email(BaseModel):
    """A cleaned inbound message — body + metadata, no quote-stripping."""

    message_id: str
    thread_id: str
    sender: str
    to: str = ""
    subject: str = ""
    body: str = ""
    snippet: str = ""
    label_ids: list[str] = Field(default_factory=list)
    headers: dict[str, str] = Field(default_factory=dict)

    def header(self, name: str) -> str | None:
        """Case-insensitive header lookup."""
        target = name.lower()
        for k, v in self.headers.items():
            if k.lower() == target:
                return v
        return None


class TriageResult(BaseModel):
    should_reply: bool
    category: str = "uncategorized"
    reason: str = ""
