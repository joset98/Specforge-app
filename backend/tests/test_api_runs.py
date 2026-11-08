import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.main import app, get_provider_factory, get_quota
from app.providers.base import ProviderError
from app.providers.fake import FakeProvider
from app.rate_limit import QuotaTracker


def parse_sse(text: str) -> list[tuple[str, dict]]:
    events = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


@pytest.fixture
def env(sample_result):
    r = sample_result
    responses = [{"stories": [s.model_dump() for s in r.stories]}, r.architecture.model_dump(),
                 {"tests": [t.model_dump() for t in r.tests]}]
    state = {"quota": QuotaTracker(per_ip=3, global_cap=100), "responses": responses,
             "calls": []}

    def factory(provider, key, settings):
        state["calls"].append((provider, key))
        return FakeProvider(list(state["responses"]))

    app.dependency_overrides[get_provider_factory] = lambda: factory
    app.dependency_overrides[get_quota] = lambda: state["quota"]
    yield TestClient(app), state
    app.dependency_overrides.clear()


def test_health(env):
    client, _ = env
    assert client.get("/api/health").json() == {"status": "ok"}


def test_run_streams_events_in_order(env):
    client, _ = env
    res = client.post("/api/runs", data={"text": "App de veterinaria", "team_context": "Django"})
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(res.text)
    assert [e for e, _ in events][-2:] == ["validation", "result"]
    assert events[-1][1]["input"] == {"text": "App de veterinaria", "team_context": "Django"}


def test_quota_endpoint(env):
    client, _ = env
    assert client.get("/api/quota").json() == {"remaining": 3, "limit": 3}


def test_bad_file_returns_400_and_does_not_consume_quota(env):
    client, _ = env
    res = client.post("/api/runs", files={"file": ("scan.exe", b"MZ", "application/octet-stream")})
    assert res.status_code == 400 and "Unsupported" in res.json()["detail"]
    res = client.post("/api/runs", data={"text": "   "})
    assert res.status_code == 400
    assert client.get("/api/quota").json()["remaining"] == 3


def test_oversized_upload_413(env):
    client, _ = env
    big = b"a" * (5 * 1024 * 1024 + 1)
    res = client.post("/api/runs", files={"file": ("r.txt", big, "text/plain")})
    assert res.status_code == 413


def test_quota_exhausted_429_without_key(env):
    client, _ = env
    for _ in range(3):
        assert client.post("/api/runs", data={"text": "x"}).status_code == 200
    res = client.post("/api/runs", data={"text": "x"})
    assert res.status_code == 429 and res.json()["detail"] == "free_quota_exhausted"


def test_user_key_bypasses_quota(env):
    client, state = env
    headers = {"X-LLM-Key": "sk-user-123456789", "X-LLM-Provider": "openai"}
    for _ in range(4):
        assert client.post("/api/runs", data={"text": "x"}, headers=headers).status_code == 200
    assert state["calls"][-1] == ("openai", "sk-user-123456789")
    assert client.get("/api/quota").json()["remaining"] == 3


def test_provider_setup_error_does_not_consume_quota(env):
    client, _ = env

    def broken(provider, key, settings):
        raise ProviderError("auth", "No API key available for this provider.")

    app.dependency_overrides[get_provider_factory] = lambda: broken
    assert client.post("/api/runs", data={"text": "x"}).status_code == 401
    assert client.get("/api/quota").json()["remaining"] == 3


def test_refine_streams_result(env, sample_result):
    client, state = env
    state["responses"] = [{"tests": [t.model_dump() for t in sample_result.tests]}]
    body = {"result": sample_result.model_dump(), "section": "qa", "feedback": "más errores"}
    res = client.post("/api/refine", json=body)
    assert res.status_code == 200
    assert parse_sse(res.text)[-1][0] == "result"


def test_tampered_result_422(env, sample_result):
    client, _ = env
    body = {"result": sample_result.model_dump(), "section": "hacker", "feedback": "x"}
    assert client.post("/api/refine", json=body).status_code == 422


def test_refine_body_too_large_413(env):
    client, _ = env
    res = client.post("/api/refine", content=b"x" * (1024 * 1024 + 1),
                      headers={"Content-Type": "application/json"})
    assert res.status_code == 413


def test_user_key_never_logged(env, caplog):
    client, state = env
    state["responses"] = [ProviderError("auth")]
    caplog.set_level(logging.DEBUG)
    res = client.post("/api/runs", data={"text": "x"},
                      headers={"X-LLM-Key": "sk-ant-supersecret123"})
    expected = {"code": "auth", "message": ProviderError("auth").message}
    assert parse_sse(res.text)[-1] == ("error", expected)
    logging.getLogger("anything").warning("leak %s", "sk-ant-supersecret123")
    assert "supersecret" not in caplog.text


def test_refine_rejects_oversized_input_text(env, sample_result):
    client, state = env
    body = {"result": sample_result.model_dump(), "section": "qa", "feedback": "x"}
    body["result"]["input"]["text"] = "a" * 30001
    assert client.post("/api/refine", json=body).status_code == 422
    body["result"]["input"]["text"] = "ok"
    body["result"]["input"]["team_context"] = "a" * 2001
    assert client.post("/api/refine", json=body).status_code == 422


def test_body_without_content_length_rejected(env):
    client, _ = env

    def chunks():
        yield b'{"result": '

    res = client.post("/api/refine", content=chunks(), headers={"Content-Type": "application/json"})
    assert res.status_code == 411


def test_free_run_refunded_when_owner_key_fails_before_any_agent(env):
    client, state = env
    state["responses"] = [ProviderError("rate_limited")]
    res = client.post("/api/runs", data={"text": "x"})
    assert parse_sse(res.text)[-1][0] == "error"
    assert client.get("/api/quota").json()["remaining"] == 3


def test_free_run_kept_when_failure_after_an_agent_finished(env, sample_result):
    client, state = env
    state["responses"] = [{"stories": [s.model_dump() for s in sample_result.stories]},
                          ProviderError("upstream")]
    client.post("/api/runs", data={"text": "x"})
    assert client.get("/api/quota").json()["remaining"] == 2
