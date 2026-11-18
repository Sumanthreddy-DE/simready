"""Provider client: retries, quota stop, key lookup, rate limit, prompt hash. No network."""

from __future__ import annotations

import json
from types import SimpleNamespace

import openai
import pytest

if int(openai.__version__.split(".")[0]) >= 3:  # openai 3.0 moved from httpx to httpx2
    import httpx2 as httpx
else:
    import httpx

from simready.bench.prompting import BUILD_PART_TOOL, SYSTEM_PROMPT, build_messages, system_prompt_sha256
from simready.bench.providers import (
    PROVIDERS_JSON,
    InfraError,
    ModelClient,
    Provider,
    QuotaExhausted,
    RateLimiter,
    load_providers,
    resolve_key,
)
from simready.gen.spec import STEPS_MAX

P = Provider("t", "http://x/v1", "m", "BENCH_TEST_KEY", 0, 512, True, {})
REQ = httpx.Request("POST", "http://x/v1/chat/completions")


def _resp(content=None, calls=()):
    tool_calls = [SimpleNamespace(function=SimpleNamespace(name=n, arguments=a)) for n, a in calls]
    msg = SimpleNamespace(content=content, tool_calls=tool_calls or None)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=msg, finish_reason="stop")],
        model="m-2026",
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )


class FakeCompletions:
    def __init__(self, outcomes):
        self.outcomes, self.calls = list(outcomes), []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        out = self.outcomes.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


def _client(outcomes, provider=P, **kw):
    comp = FakeCompletions(outcomes)
    fake = SimpleNamespace(chat=SimpleNamespace(completions=comp))
    return ModelClient(provider, client=fake, sleep=lambda s: None, **kw), comp


def _rate_limited():
    return openai.RateLimitError("slow down", response=httpx.Response(429, request=REQ), body=None)


def test_complete_returns_tool_calls_usage_and_passes_seed():
    client, comp = _client([_resp(calls=[("build_part", json.dumps({"spec": {"steps": []}}))])])
    out = client.complete(build_messages("x"), [BUILD_PART_TOOL], 0.7, seed=3)
    assert out["tool_calls"][0]["name"] == "build_part"
    assert out["usage"] == {"prompt_tokens": 10, "completion_tokens": 5}
    assert out["model_returned"] == "m-2026"
    assert comp.calls[0]["seed"] == 3 and comp.calls[0]["temperature"] == 0.7


def test_seed_not_sent_when_unsupported():
    no_seed = Provider("t", "http://x/v1", "m", "K", 0, 512, False, {})
    client, comp = _client([_resp(content="hi")], provider=no_seed)
    client.complete(build_messages("x"), [BUILD_PART_TOOL], 0.7, seed=3)
    assert "seed" not in comp.calls[0]


def test_transient_errors_retry_then_succeed():
    server = openai.InternalServerError("boom", response=httpx.Response(500, request=REQ), body=None)
    client, comp = _client([server, _rate_limited(), _resp(content="ok")])
    assert client.complete(build_messages("x"), [], 0.7)["content"] == "ok"
    assert len(comp.calls) == 3


def test_persistent_429_means_quota_exhausted():
    client, _ = _client([_rate_limited() for _ in range(3)], max_retries=3)
    with pytest.raises(QuotaExhausted):
        client.complete(build_messages("x"), [], 0.7)


def test_persistent_connection_error_is_infra():
    client, _ = _client([openai.APIConnectionError(request=REQ) for _ in range(3)], max_retries=3)
    with pytest.raises(InfraError):
        client.complete(build_messages("x"), [], 0.7)


def test_empty_or_null_choices_retries_then_raises_infra():
    null_choices = SimpleNamespace(choices=None, model="m-2026", usage=None)
    empty_choices = SimpleNamespace(choices=[], model="m-2026", usage=None)
    null_msg = SimpleNamespace(choices=[SimpleNamespace(message=None, finish_reason="stop")], model="m-2026", usage=None)

    client, comp = _client([null_choices, empty_choices, null_msg, _resp(content="recovered")], max_retries=4)
    assert client.complete(build_messages("x"), [], 0.7)["content"] == "recovered"
    assert len(comp.calls) == 4

    exhausted, comp2 = _client([null_choices, empty_choices], max_retries=2)
    with pytest.raises(InfraError, match="empty choices"):
        exhausted.complete(build_messages("x"), [], 0.7)
    assert len(comp2.calls) == 2


def test_client_error_is_infra_without_retry():
    bad = openai.BadRequestError("bad param", response=httpx.Response(400, request=REQ), body=None)
    client, comp = _client([bad, _resp(content="never")])
    with pytest.raises(InfraError, match="HTTP 400"):
        client.complete(build_messages("x"), [], 0.7)
    assert len(comp.calls) == 1


def test_resolve_key_env_then_dotenv_never_echoes(tmp_path):
    assert resolve_key(P, env={"BENCH_TEST_KEY": "sk-1"}, dotenv_path=tmp_path / ".env") == "sk-1"
    (tmp_path / ".env").write_text("BENCH_TEST_KEY=sk-2\n", encoding="utf-8")
    assert resolve_key(P, env={}, dotenv_path=tmp_path / ".env") == "sk-2"
    with pytest.raises(KeyError) as exc:
        resolve_key(P, env={}, dotenv_path=tmp_path / "missing.env")
    assert "sk-" not in str(exc.value)


def test_rate_limiter_spaces_calls():
    t = {"now": 0.0}
    slept = []
    lim = RateLimiter(60, clock=lambda: t["now"], sleep=slept.append)
    lim.wait()
    lim.wait()
    assert slept == [pytest.approx(1.0)]


def test_bench_tool_drops_agent_only_instructions():
    desc = BUILD_PART_TOOL["function"]["description"]
    assert "analyze_geometry" not in desc and "axis is +Z" in desc
    assert f"at most {STEPS_MAX} steps" in desc  # the PartSpec cap is stated, not hidden (Task 10 smoke)
    assert "(0, 1000]" in desc and "(0, 500]" in desc and "[-10000, 10000]" in desc  # PartSpec bounds stated too
    assert "timeout_seconds" not in BUILD_PART_TOOL["function"]["parameters"]["properties"]
    assert "say so" in SYSTEM_PROMPT
    assert len(system_prompt_sha256()) == 64


@pytest.mark.live_llm  # deselected by default until Task 6-live fills in verified values
def test_providers_json_is_complete():
    providers = load_providers(PROVIDERS_JSON)
    assert {"glm-5.3", "deepseek-v4.1-flash"} <= set(providers)
    for p in providers.values():
        blob = json.dumps(p.__dict__)
        assert "<VERIFY" not in blob, f"{p.alias}: fill in verified values (Task 6 step 6)"
        assert p.key_env and not p.key_env.startswith("sk-")
