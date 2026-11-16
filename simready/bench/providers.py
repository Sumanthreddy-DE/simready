"""Provider config, API-key lookup and a retrying, rate-limited chat client.

Keys are looked up by env-var NAME (environment first, then repo .env) and
are never logged or printed. Retry policy: 429 and transient errors back off
exponentially; if every try was a 429 the daily quota is assumed spent
(QuotaExhausted -> the runner stops cleanly). Other 4xx are config bugs:
no retry, InfraError.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
PROVIDERS_JSON = Path(__file__).resolve().parent / "providers.json"


class InfraError(Exception):
    """API failure after retries; the attempt is excluded and retried on resume."""


class QuotaExhausted(Exception):
    """Every retry hit HTTP 429: stop the run, resume tomorrow."""


@dataclass
class Provider:
    alias: str
    base_url: str
    model: str
    key_env: str
    rpm: int
    max_tokens: int
    supports_seed: bool
    extra_body: dict = field(default_factory=dict)


def load_providers(path: str | Path = PROVIDERS_JSON) -> dict[str, Provider]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return {alias: Provider(alias=alias, **cfg) for alias, cfg in raw.items()}


def resolve_key(
    provider: Provider,
    env: Mapping[str, str] = os.environ,
    dotenv_path: Path = REPO_ROOT / ".env",
) -> str:
    if env.get(provider.key_env):
        return env[provider.key_env]
    if dotenv_path.exists():
        from dotenv import dotenv_values

        value = dotenv_values(dotenv_path).get(provider.key_env)
        if value:
            return value
    raise KeyError(f"API key variable {provider.key_env} is not set (environment or .env)")


class RateLimiter:
    """Spaces call starts at least 60/rpm seconds apart, across threads."""

    def __init__(self, rpm: int, clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], Any] = time.sleep):
        self.interval = 60.0 / rpm if rpm > 0 else 0.0
        self._clock, self._sleep = clock, sleep
        self._next = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = self._clock()
            start = max(now, self._next)
            self._next = start + self.interval
        if start > now:
            self._sleep(start - now)


def _reply(resp: Any, latency_s: float) -> dict:
    choice = resp.choices[0]
    msg = choice.message
    usage = resp.usage
    return {
        "tool_calls": [
            {"name": tc.function.name, "arguments": tc.function.arguments} for tc in (msg.tool_calls or [])
        ],
        "content": msg.content,
        "finish_reason": choice.finish_reason,
        "model_returned": getattr(resp, "model", None),
        "usage": (
            {"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens}
            if usage is not None
            else None
        ),
        "latency_s": round(latency_s, 3),
    }


class ModelClient:
    def __init__(
        self,
        provider: Provider,
        client: Any = None,
        sleep: Callable[[float], Any] = time.sleep,
        max_retries: int = 6,
        initial_backoff: float = 2.0,
        max_backoff: float = 120.0,
    ):
        self.provider = provider
        if client is None:
            from openai import OpenAI

            # SDK retries off: our loop owns retry counting and quota detection.
            client = OpenAI(api_key=resolve_key(provider), base_url=provider.base_url, timeout=300, max_retries=0)
        self.client = client
        self.limiter = RateLimiter(provider.rpm, sleep=sleep)
        self._sleep = sleep
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff

    def complete(self, messages: list[dict], tools: list[dict], temperature: float, seed: int | None = None) -> dict:
        import openai

        kwargs: dict[str, Any] = {
            "model": self.provider.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": self.provider.max_tokens,
        }
        if tools:
            kwargs.update(tools=tools, tool_choice="auto")
        if seed is not None and self.provider.supports_seed:
            kwargs["seed"] = seed
        if self.provider.extra_body:
            kwargs["extra_body"] = self.provider.extra_body

        backoff = self.initial_backoff
        rate_limited = 0
        last = ""
        for attempt in range(1, self.max_retries + 1):
            self.limiter.wait()
            started = time.monotonic()
            try:
                resp = self.client.chat.completions.create(**kwargs)
            except openai.RateLimitError as exc:
                rate_limited += 1
                last = f"HTTP 429: {exc}"
            except (openai.APIConnectionError, openai.InternalServerError) as exc:
                last = f"{type(exc).__name__}: {exc}"
            except openai.APIStatusError as exc:
                raise InfraError(f"HTTP {exc.status_code}: {exc}") from exc
            else:
                return _reply(resp, time.monotonic() - started)
            if attempt < self.max_retries:
                self._sleep(min(backoff, self.max_backoff))
                backoff *= 2
        if rate_limited == self.max_retries:
            raise QuotaExhausted(last)
        raise InfraError(last)
