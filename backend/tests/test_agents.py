import pytest
from pydantic import ValidationError

from app.agents.architect import ArchitectAgent
from app.agents.base import AgentContext
from app.agents.product_owner import ProductOwnerAgent
from app.agents.qa import QAAgent
from app.providers.fake import FakeProvider
from app.schemas import Issue


def ctx(r, upto: str) -> AgentContext:
    c = AgentContext(input=r.input)
    if upto in ("architect", "qa"):
        c.stories = r.stories
    if upto == "qa":
        c.architecture = r.architecture
    return c


async def test_architect_prompt_includes_stories_and_team_context(sample_result):
    fake = FakeProvider([sample_result.architecture.model_dump()])
    out = await ArchitectAgent(fake).run(ctx(sample_result, "architect"))
    assert out == sample_result.architecture
    system, user, schema = fake.calls[0]
    assert "## Historias" in user and "US-1" in user
    assert "## Contexto del equipo" in user and "PostgreSQL" in user
    assert "## Requerimiento" in user
    assert "## Feedback del usuario" not in user
    assert "español" in system and schema == "ArchitectOutput"


async def test_team_context_block_omitted_when_empty(sample_result):
    r = sample_result.model_copy(deep=True)
    r.input.team_context = ""
    fake = FakeProvider([{"stories": [s.model_dump() for s in r.stories]}])
    await ProductOwnerAgent(fake).run(ctx(r, "product_owner"))
    assert "## Contexto del equipo" not in fake.calls[0][1]


async def test_feedback_previous_and_issues_included(sample_result):
    fake = FakeProvider([{"tests": [t.model_dump() for t in sample_result.tests]}])
    prev = (await QAAgent(FakeProvider([{"tests": [t.model_dump() for t in sample_result.tests]}])
                          ).run(ctx(sample_result, "qa")))
    issue = Issue(code="ENDPOINT_WITHOUT_TEST", owner="qa", message="falta EP-3")
    await QAAgent(fake).run(ctx(sample_result, "qa"), issues=[issue],
                            feedback="más casos de error", previous=prev)
    user = fake.calls[0][1]
    for block in ("## Resultado anterior", "## Feedback del usuario", "más casos de error",
                  "## Problemas a corregir", "ENDPOINT_WITHOUT_TEST", "## Arquitectura"):
        assert block in user


async def test_schema_error_retries_once_with_error(sample_result):
    good = {"tests": [t.model_dump() for t in sample_result.tests]}
    fake = FakeProvider([{"bad": 1}, good])
    out = await QAAgent(fake).run(ctx(sample_result, "qa"))
    assert len(out.tests) == 3
    assert "## Error de formato" not in fake.calls[0][1]
    assert "## Error de formato" in fake.calls[1][1]


async def test_schema_error_twice_raises(sample_result):
    fake = FakeProvider([{"bad": 1}, {"bad": 2}])
    with pytest.raises(ValidationError):
        await QAAgent(fake).run(ctx(sample_result, "qa"))
