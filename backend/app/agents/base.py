import json
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ValidationError

from app.providers.base import LLMProvider
from app.schemas import ArchitectOutput, Issue, RunInput, Section, Story

PROMPTS = Path(__file__).parent / "prompts"

COMMON_RULES = """
Reglas comunes:
- Escribe TODO el contenido en español.
- En Gherkin usa las palabras clave en español:
  Característica, Escenario, Dado, Cuando, Entonces (y Y / Pero).
- Formatos de id: historias US-n, endpoints EP-n, casos de prueba TC-n.
- Si se te da un "Resultado anterior", conserva sus ids y todo lo que no deba cambiar;
  las piezas nuevas reciben ids nuevos.
- Si hay "Contexto del equipo", respétalo (stack, convenciones, restricciones).
- Si hay "Problemas a corregir", corrígelos todos.
- Responde solo mediante la herramienta/estructura indicada.
"""


def _json(value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump()
    elif isinstance(value, list):
        value = [v.model_dump() if isinstance(v, BaseModel) else v for v in value]
    return json.dumps(value, ensure_ascii=False, indent=1)


@dataclass
class AgentContext:
    input: RunInput
    stories: list[Story] | None = None
    architecture: ArchitectOutput | None = None


class Agent[T: BaseModel]:
    name: ClassVar[Section]
    output_model: ClassVar[type[BaseModel]]
    prompt_file: ClassVar[str]

    def __init__(self, provider: LLMProvider):
        self.provider = provider

    def system_prompt(self) -> str:
        return (PROMPTS / self.prompt_file).read_text(encoding="utf-8") + COMMON_RULES

    def user_prompt(self, ctx: AgentContext, issues: list[Issue] | None,
                    feedback: str | None, previous: T | None) -> str:
        blocks = [("Requerimiento", ctx.input.text),
                  ("Contexto del equipo", ctx.input.team_context),
                  ("Historias", ctx.stories and _json(ctx.stories)),
                  ("Arquitectura", ctx.architecture and _json(ctx.architecture)),
                  ("Resultado anterior", previous and _json(previous)),
                  ("Feedback del usuario", feedback),
                  ("Problemas a corregir", issues and "\n".join(
                      f"- [{i.code}] {i.message}" for i in issues))]
        return "\n\n".join(f"## {title}\n{body}" for title, body in blocks if body)

    async def run(self, ctx: AgentContext, issues: list[Issue] | None = None,
                  feedback: str | None = None, previous: T | None = None) -> T:
        system = self.system_prompt()
        user = self.user_prompt(ctx, issues, feedback, previous)
        try:
            return await self.provider.generate_structured(system, user, self.output_model)
        except ValidationError as e:
            retry = f"{user}\n\n## Error de formato\nTu respuesta no cumplió el esquema:\n{e}"
            return await self.provider.generate_structured(system, retry, self.output_model)
