# AI Requirements Generator — Design Spec

**Date:** 2026-11-08
**Status:** Draft, pending review

## 1. Goal

A web app that turns a plain-text software idea (or an uploaded PDF/DOCX) into a structured technical package produced by a pipeline of AI agents:

1. **Product Owner** writes user stories with acceptance criteria in Gherkin.
2. **Architect** proposes a relational data model and the REST API endpoints.
3. **QA** generates test cases from the stories and endpoints.
4. **Validator** (deterministic code, not an LLM) checks the outputs for consistency and sends targeted corrections back to the responsible agent.

The result is not a dead-end document. Teams can:
- **Steer** generation with their own context: stack, conventions, constraints.
- **Refine** any section with written feedback.
- **Ship** the output straight into their workflow:
  - Jira CSV or GitHub Issues;
  - `openapi.yaml`;
  - a PostgreSQL `CREATE TABLE` script.

**Audience:**
- recruiters and technical teams evaluating the work;
- product and dev teams using it to kick off real projects, on the hosted demo or self-hosted with Docker and their own key.

**Success criteria:**
- A visitor opens a link, clicks an example (or types an idea) and sees the full result in under ~60 s, with no signup and no API key.
- A team goes from a requirements doc to Jira/GitHub tickets plus an OpenAPI file and SQL schema in one session.
- An engineer reading the repo sees typed contracts, hand-written orchestration with a self-correction loop, tests that run without spending tokens, and CI.

**Out of scope (YAGNI):** user accounts, database, saved history, background job queues, E2E tests, more than two LLM providers, SQL dialects other than PostgreSQL, direct Jira API integration (CSV import covers it), de-duplication of GitHub issues on re-export.

## 2. Decisions

| Topic | Decision |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2 |
| Frontend | React + Vite + TypeScript |
| Orchestration | Hand-written (no LangChain/LangGraph) |
| LLM | `LLMProvider` interface; `ClaudeProvider` (default, `claude-sonnet-5-5`) and `OpenAIProvider` |
| Structured output | Claude tool use / OpenAI JSON schema, validated with Pydantic |
| Input | Free text, or a PDF (`pypdf`) / DOCX (`python-docx`) upload (max 5 MB), plus optional team context |
| Access | Hybrid: free demo on the owner's key, limited per IP per day; or the visitor's own key (BYOK) |
| Progress | Server-Sent Events (SSE) |
| Language | UI in English; all generated content in Spanish (including Gherkin keywords) |
| Diagrams | Mermaid `erDiagram`, built on the frontend from the Architect's JSON |
| Exports | Built in deterministic backend code (no LLM): Markdown, JSON, Jira CSV, OpenAPI 3.1 YAML, PostgreSQL DDL, GitHub Issues |
| State | Stateless server: the client keeps the `PipelineResult` and sends it back for refine/export |
| Deploy | Backend on Render (Docker), frontend on Vercel; `docker-compose` for self-hosting |
| Visual design | Use the `impeccable` skill in `.agents/skills/` |

## 3. Architecture

```
[React] ──text / file + team context──► [FastAPI] ──► Extractor (PDF/DOCX → text)
   ▲                                                       │
   │ SSE progress events                                   ▼
   └─────────────────────────────────────────────── Orchestrator
                                                      1. ProductOwnerAgent → Stories
                                                      2. ArchitectAgent    → Tables + Endpoints
                                                      3. QAAgent           → TestCases
                                                      4. Validator         → ValidationReport
                                                         └─ on failure: re-run the responsible
                                                            agent + downstream (max 2 rounds)
                                                      ▼
                                                 PipelineResult (JSON)
                                                      │
        refine (section + feedback) ◄─────────────────┤
        exports (md/json/csv/openapi/sql/github) ◄────┘
```

### 3.1 Backend layout

```
backend/
  app/
    main.py              # FastAPI app, routes, CORS
    config.py            # settings from env (keys, limits, model ids)
    schemas.py           # Pydantic contracts (section 4)
    extract.py           # PDF/DOCX/text → plain text
    rate_limit.py        # in-memory per-IP daily counter
    providers/
      base.py            # LLMProvider protocol
      claude.py
      openai.py
      fake.py            # canned responses for tests
    agents/
      base.py            # shared: build prompt, call provider, retry on schema error
      product_owner.py
      architect.py
      qa.py
      prompts/           # one prompt file per agent
    validator.py         # deterministic consistency checks
    orchestrator.py      # full run + refine; yields progress events
    exporters/
      markdown.py
      jira_csv.py
      openapi.py
      sql.py
      github.py          # creates issues via GitHub REST API (httpx)
  tests/
```

Each unit has one job and a typed interface:
- **Agent:** `run(ctx, issues=None, feedback=None, previous=None) -> OutputModel`.
  - `ctx` holds the requirement text, the team context and the upstream outputs.
  - `previous` + `feedback` are used for refinement.
- **Validator:** `validate(result) -> ValidationReport`.
- **Exporter:** a pure function `PipelineResult -> str | bytes`. GitHub is the exception: it is async and takes a token and a repo.
- **Orchestrator:** depends only on the agents and the validator. It never sees provider details.

### 3.2 Provider interface

```python
class LLMProvider(Protocol):
    async def generate_structured(
        self, system: str, user: str, schema: type[BaseModel]
    ) -> BaseModel: ...
```

- **ClaudeProvider:** passes `schema.model_json_schema()` as a single forced tool.
- **OpenAIProvider:** uses its JSON-schema response format.
- Both parse the result with `schema.model_validate`.
- A `ValidationError` is raised to the agent, which retries **once** with the error text appended to the prompt.

### 3.3 Correction loop

1. Run PO → Architect → QA in order. Each agent receives the original requirement, the team context and all upstream outputs.
2. Run the Validator.
3. If there are issues, take the most upstream agent that owns an issue and re-run it and every agent downstream of it, passing each agent its own issues.
   - Example: an issue owned by the Architect re-runs Architect + QA.
4. Stop when the Validator passes or after **2** correction rounds. Return the result in both cases. The report marks unresolved issues and never discards work.

### 3.4 Refinement

The user picks a section (`product_owner` | `architect` | `qa`) and writes feedback, e.g. *"separa el login en dos historias"*.

1. The orchestrator re-runs that agent with its `previous` output and the `feedback`. The prompt says: apply the feedback, keep everything else, keep existing ids stable.
2. The agents downstream of it re-run with the updated upstream output, also receiving their `previous` output so unaffected parts stay stable.
3. The Validator and the correction loop run exactly as in 3.3.
4. Refinement streams the same SSE events and returns a new `PipelineResult`. Each refinement counts as one run against the free quota.

## 4. Data contracts (Pydantic)

```python
class RunInput(BaseModel):
    text: str                   # extracted requirement, truncated to ~30k chars
    team_context: str = ""      # optional, max ~2k chars

class Story(BaseModel):
    id: str                     # "US-1"
    title: str
    as_a: str; i_want: str; so_that: str
    gherkin: str                # Spanish keywords: Característica / Escenario / Dado / Cuando / Entonces
    priority: Literal["alta", "media", "baja"]

ColumnType = Literal["uuid", "text", "integer", "bigint", "decimal",
                     "boolean", "date", "timestamp", "json"]

class Column(BaseModel):
    name: str; type: ColumnType      # closed set → deterministic SQL/OpenAPI mapping
    primary_key: bool = False
    foreign_key: str | None = None   # "table.column"
    nullable: bool = True

class Table(BaseModel):
    name: str; columns: list[Column]

class Endpoint(BaseModel):
    id: str                     # "EP-1"
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    path: str                   # path params as {id}
    description: str
    story_ids: list[str]        # stories it serves
    request_table: str | None = None   # body schema derived from this table
    response_table: str | None = None  # response schema derived from this table
    response_is_list: bool = False

class ArchitectOutput(BaseModel):
    tables: list[Table]; endpoints: list[Endpoint]

class TestCase(BaseModel):
    id: str                     # "TC-1"
    title: str
    endpoint_id: str; story_id: str
    steps: list[str]; expected: str
    type: Literal["happy_path", "edge_case", "error"]

class Issue(BaseModel):
    code: str                   # e.g. "STORY_WITHOUT_ENDPOINT"
    owner: Literal["product_owner", "architect", "qa"]
    message: str                # Spanish, fed back to the agent

class ValidationReport(BaseModel):
    passed: bool
    issues: list[Issue]
    rounds: int                 # correction rounds used

class PipelineResult(BaseModel):
    input: RunInput             # kept so refine/export are self-contained
    stories: list[Story]; architecture: ArchitectOutput
    tests: list[TestCase]; validation: ValidationReport
```

Every `PipelineResult` sent back by the client is re-validated with Pydantic. Size limits are enforced at the API boundary.

## 5. Validator checks

All checks are deterministic.

| Code | Rule | Owner |
|---|---|---|
| `STORY_WITHOUT_ENDPOINT` | every story id appears in some `endpoint.story_ids` | architect |
| `ENDPOINT_UNKNOWN_STORY` | every `endpoint.story_ids` entry exists | architect |
| `ENDPOINT_UNKNOWN_TABLE` | `request_table` / `response_table`, when set, name an existing table | architect |
| `ENDPOINT_WITHOUT_TEST` | every endpoint id has ≥1 test case | qa |
| `TEST_UNKNOWN_REF` | every test's `endpoint_id` / `story_id` exists | qa |
| `FK_BROKEN` | every `foreign_key` points to an existing `table.column` | architect |
| `TABLE_WITHOUT_PK` | every table has a primary key | architect |
| `DUPLICATE_ID` | story / endpoint / test ids are unique | owner of that list |
| `GHERKIN_INVALID` | each `gherkin` contains `Escenario`, `Dado`, `Cuando`, `Entonces` | product_owner |

## 6. Exports

All exporters are pure, deterministic code with no LLM calls.

| Format | Content |
|---|---|
| Markdown | Every section; the ER diagram as a Mermaid block (renders on GitHub) |
| JSON | Raw `PipelineResult` (can be re-imported into the UI to keep refining) |
| Jira CSV | One row per story: `Summary`, `Description` (user story + Gherkin + linked endpoints and test titles), `Issue Type`=Story, `Priority` (alta/media/baja → High/Medium/Low), `Labels`=ai-generated |
| OpenAPI 3.1 YAML | `paths` from endpoints (path params from `{x}`), `components.schemas` from the referenced tables (`ColumnType` → JSON Schema type/format), `tags` from story ids |
| PostgreSQL DDL | `CREATE TABLE` per table, `PRIMARY KEY`, `NOT NULL`, `FOREIGN KEY ... REFERENCES`, ordered by FK dependencies (cycles: tables first, then `ALTER TABLE ADD CONSTRAINT`) |
| GitHub Issues | One issue per story in the repo given by the user; body as in the Jira description; label `ai-generated`. The token is sent in the `X-GitHub-Token` header, used once, and never stored or logged. Returns the created issue URLs. |

## 7. API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | liveness |
| `GET` | `/api/quota` | remaining free runs for the caller's IP |
| `POST` | `/api/runs` | multipart body (`text` or `file`, optional `team_context`). Optional headers `X-LLM-Provider: claude\|openai` and `X-LLM-Key`. Responds with an SSE stream. |
| `POST` | `/api/refine` | JSON `{result, section, feedback}`. Same LLM headers. Responds with an SSE stream. |
| `POST` | `/api/export/{format}` | JSON `PipelineResult`; `format` ∈ `markdown, json, jira-csv, openapi, sql`. Returns a file download. |
| `POST` | `/api/export/github` | JSON `{result, repo: "owner/name"}` + `X-GitHub-Token`. Returns `{issues: [{story_id, url}]}`. |

**SSE events (runs and refine):**
- `stage` — `{agent, status: started|done|retry, detail}`
- `validation` — the report after each round
- `result` — the `PipelineResult`
- `error` — `{code, message}`

## 8. Access and cost control

- **Without `X-LLM-Key`:** the owner's key is used and the per-IP daily counter is enforced (`FREE_RUNS_PER_DAY`, default 3; a run and a refine each count as one). When the counter is exhausted, the server returns **429** and the UI opens "Use your own key".
- **With `X-LLM-Key`:** no limit.
  - The key is used only for that request.
  - It is never stored and never logged. A logging filter masks anything that looks like a key or token.
- **Global safety cap:** `MAX_FREE_RUNS_TOTAL_PER_DAY` across all IPs, so a botnet cannot drain the owner's key.
- `# shortcut: in-memory counter, resets on restart and only works with one instance; move to Redis if scaled out.`
- Input text is truncated at ~30k characters, team context at ~2k, and feedback at ~2k.
- Exports cost no LLM tokens and are not rate-limited beyond a request body size cap.

## 9. Frontend

- **Single page, three zones:**
  1. **Input:**
     - a textarea and a PDF/DOCX dropzone;
     - an optional collapsible **Team context** field, e.g. *"PostgreSQL, NestJS, OAuth"*;
     - "Try an example" buttons (2–3 preloaded ideas);
     - the free-runs counter;
     - a "Use your own key" panel (provider select + key field). The key lives in memory only and is not persisted;
     - an "Import JSON" button to continue refining a previous export.
  2. **Live pipeline:** four steps (PO → Architect → QA → Validator) driven by SSE. Retries are shown inline, e.g. *"Validator: 2 endpoints without tests → re-running QA"*.
  3. **Results tabs:** Stories (Gherkin highlighted, priority badge), Data Model (Mermaid ER), API (endpoint table with linked stories), Tests, Validation (checks, corrections, rounds), and Export.
- **Refine:** each of the Stories, Data Model/API and Tests tabs has a "Refine" box. It sends the feedback, streams progress and then replaces the result.
- **Export tab:**
  - one download button per format;
  - a "Create GitHub issues" form (repo + token; the token is held in memory only), which shows the created issue links.
- The SSE client parses a `fetch` stream, because `EventSource` cannot send a POST body.

## 10. Error handling

| Case | Behavior |
|---|---|
| Invalid / >5 MB file, or a scanned PDF with no text | 400 with a clear message, no LLM call |
| Tampered or oversized `result` sent to refine/export | 422 from Pydantic validation / 413 on size |
| LLM output fails the schema | one retry with the validation error |
| Validator still failing after 2 rounds | return the result and flag unresolved issues |
| Free quota exhausted | 429 and the UI opens the BYOK panel |
| Invalid / out-of-credit user key | `error` event with a clear message; the key is masked |
| GitHub token invalid, no access, or repo not found | 4xx with GitHub's reason; issues already created are still listed |
| SSE connection lost | frontend shows the error and a retry button |

## 11. Testing

- **`FakeProvider`** returns canned outputs, including deliberately broken ones, so the full orchestrator, the correction loop and refinement are tested with zero tokens.
- Unit tests:
  - one test per Validator check;
  - extractors with sample PDF/DOCX fixtures;
  - rate limiter;
  - each exporter against a fixed `PipelineResult` fixture. The OpenAPI output is checked with `openapi-spec-validator`; the SQL output is checked for FK ordering, including a cycle case.
- GitHub exporter tested with a mocked HTTP transport (`httpx.MockTransport`).
- API tests with `TestClient`: quota and 429, BYOK bypass, the SSE event sequence, refine, export downloads, and that keys/tokens never appear in logs.
- Frontend: Vitest for the SSE parser and the Mermaid builder.
- CI (GitHub Actions): ruff + pytest, eslint + vitest, on every push.

## 12. Repo deliverables

- `README.md` in English:
  - demo GIF and "Try it live" link;
  - architecture diagram;
  - design decisions: why hand-written orchestration, why a deterministic validator, why a stateless server;
  - **"Use it in your team"**: self-hosting with Docker, team context, the export formats;
  - how to run it locally.
- `docker-compose.yml` to run the backend and frontend with one command.
- `.env.example` listing every setting.
