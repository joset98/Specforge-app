"""Deterministic consistency checks. Messages are Spanish: they are fed back to the agents."""

from collections import Counter

from app.schemas import ArchitectOutput, Issue, Section, Story, TestCase

GHERKIN_KEYWORDS = ("Escenario", "Dado", "Cuando", "Entonces")


def validate(stories: list[Story], arch: ArchitectOutput, tests: list[TestCase]) -> list[Issue]:
    issues: list[Issue] = []

    def add(code: str, owner: Section, message: str) -> None:
        issues.append(Issue(code=code, owner=owner, message=message))

    story_ids = {s.id for s in stories}
    endpoint_ids = {e.id for e in arch.endpoints}
    tables = {t.name: {c.name for c in t.columns} for t in arch.tables}

    for label, owner, ids in (
        ("historia", "product_owner", [s.id for s in stories]),
        ("endpoint", "architect", [e.id for e in arch.endpoints]),
        ("caso de prueba", "qa", [t.id for t in tests]),
    ):
        for dup, n in Counter(ids).items():
            if n > 1:
                add("DUPLICATE_ID", owner,
                    f"El id de {label} {dup} está repetido {n} veces; usa ids únicos.")

    for s in stories:
        missing = [k for k in GHERKIN_KEYWORDS if k not in s.gherkin]
        if missing:
            add("GHERKIN_INVALID", "product_owner",
                f"El Gherkin de {s.id} no contiene: {', '.join(missing)}.")

    covered = {sid for e in arch.endpoints for sid in e.story_ids}
    for sid in sorted(story_ids - covered):
        add("STORY_WITHOUT_ENDPOINT", "architect",
            f"La historia {sid} no está cubierta por ningún endpoint.")

    for e in arch.endpoints:
        unknown = [sid for sid in e.story_ids if sid not in story_ids]
        if unknown:
            add("ENDPOINT_UNKNOWN_STORY", "architect",
                f"El endpoint {e.id} referencia historias inexistentes: {', '.join(unknown)}.")
        for field in (e.request_table, e.response_table):
            if field is not None and field not in tables:
                add("ENDPOINT_UNKNOWN_TABLE", "architect",
                    f"El endpoint {e.id} referencia la tabla inexistente {field}.")

    for t in arch.tables:
        if not any(c.primary_key for c in t.columns):
            add("TABLE_WITHOUT_PK", "architect", f"La tabla {t.name} no tiene clave primaria.")
        for c in t.columns:
            if c.foreign_key is None:
                continue
            ref_table, _, ref_col = c.foreign_key.partition(".")
            if ref_col not in tables.get(ref_table, set()):
                add("FK_BROKEN", "architect",
                    f"La columna {t.name}.{c.name} apunta a {c.foreign_key}, que no existe "
                    "(usa el formato tabla.columna).")

    routes = Counter((e.method, e.path) for e in arch.endpoints)
    for (method, path), n in routes.items():
        if n > 1:
            add("DUPLICATE_ROUTE", "architect",
                f"La ruta {method} {path} está definida {n} veces; unifica o cambia la ruta.")

    tested = {t.endpoint_id for t in tests}
    for eid in sorted(endpoint_ids - tested):
        add("ENDPOINT_WITHOUT_TEST", "qa", f"El endpoint {eid} no tiene ningún caso de prueba.")

    for t in tests:
        bad = [r for r, known in ((t.endpoint_id, endpoint_ids), (t.story_id, story_ids))
               if r not in known]
        if bad:
            add("TEST_UNKNOWN_REF", "qa",
                f"El caso {t.id} referencia ids inexistentes: {', '.join(bad)}.")

    return issues
