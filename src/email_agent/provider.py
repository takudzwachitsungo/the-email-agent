from functools import lru_cache

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from email_agent.config import Settings


@lru_cache(maxsize=1)
def _client() -> AsyncOpenAI:
    s = Settings()
    return AsyncOpenAI(api_key=s.groq_api_key, base_url=s.llm_base_url)


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, max=30), reraise=True)
async def complete(system: str, user: str, *, model: str, json_mode: bool = False) -> str:
    """Single vendor-agnostic chat call. System = trusted; user = untrusted data."""
    kwargs: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.3,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = await _client().chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""
