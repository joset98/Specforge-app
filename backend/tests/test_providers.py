import json

import httpx
import httpx2
import pytest
from pydantic import ValidationError

from app.config import Settings
from app.providers.base import ProviderError
from app.providers.claude import ClaudeProvider
from app.providers.factory import make_provider
from app.providers.fake import FakeProvider
from app.providers.openai import OpenAIProvider
from app.schemas import ProductOwnerOutput

STORY = {"id": "US-1", "title": "t", "as_a": "a", "i_want": "b", "so_that": "c",
         "gherkin": "Escenario: x", "priority": "alta"}
PO = {"stories": [STORY]}


def client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def claude_client(handler) -> httpx2.AsyncClient:
    def adapt(req: httpx2.Request) -> httpx2.Response:
        r = handler(req)
        return httpx2.Response(r.status_code, content=r.content, headers=r.headers)

    return httpx2.AsyncClient(transport=httpx2.MockTransport(adapt))


def claude_message(payload: dict) -> dict:
    return {"id": "msg_1", "type": "message", "role": "assistant", "model": "m",
            "content": [{"type": "tool_use", "id": "tu_1", "name": "submit", "input": payload}],
            "stop_reason": "tool_use", "stop_sequence": None,
            "usage": {"input_tokens": 1, "output_tokens": 1}}


async def test_claude_forces_tool_and_parses():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen.update(json.loads(req.content))
        return httpx.Response(200, json=claude_message(PO))

    p = ClaudeProvider("sk-ant-x", "claude-sonnet-5-5", http_client=claude_client(handler))
    out = await p.generate_structured("sys", "user", ProductOwnerOutput)
    assert isinstance(out, ProductOwnerOutput) and out.stories[0].id == "US-1"
    assert seen["tool_choice"] == {"type": "tool", "name": "submit"}
    assert seen["tools"][0]["input_schema"]["title"] == "ProductOwnerOutput"
    assert seen["system"] == "sys"


async def test_claude_bad_shape_raises_validation_error():
    p = ClaudeProvider("k", "m", http_client=claude_client(
        lambda r: httpx.Response(200, json=claude_message({"nope": 1}))))
    with pytest.raises(ValidationError):
        await p.generate_structured("s", "u", ProductOwnerOutput)


async def test_claude_401_maps_to_auth():
    p = ClaudeProvider("sk-ant-secret", "m", max_retries=0, http_client=claude_client(
        lambda r: httpx.Response(401, json={"type": "error", "error": {
            "type": "authentication_error", "message": "invalid x-api-key"}})))
    with pytest.raises(ProviderError) as e:
        await p.generate_structured("s", "u", ProductOwnerOutput)
    assert e.value.code == "auth" and "sk-ant-secret" not in str(e.value)


def openai_completion(content: str) -> dict:
    return {"id": "c1", "object": "chat.completion", "created": 0, "model": "m",
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": content}}]}


async def test_openai_parses_json_schema_response():
    seen = {}

    def handler(req):
        seen.update(json.loads(req.content))
        return httpx.Response(200, json=openai_completion(json.dumps(PO)))

    p = OpenAIProvider("sk-x", "gpt-x", http_client=client(handler))
    out = await p.generate_structured("sys", "user", ProductOwnerOutput)
    assert out.stories[0].id == "US-1"
    assert seen["response_format"]["type"] == "json_schema"
    assert seen["messages"][0] == {"role": "system", "content": "sys"}


async def test_openai_429_maps_to_rate_limited():
    p = OpenAIProvider("sk-x", "m", max_retries=0, http_client=client(
        lambda r: httpx.Response(429, json={"error": {"message": "quota",
                                                      "type": "insufficient_quota"}})))
    with pytest.raises(ProviderError) as e:
        await p.generate_structured("s", "u", ProductOwnerOutput)
    assert e.value.code == "rate_limited"


async def test_fake_provider_replays_in_order():
    err = ProviderError("auth", "bad")
    f = FakeProvider([PO, err])
    assert (await f.generate_structured("s", "u", ProductOwnerOutput)).stories[0].id == "US-1"
    with pytest.raises(ProviderError):
        await f.generate_structured("s", "u2", ProductOwnerOutput)
    assert f.calls == [("s", "u", "ProductOwnerOutput"), ("s", "u2", "ProductOwnerOutput")]


def test_factory_prefers_user_key():
    s = Settings(anthropic_api_key="owner", openai_model="gpt-x", _env_file=None)
    p = make_provider("openai", "sk-user", s)
    assert isinstance(p, OpenAIProvider) and p.api_key == "sk-user"
    p = make_provider(None, None, s)
    assert isinstance(p, ClaudeProvider) and p.api_key == "owner"


def test_factory_without_any_key_raises_auth():
    with pytest.raises(ProviderError) as e:
        make_provider(None, None, Settings(_env_file=None))
    assert e.value.code == "auth"


async def test_claude_truncated_output_raises_clear_error():
    msg = claude_message({"stories": []})
    msg["stop_reason"] = "max_tokens"
    p = ClaudeProvider("k", "m", http_client=claude_client(lambda r: httpx.Response(200, json=msg)))
    with pytest.raises(ProviderError) as e:
        await p.generate_structured("s", "u", ProductOwnerOutput)
    assert e.value.code == "upstream" and "too long" in e.value.message
