from app.orchestrator import Orchestrator
from app.providers.base import ProviderError
from app.providers.fake import FakeProvider


def outputs(r):
    po = {"stories": [s.model_dump() for s in r.stories]}
    arch = r.architecture.model_dump()
    qa = {"tests": [t.model_dump() for t in r.tests]}
    return po, arch, qa


async def collect(gen):
    return [e async for e in gen]


def validations(events):
    return [d for t, d in events if t == "validation"]


async def test_happy_path_events(sample_result):
    po, arch, qa = outputs(sample_result)
    events = await collect(Orchestrator(FakeProvider([po, arch, qa])).run(sample_result.input))
    types = [t for t, _ in events]
    assert types[:6] == ["stage"] * 6
    assert types[-2:] == ["validation", "result"]
    v = validations(events)[-1]
    assert v["passed"] is True and v["rounds"] == 0
    assert events[-1][1]["validation"]["passed"] is True
    assert events[-1][1]["input"]["text"] == sample_result.input.text


async def test_qa_issue_reruns_only_qa(sample_result):
    po, arch, qa = outputs(sample_result)
    broken_qa = {"tests": qa["tests"][:2]}
    fake = FakeProvider([po, arch, broken_qa, qa])
    events = await collect(Orchestrator(fake).run(sample_result.input))
    assert len(fake.calls) == 4
    assert fake.calls[3][2] == "QAOutput"
    assert "## Problemas a corregir" in fake.calls[3][1]
    assert "ENDPOINT_WITHOUT_TEST" in fake.calls[3][1]
    first, last = validations(events)
    assert first["passed"] is False and last["passed"] is True and last["rounds"] == 1
    assert ("stage", {"agent": "qa", "status": "retry",
                      "detail": "1 problema(s): ENDPOINT_WITHOUT_TEST"}) in events


async def test_architect_issue_reruns_architect_and_qa(sample_result):
    po, arch, qa = outputs(sample_result)
    broken = sample_result.architecture.model_copy(deep=True)
    broken.tables[0].columns[0].primary_key = False
    fake = FakeProvider([po, broken.model_dump(), qa, arch, qa])
    events = await collect(Orchestrator(fake).run(sample_result.input))
    assert [c[2] for c in fake.calls[3:]] == ["ArchitectOutput", "QAOutput"]
    assert "TABLE_WITHOUT_PK" in fake.calls[3][1]
    assert "## Problemas a corregir" not in fake.calls[4][1]
    assert validations(events)[-1]["passed"] is True


async def test_gives_up_after_two_rounds_and_still_returns_result(sample_result):
    po, arch, qa = outputs(sample_result)
    broken_qa = {"tests": qa["tests"][:2]}
    fake = FakeProvider([po, arch, broken_qa, broken_qa, broken_qa])
    events = await collect(Orchestrator(fake).run(sample_result.input))
    v = validations(events)[-1]
    assert v["rounds"] == 2 and v["passed"] is False
    assert events[-1][0] == "result"
    assert events[-1][1]["validation"]["issues"][0]["code"] == "ENDPOINT_WITHOUT_TEST"


async def test_provider_error_emits_error_event(sample_result):
    fake = FakeProvider([ProviderError("auth", "bad key")])
    events = await collect(Orchestrator(fake).run(sample_result.input))
    assert events[-1] == ("error", {"code": "auth", "message": "bad key"})
    assert "result" not in [t for t, _ in events]


async def test_invalid_output_twice_emits_error(sample_result):
    fake = FakeProvider([{"bad": 1}, {"bad": 2}])
    events = await collect(Orchestrator(fake).run(sample_result.input))
    assert events[-1][0] == "error" and events[-1][1]["code"] == "llm_output_invalid"


async def test_refine_architect_reruns_architect_then_qa_with_previous(sample_result):
    _, arch, qa = outputs(sample_result)
    fake = FakeProvider([arch, qa])
    events = await collect(Orchestrator(fake).refine(sample_result, "architect", "usa soft delete"))
    assert [c[2] for c in fake.calls] == ["ArchitectOutput", "QAOutput"]
    arch_user, qa_user = fake.calls[0][1], fake.calls[1][1]
    assert "## Feedback del usuario" in arch_user and "usa soft delete" in arch_user
    assert "## Resultado anterior" in arch_user
    assert "## Resultado anterior" in qa_user and "## Feedback del usuario" not in qa_user
    result = events[-1][1]
    assert result["stories"] == [s.model_dump() for s in sample_result.stories]
    assert validations(events)[-1]["passed"] is True


async def test_refine_qa_only_one_call(sample_result):
    _, _, qa = outputs(sample_result)
    fake = FakeProvider([qa])
    events = await collect(Orchestrator(fake).refine(sample_result, "qa", "más errores"))
    assert len(fake.calls) == 1 and events[-1][0] == "result"


async def test_refine_runs_correction_loop(sample_result):
    _, _, qa = outputs(sample_result)
    fake = FakeProvider([{"tests": qa["tests"][:2]}, qa])
    events = await collect(Orchestrator(fake).refine(sample_result, "qa", "menos casos"))
    assert len(fake.calls) == 2
    assert "## Problemas a corregir" in fake.calls[1][1]
    assert validations(events)[-1]["rounds"] == 1


async def test_unexpected_exception_emits_generic_error(sample_result):
    fake = FakeProvider([RuntimeError("boom")])
    events = await collect(Orchestrator(fake).run(sample_result.input))
    assert events[-1][0] == "error" and events[-1][1]["code"] == "internal"
    assert "boom" not in events[-1][1]["message"]
