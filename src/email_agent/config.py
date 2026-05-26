from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Secrets and runtime knobs, loaded from environment / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://agent:agent@localhost:5432/email_agent"
    groq_api_key: str = ""
    llm_base_url: str = "https://api.groq.com/openai/v1"
    triage_model: str = "llama-3.1-8b-instant"
    draft_model: str = "llama-3.3-70b-versatile"
    dry_run: bool = True
    poll_interval_seconds: int = 60
    gmail_credentials_path: str = "credentials.json"
    gmail_token_path: str = "token.json"
    log_level: str = "INFO"
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_enabled: bool = False


def load_behavior(path: str | Path = "config.yaml") -> dict[str, Any]:
    """Load editable behavior (persona, prefilter rules) from YAML."""
    p = Path(path)
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text()) or {}
