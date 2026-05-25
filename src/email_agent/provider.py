from functools import lru_cache

from openai import (
    APIConnectionError,
    AsyncOpenAI,
    InternalServerError,
    RateLimitError,
)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from email_agent.config import Settings

# Only transient failures are worth retrying. Auth (401), permission/geo (403),
# and bad-request (400) errors are permanent — retrying them just wastes time.
_RETRYABLE = (RateLimitError, APIConnectionError, InternalServerError)


@lru_cache(maxsize=1)
def _client() -> AsyncOpenAI:
    s = Settings()
    return AsyncOpenAI(api_key=s.groq_api_key, base_url=s.llm_base_url)


@retry(
    retry=retry_if_exception_type(_RETRYABLE),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, max=30),
    reraise=True,
)
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
