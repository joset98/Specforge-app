import pytest

from app.schemas import (
    ArchitectOutput,
    Column,
    Endpoint,
    PipelineResult,
    RunInput,
    Story,
    Table,
    TestCase,
    ValidationReport,
)

GHERKIN = (
    "Característica: Reservas\n"
    "  Escenario: reservar una cita, con mascota registrada\n"
    "    Dado un dueño con una mascota\n"
    "    Cuando reserva una cita\n"
    "    Entonces la cita queda confirmada"
)


def build_sample_result() -> PipelineResult:
    stories = [
        Story(id="US-1", title="Registrar mascota", as_a="dueño", i_want="registrar mi mascota",
              so_that="pueda reservar citas", gherkin=GHERKIN, priority="alta"),
        Story(id="US-2", title="Ver mascotas", as_a="dueño", i_want="ver mis mascotas",
              so_that="sepa cuáles tengo", gherkin=GHERKIN, priority="media"),
    ]
    tables = [
        Table(name="owners", columns=[
            Column(name="id", type="uuid", primary_key=True, nullable=False),
            Column(name="name", type="text", nullable=False),
        ]),
        Table(name="pets", columns=[
            Column(name="id", type="uuid", primary_key=True, nullable=False),
            Column(name="owner_id", type="uuid", foreign_key="owners.id", nullable=False),
            Column(name="name", type="text", nullable=False),
            Column(name="birth_date", type="date"),
        ]),
    ]
    endpoints = [
        Endpoint(id="EP-1", method="POST", path="/owners/{ownerId}/pets",
                 description="Registra una mascota", story_ids=["US-1"],
                 request_table="pets", response_table="pets"),
        Endpoint(id="EP-2", method="GET", path="/owners/{ownerId}/pets",
                 description="Lista las mascotas", story_ids=["US-2"],
                 response_table="pets", response_is_list=True),
        Endpoint(id="EP-3", method="GET", path="/owners/{ownerId}/pets/{petId}",
                 description="Detalle de una mascota", story_ids=["US-2"],
                 response_table="pets"),
    ]
    tests = [
        TestCase(id=f"TC-{i}", title=f"Prueba {i}", endpoint_id=f"EP-{i}",
                 story_id="US-1" if i == 1 else "US-2", steps=["paso"], expected="ok",
                 type="happy_path")
        for i in (1, 2, 3)
    ]
    return PipelineResult(
        input=RunInput(text="App de reservas para veterinaria", team_context="PostgreSQL"),
        stories=stories,
        architecture=ArchitectOutput(tables=tables, endpoints=endpoints),
        tests=tests,
        validation=ValidationReport(passed=True, issues=[], rounds=0),
    )


@pytest.fixture
def sample_result() -> PipelineResult:
    return build_sample_result()
