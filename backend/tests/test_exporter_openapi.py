import yaml
from fastapi.testclient import TestClient
from openapi_spec_validator import validate

from app.exporters.openapi import to_openapi
from app.main import app


def spec(r):
    return yaml.safe_load(to_openapi(r))


def test_openapi_is_valid(sample_result):
    s = spec(sample_result)
    validate(s)
    assert s["openapi"].startswith("3.1")


def test_multiple_path_params_declared(sample_result):
    op = spec(sample_result)["paths"]["/owners/{ownerId}/pets/{petId}"]["get"]
    assert {p["name"] for p in op["parameters"]} == {"ownerId", "petId"}
    assert all(p["in"] == "path" and p["required"] for p in op["parameters"])
    assert op["operationId"] == "EP-3" and op["tags"] == ["US-2"]


def test_list_response_is_array(sample_result):
    op = spec(sample_result)["paths"]["/owners/{ownerId}/pets"]["get"]
    schema = op["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema == {"type": "array", "items": {"$ref": "#/components/schemas/pets"}}


def test_request_body_and_component_types(sample_result):
    s = spec(sample_result)
    post = s["paths"]["/owners/{ownerId}/pets"]["post"]
    ref = post["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    assert ref == "#/components/schemas/pets"
    pets = s["components"]["schemas"]["pets"]
    assert pets["properties"]["id"] == {"type": "string", "format": "uuid"}
    assert pets["properties"]["birth_date"] == {"type": "string", "format": "date"}
    assert set(pets["required"]) == {"id", "owner_id", "name"}


def test_get_never_has_request_body(sample_result):
    r = sample_result.model_copy(deep=True)
    r.architecture.endpoints[1].request_table = "pets"
    assert "requestBody" not in spec(r)["paths"]["/owners/{ownerId}/pets"]["get"]


def test_export_openapi_route_200(sample_result):
    res = TestClient(app).post("/api/export/openapi", json=sample_result.model_dump())
    assert res.status_code == 200 and "openapi:" in res.text


def test_unresolved_table_refs_still_valid(sample_result):
    r = sample_result.model_copy(deep=True)
    r.architecture.endpoints[0].response_table = "ghosts"
    r.architecture.endpoints[0].path = "owners/{ownerId}/pets"
    validate(spec(r))
