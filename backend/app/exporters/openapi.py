import re

import yaml

from app.schemas import Endpoint, PipelineResult, Table

TYPES: dict[str, dict] = {
    "uuid": {"type": "string", "format": "uuid"},
    "text": {"type": "string"},
    "integer": {"type": "integer"},
    "bigint": {"type": "integer", "format": "int64"},
    "decimal": {"type": "number"},
    "boolean": {"type": "boolean"},
    "date": {"type": "string", "format": "date"},
    "timestamp": {"type": "string", "format": "date-time"},
    "json": {"type": "object"},
}
NO_BODY = {"GET", "DELETE"}


def _component(t: Table) -> dict:
    schema: dict = {"type": "object",
                    "properties": {c.name: dict(TYPES[c.type]) for c in t.columns}}
    required = [c.name for c in t.columns if not c.nullable or c.primary_key]
    if required:
        schema["required"] = required
    return schema


def _operation(e: Endpoint, tables: set[str]) -> dict:
    ref = lambda name: {"$ref": f"#/components/schemas/{name}"}  # noqa: E731
    op: dict = {"operationId": e.id, "summary": e.description, "tags": e.story_ids}
    params = re.findall(r"{([^}/]+)}", e.path)
    if params:
        op["parameters"] = [{"name": p, "in": "path", "required": True,
                             "schema": {"type": "string"}} for p in params]
    # Tables are checked again here: a result with unresolved validator issues may still dangle.
    if e.request_table in tables and e.method not in NO_BODY:
        op["requestBody"] = {"required": True,
                             "content": {"application/json": {"schema": ref(e.request_table)}}}
    response: dict = {"description": "OK"}
    if e.response_table in tables:
        schema = ref(e.response_table)
        if e.response_is_list:
            schema = {"type": "array", "items": schema}
        response["content"] = {"application/json": {"schema": schema}}
    op["responses"] = {"200": response}
    return op


def to_openapi(r: PipelineResult, title: str = "Generated API") -> str:
    tables = {t.name for t in r.architecture.tables}
    paths: dict[str, dict] = {}
    for e in r.architecture.endpoints:
        path = e.path if e.path.startswith("/") else "/" + e.path
        paths.setdefault(path, {})[e.method.lower()] = _operation(e, tables)
    doc = {
        "openapi": "3.1.0",
        "info": {"title": title, "version": "0.1.0",
                 "description": r.input.text[:500]},
        "tags": [{"name": s.id, "description": s.title} for s in r.stories],
        "paths": paths,
        "components": {"schemas": {t.name: _component(t) for t in r.architecture.tables}},
    }
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)
