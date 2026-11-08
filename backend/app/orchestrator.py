"""Hand-written pipeline: PO → Architect → QA, then a deterministic validator that sends
targeted corrections back to the responsible agent (and everything downstream of it)."""

from collections.abc import AsyncIterator
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

from app.agents.architect import ArchitectAgent
from app.agents.base import Agent, AgentContext
from app.agents.product_owner import ProductOwnerAgent
from app.agents.qa import QAAgent
from app.providers.base import LLMProvider, ProviderError
from app.schemas import (
    Issue,
    PipelineResult,
    ProductOwnerOutput,
    QAOutput,
    RunInput,
    Section,
    TestCase,
    ValidationReport,
)
from app.validator import validate

Event = tuple[Literal["stage", "validation", "result", "error"], dict[str, Any]]
ORDER: list[Section] = ["product_owner", "architect", "qa"]


class _State:
    def __init__(self, input: RunInput):
        self.ctx = AgentContext(input=input)
        self.tests: list[TestCase] = []

    def output_of(self, section: Section) -> BaseModel | None:
        if section == "product_owner":
            return ProductOwnerOutput(stories=self.ctx.stories) if self.ctx.stories else None
        if section == "architect":
            return self.ctx.architecture
        return QAOutput(tests=self.tests) if self.tests else None

    def apply(self, section: Section, out: Any) -> None:
        if section == "product_owner":
            self.ctx.stories = out.stories
        elif section == "architect":
            self.ctx.architecture = out
        else:
            self.tests = out.tests


def _stage(agent: str, status: str, detail: str = "") -> Event:
    return ("stage", {"agent": agent, "status": status, "detail": detail})


class Orchestrator:
    def __init__(self, provider: LLMProvider, max_rounds: int = 2):
        self.max_rounds = max_rounds
        self.agents: dict[Section, Agent] = {
            "product_owner": ProductOwnerAgent(provider),
            "architect": ArchitectAgent(provider),
            "qa": QAAgent(provider),
        }

    async def run(self, input: RunInput) -> AsyncIterator[Event]:
        state = _State(input)

        async def steps() -> AsyncIterator[Event]:
            for section in ORDER:
                async for e in self._step(state, section):
                    yield e

        async for e in self._guarded(state, steps()):
            yield e

    async def _guarded(self, state: _State, steps: AsyncIterator[Event]) -> AsyncIterator[Event]:
        """Run the given agent steps, then the validation loop; turn failures into error events."""
        try:
            async for e in steps:
                yield e
            async for e in self._validation_loop(state):
                yield e
        except ProviderError as exc:
            yield ("error", {"code": exc.code, "message": exc.message})
        except ValidationError:
            yield ("error", {"code": "llm_output_invalid",
                             "message": "The model returned invalid output twice. Try again."})

    async def _step(self, state: _State, section: Section, *, issues: list[Issue] | None = None,
                    feedback: str | None = None, previous: BaseModel | None = None,
                    status: str = "started", detail: str = "") -> AsyncIterator[Event]:
        yield _stage(section, status, detail)
        out = await self.agents[section].run(state.ctx, issues=issues, feedback=feedback,
                                             previous=previous)
        state.apply(section, out)
        yield _stage(section, "done")

    async def _validation_loop(self, state: _State) -> AsyncIterator[Event]:
        rounds = 0
        while True:
            yield _stage("validator", "started")
            issues = validate(state.ctx.stories or [], state.ctx.architecture, state.tests)
            report = ValidationReport(passed=not issues, issues=issues, rounds=rounds)
            yield ("validation", report.model_dump())
            if not issues or rounds == self.max_rounds:
                break
            rounds += 1
            start = min(ORDER.index(i.owner) for i in issues)
            for section in ORDER[start:]:
                own = [i for i in issues if i.owner == section]
                detail = (f"{len(own)} problema(s): {', '.join(sorted({i.code for i in own}))}"
                          if own else "actualizando con los cambios anteriores")
                async for e in self._step(state, section, issues=own or None,
                                          previous=state.output_of(section),
                                          status="retry", detail=detail):
                    yield e
        result = PipelineResult(input=state.ctx.input, stories=state.ctx.stories,
                                architecture=state.ctx.architecture, tests=state.tests,
                                validation=report)
        yield ("result", result.model_dump())
