import csv
import io

from app.exporters.jira_csv import to_jira_csv
from app.exporters.markdown import er_diagram, story_body, to_markdown


def test_markdown_contains_mermaid_and_gherkin(sample_result):
    md = to_markdown(sample_result)
    assert "```mermaid\nerDiagram" in md and "```gherkin\nCaracterística" in md
    for heading in ("# Requerimiento", "## Historias de usuario", "## Modelo de datos", "## API",
                    "## Casos de prueba", "## Validación"):
        assert heading in md
    assert "`POST` | `/owners/{ownerId}/pets`" in md


def test_er_diagram_relation(sample_result):
    d = er_diagram(sample_result.architecture)
    assert d.startswith("erDiagram")
    assert 'owners ||--o{ pets : "owner_id"' in d
    assert "uuid owner_id FK" in d and "uuid id PK" in d


def test_story_body_links_endpoints_and_tests(sample_result):
    body = story_body(sample_result, sample_result.stories[1])
    assert "Como dueño, quiero ver mis mascotas" in body
    assert "GET /owners/{ownerId}/pets" in body and "TC-2" in body


def test_jira_csv_roundtrips_commas_and_newlines(sample_result):
    rows = list(csv.DictReader(io.StringIO(to_jira_csv(sample_result))))
    assert len(rows) == 2
    assert list(rows[0]) == ["Summary", "Description", "Issue Type", "Priority", "Labels"]
    assert rows[0]["Summary"] == "[US-1] Registrar mascota"
    assert "reservar una cita, con mascota registrada\n" in rows[0]["Description"]
    assert (rows[0]["Priority"], rows[1]["Priority"]) == ("High", "Medium")
    assert rows[0]["Issue Type"] == "Story" and rows[0]["Labels"] == "ai-generated"
