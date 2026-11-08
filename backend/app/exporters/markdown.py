from app.schemas import ArchitectOutput, PipelineResult, Story


def er_diagram(arch: ArchitectOutput) -> str:
    """Mermaid erDiagram. Keep in sync with frontend/src/lib/mermaid.ts (toErDiagram)."""
    lines = ["erDiagram"]
    for t in arch.tables:
        lines.append(f"    {t.name} {{")
        for c in t.columns:
            keys = ", ".join(k for k, on in (("PK", c.primary_key), ("FK", c.foreign_key)) if on)
            lines.append(f"        {c.type} {c.name}{' ' + keys if keys else ''}")
        lines.append("    }")
    for t in arch.tables:
        for c in t.columns:
            if c.foreign_key:
                parent = c.foreign_key.partition(".")[0]
                lines.append(f'    {parent} ||--o{{ {t.name} : "{c.name}"')
    return "\n".join(lines)


def story_body(r: PipelineResult, story: Story) -> str:
    """Ticket description shared by the Jira and GitHub exports."""
    endpoints = [e for e in r.architecture.endpoints if story.id in e.story_ids]
    tests = [t for t in r.tests if t.story_id == story.id]
    parts = [f"Como {story.as_a}, quiero {story.i_want}, para {story.so_that}.",
             "", story.gherkin]
    if endpoints:
        parts += ["", "Endpoints:"] + [f"- {e.method} {e.path} ({e.id})" for e in endpoints]
    if tests:
        parts += ["", "Tests:"] + [f"- {t.id}: {t.title}" for t in tests]
    return "\n".join(parts)


def _cell(text: str) -> str:
    return text.replace("|", "\|").replace("\n", " ")


def to_markdown(r: PipelineResult) -> str:
    out = ["# Requerimiento", "", r.input.text, ""]
    if r.input.team_context:
        out += ["**Contexto del equipo:** " + r.input.team_context, ""]
    out += ["## Historias de usuario", ""]
    for s in r.stories:
        out += [f"### {s.id} · {s.title} (prioridad {s.priority})", "",
                f"Como {s.as_a}, quiero {s.i_want}, para {s.so_that}.", "",
                "```gherkin", s.gherkin, "```", ""]
    out += ["## Modelo de datos", "", "```mermaid", er_diagram(r.architecture), "```", ""]
    out += ["## API", "", "| Id | Método | Ruta | Descripción | Historias |",
            "|---|---|---|---|---|"]
    out += [f"| {e.id} | `{e.method}` | `{e.path}` | {_cell(e.description)} | "
            f"{', '.join(e.story_ids)} |" for e in r.architecture.endpoints]
    out += ["", "## Casos de prueba", ""]
    for t in r.tests:
        out += [f"### {t.id} · {t.title} ({t.type})", "",
                f"Endpoint {t.endpoint_id} · Historia {t.story_id}", ""]
        out += [f"{i}. {step}" for i, step in enumerate(t.steps, 1)]
        out += ["", f"**Resultado esperado:** {t.expected}", ""]
    v = r.validation
    status = "Aprobada" if v.passed else "Con problemas"
    out += ["## Validación", "", f"{status} tras {v.rounds} ronda(s) de corrección.", ""]
    out += [f"- [{i.code}] {i.message}" for i in v.issues]
    return "\n".join(out).rstrip() + "\n"
