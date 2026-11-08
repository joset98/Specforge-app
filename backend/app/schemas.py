from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field


def normalize_id(v: object) -> object:
    """LLMs write ids inconsistently ("us-1", " US-1 "); normalize so references still link."""
    return v.strip().upper() if isinstance(v, str) else v


Id = Annotated[str, BeforeValidator(normalize_id)]
Section = Literal["product_owner", "architect", "qa"]
ColumnType = Literal[
    "uuid", "text", "integer", "bigint", "decimal", "boolean", "date", "timestamp", "json"
]


# Hard caps for client-supplied results (refine/export); match the default settings.
MAX_TEXT_CHARS = 30000
MAX_CONTEXT_CHARS = 2000


class RunInput(BaseModel):
    text: str = Field(max_length=MAX_TEXT_CHARS)
    team_context: str = Field("", max_length=MAX_CONTEXT_CHARS)


class Story(BaseModel):
    id: Id
    title: str
    as_a: str
    i_want: str
    so_that: str
    gherkin: str
    priority: Literal["alta", "media", "baja"]


class Column(BaseModel):
    name: str
    type: ColumnType
    primary_key: bool = False
    foreign_key: str | None = None  # "table.column"
    nullable: bool = True


class Table(BaseModel):
    name: str
    columns: list[Column]


class Endpoint(BaseModel):
    id: Id
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    path: str
    description: str
    story_ids: list[Id]
    request_table: str | None = None
    response_table: str | None = None
    response_is_list: bool = False


class ArchitectOutput(BaseModel):
    tables: list[Table]
    endpoints: list[Endpoint]


class TestCase(BaseModel):
    __test__ = False  # not a pytest test class

    id: Id
    title: str
    endpoint_id: Id
    story_id: Id
    steps: list[str]
    expected: str
    type: Literal["happy_path", "edge_case", "error"]


class ProductOwnerOutput(BaseModel):
    stories: list[Story]


class QAOutput(BaseModel):
    tests: list[TestCase]


class Issue(BaseModel):
    code: str
    owner: Section
    message: str


class ValidationReport(BaseModel):
    passed: bool
    issues: list[Issue]
    rounds: int


class PipelineResult(BaseModel):
    input: RunInput
    stories: list[Story]
    architecture: ArchitectOutput
    tests: list[TestCase]
    validation: ValidationReport


class RefineRequest(BaseModel):
    result: PipelineResult
    section: Section
    feedback: str = Field(min_length=1, max_length=2000)


class GithubExportRequest(BaseModel):
    result: PipelineResult
    repo: str = Field(pattern=r"^[\w.-]+/[\w.-]+$")
