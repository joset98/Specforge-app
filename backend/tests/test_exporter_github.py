import json
import logging

import httpx
from fastapi.testclient import TestClient

from app.exporters.github import create_issues
from app.main import app, get_http_client

TOKEN = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123"


def gh_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def ok_handler(seen):
    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        n = len(seen)
        return httpx.Response(201, json={"html_url": f"https://github.com/o/r/issues/{n}"})
    return handler


async def test_creates_one_issue_per_story(sample_result):
    seen: list[httpx.Request] = []
    created, error, _ = await create_issues(sample_result, "o/r", TOKEN,
                                            gh_client(ok_handler(seen)))
    assert error is None
    assert created == [{"story_id": "US-1", "url": "https://github.com/o/r/issues/1"},
                       {"story_id": "US-2", "url": "https://github.com/o/r/issues/2"}]
    assert str(seen[0].url) == "https://api.github.com/repos/o/r/issues"
    assert seen[0].headers["authorization"] == f"Bearer {TOKEN}"
    body = json.loads(seen[0].content)
    assert body["title"] == "[US-1] Registrar mascota" and body["labels"] == ["ai-generated"]
    assert "Escenario" in body["body"]


async def test_stops_on_error_and_reports_created(sample_result):
    calls = []

    def handler(req):
        calls.append(req)
        if len(calls) == 1:
            return httpx.Response(201, json={"html_url": "https://github.com/o/r/issues/1"})
        return httpx.Response(404, json={"message": "Not Found"})

    created, error, status = await create_issues(sample_result, "o/r", TOKEN, gh_client(handler))
    assert len(created) == 1 and error == "Not Found" and status == 404


def _client(handler):
    app.dependency_overrides[get_http_client] = lambda: gh_client(handler)
    return TestClient(app)


def test_route_requires_token_400(sample_result):
    client = _client(ok_handler([]))
    res = client.post("/api/export/github", json={"result": sample_result.model_dump(),
                                                  "repo": "o/r"})
    app.dependency_overrides.clear()
    assert res.status_code == 400


def test_route_rejects_bad_repo_422(sample_result):
    client = _client(ok_handler([]))
    res = client.post("/api/export/github", headers={"X-GitHub-Token": TOKEN},
                      json={"result": sample_result.model_dump(), "repo": "../../etc"})
    app.dependency_overrides.clear()
    assert res.status_code == 422


def test_route_success_and_partial_failure(sample_result):
    client = _client(ok_handler([]))
    body = {"result": sample_result.model_dump(), "repo": "o/r"}
    res = client.post("/api/export/github", headers={"X-GitHub-Token": TOKEN}, json=body)
    assert res.status_code == 200 and len(res.json()["issues"]) == 2
    client = _client(lambda r: httpx.Response(401, json={"message": "Bad credentials"}))
    res = client.post("/api/export/github", headers={"X-GitHub-Token": TOKEN}, json=body)
    app.dependency_overrides.clear()
    assert res.status_code == 401
    assert res.json() == {"issues": [], "error": "Bad credentials"}


def test_route_network_failure_502(sample_result):
    def boom(req):
        raise httpx.ConnectError("down")

    client = _client(boom)
    res = client.post("/api/export/github", headers={"X-GitHub-Token": TOKEN},
                      json={"result": sample_result.model_dump(), "repo": "o/r"})
    app.dependency_overrides.clear()
    assert res.status_code == 502 and res.json()["error"] == "Could not reach GitHub."


def test_token_not_in_logs(sample_result, caplog):
    caplog.set_level(logging.DEBUG)
    client = _client(lambda r: httpx.Response(401, json={"message": "Bad credentials"}))
    client.post("/api/export/github", headers={"X-GitHub-Token": TOKEN},
                json={"result": sample_result.model_dump(), "repo": "o/r"})
    app.dependency_overrides.clear()
    assert TOKEN not in caplog.text
