import json

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_export_markdown_download_headers(sample_result):
    res = client.post("/api/export/markdown", json=sample_result.model_dump())
    assert res.status_code == 200
    assert res.headers["content-disposition"] == "attachment; filename=requirements.md"
    assert "erDiagram" in res.text


def test_export_json_roundtrips(sample_result):
    res = client.post("/api/export/json", json=sample_result.model_dump())
    assert json.loads(res.text) == sample_result.model_dump()
    assert res.headers["content-disposition"].endswith("requirements.json")


def test_export_jira_csv(sample_result):
    res = client.post("/api/export/jira-csv", json=sample_result.model_dump())
    assert res.status_code == 200 and res.text.startswith("Summary,Description")


def test_export_unknown_format_404(sample_result):
    assert client.post("/api/export/pdf", json=sample_result.model_dump()).status_code == 404


def test_export_invalid_result_422():
    assert client.post("/api/export/markdown", json={"stories": "nope"}).status_code == 422
