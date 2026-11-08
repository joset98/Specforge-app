# AI Requirements Generator — Design Spec

**Date:** 2026-11-08
**Status:** Draft, pending review

## 1. Goal

A portfolio web app that turns a plain-text software idea (or an uploaded PDF/DOCX) into a structured technical package produced by a pipeline of AI agents:

1. **Product Owner** writes user stories with acceptance criteria in Gherkin.
2. **Architect** proposes a relational data model and the REST API endpoints.
3. **QA** generates test cases from the stories and endpoints.
4. **Validator** (deterministic code, not an LLM) checks the outputs for consistency and sends targeted corrections back to the responsible agent.

**Audience:** recruiters and technical teams.

**Success criteria:**
- A visitor opens a link, clicks an example (or types an idea) and sees the full result in under ~60 s, with no signup and no API key.
- An engineer reading the repo sees typed contracts, hand-written orchestration with a self-correction loop, tests that run without spending tokens, and CI.

**Out of scope (YAGNI):** user accounts, database, saved history, background job queues, E2E tests, more than two LLM providers.

## 2. Decisions

| Topic | Decision |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2 |
| Frontend | React + Vite + TypeScript |
| Orchestration | Hand-written (no LangChain/LangGraph) |
| LLM | `LLMProvider` interface; `ClaudeProvider` (default, `claude-sonnet-5-5`) and `OpenAIProvider` |
| Structured output | Claude tool use / OpenAI JSON schema, validated with Pydantic |
| Input | Free text, or a PDF (`pypdf`) / DOCX (`python-docx`) upload, max 5 MB |
| Access | Hybrid: free demo on the owner's key, limited per IP per day; or the visitor's own key (BYOK) |
| Progress | Server-Sent Events (SSE) |
| Language | UI in English; all generated content in Spanish (including Gherkin keywords) |
| Diagrams | Mermaid `erDiagram`, built on the frontend from the Architect's JSON |
| Deploy | Backend on Render (Docker), frontend on Vercel |
| Visual design | Use the `impeccable` skill in `.agents/skills/` |

## 3. Architecture

```
[React] ──text / file──► [FastAPI] ──► Extractor (PDF/DOCX → text)
   ▲                                        │
   │ SSE progress events                    ▼
   └──────────────────────────────── Orchestrator
                                       1. ProductOwnerAgent → Stories
                                       2. ArchitectAgent    → DataModel + Endpoints
                                       3. QAAgent           → TestCases
                                       4. Validator         → ValidationReport
                                          └─ on failure: re-run only the
                                             responsible agent with the
                                             issues (max 2 correction rounds)
                                       ▼
                                  PipelineResult (JSON)
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
    orchestrator.py      # runs the pipeline, yields progress events
  tests/
```

Each unit has one job and a typed interface:
- **Agent:** `run(input, issues=None) -> OutputModel`.
- **Validator:** `validate(stories, model, endpoints, tests) -> ValidationReport`.
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

1. Run PO → Architect → QA in order. Each agent receives all previous outputs plus the original requirement.
2. Run the Validator.
3. If there are issues, group them by responsible agent and re-run only that agent and the agents downstream of it, passing the issues in.
   - Example: an issue owned by the Architect re-runs Architect + QA.
4. Stop when the Validator passes or after **2** correction rounds. Return the result in both cases. The report marks unresolved issues and never discards work.

## 4. Data contracts (Pydantic)

```python
class Story(BaseModel):
    id: str                     # "US-1"
    title: str
    as_a: str; i_want: str; so_that: str
    gherkin: str                # Spanish keywords: Característica / Escenario / Dado / Cuando / Entonces

class Column(BaseModel):
    name: str; type: str
    primary_key: bool = False
    foreign_key: str | None = None   # "table.column"
    nullable: bool = True

class Table(BaseModel):
    name: str; columns: list[Column]

class Endpoint(BaseModel):
    id: str                     # "EP-1"
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    path: str; description: str
    story_ids: list[str]        # stories it serves

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
    stories: list[Story]; architecture: ArchitectOutput
    tests: list[TestCase]; validation: ValidationReport
```

## 5. Validator checks

All checks are deterministic.

| Code | Rule | Owner |
|---|---|---|
| `STORY_WITHOUT_ENDPOINT` | every story id appears in some `endpoint.story_ids` | architect |
| `ENDPOINT_UNKNOWN_STORY` | every `endpoint.story_ids` entry exists | architect |
| `ENDPOINT_WITHOUT_TEST` | every endpoint id has ≥1 test case | qa |
| `TEST_UNKNOWN_REF` | every test's `endpoint_id` / `story_id` exists | qa |
| `FK_BROKEN` | every `foreign_key` points to an existing `table.column` | architect |
| `TABLE_WITHOUT_PK` | every table has a primary key | architect |
| `DUPLICATE_ID` | story / endpoint / test ids are unique | owner of that list |
| `GHERKIN_INVALID` | each `gherkin` contains `Escenario`, `Dado`, `Cuando`, `Entonces` | product_owner |

## 6. API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | liveness |
| `GET` | `/api/quota` | remaining free runs for the caller's IP |
| `POST` | `/api/runs` | multipart body (`text` or `file`). Optional headers `X-LLM-Provider: claude\|openai` and `X-LLM-Key`. Responds with an SSE stream. |

**SSE events:**
- `stage` — `{agent, status: started|done|retry, detail}`
- `validation` — the report after each round
- `result` — the `PipelineResult`
- `error` — `{code, message}`

## 7. Access and cost control

- **Without `X-LLM-Key`:** the owner's key is used and the per-IP daily counter is enforced (`FREE_RUNS_PER_DAY`, default 3). When the counter is exhausted, the server returns **429** and the UI opens "Use your own key".
- **With `X-LLM-Key`:** no limit.
  - The key is used only for that request.
  - It is never stored and never logged. A logging filter masks anything that looks like a key.
- **Global safety cap:** `MAX_FREE_RUNS_TOTAL_PER_DAY` across all IPs, so a botnet cannot drain the owner's key.
- `# shortcut: in-memory counter, resets on restart and only works with one instance; move to Redis if scaled out.`
- Input text is truncated at ~30k characters before reaching the agents.

## 8. Frontend

- **Single page, three zones:**
  1. **Input:** a textarea, a PDF/DOCX dropzone, "Try an example" buttons (2–3 preloaded ideas), the free-runs counter and a "Use your own key" panel (provider select + key field). The key lives in memory only and is not persisted.
  2. **Live pipeline:** four steps (PO → Architect → QA → Validator) driven by SSE. Retries are shown inline, e.g. *"Validator: 2 endpoints without tests → re-running QA"*.
  3. **Results tabs:** Stories (Gherkin highlighted), Data Model (Mermaid ER), API (endpoint table with linked stories), Tests, Validation (checks, corrections, rounds), and Export.
- **Export:**
  - Markdown file with every section. The Mermaid block renders on GitHub.
  - Raw JSON file.
- The SSE client parses a `fetch` stream, because `EventSource` cannot send a POST body.

## 9. Error handling

| Case | Behavior |
|---|---|
| Invalid / >5 MB file, or a scanned PDF with no text | 400 with a clear message, no LLM call |
| LLM output fails the schema | one retry with the validation error |
| Validator still failing after 2 rounds | return the result and flag unresolved issues |
| Free quota exhausted | 429 and the UI opens the BYOK panel |
| Invalid / out-of-credit user key | `error` event with a clear message; the key is masked |
| SSE connection lost | frontend shows the error and a retry button |

## 10. Testing

- **`FakeProvider`** returns canned outputs, including deliberately broken ones, so the full orchestrator and the correction loop are tested with zero tokens.
- Unit tests:
  - one test per Validator check;
  - extractors with sample PDF/DOCX fixtures;
  - rate limiter.
- API tests with `TestClient`: quota and 429, BYOK bypass, the SSE event sequence, and that the key never appears in logs.
- Frontend: Vitest for the SSE parser and the Mermaid builder.
- CI (GitHub Actions): ruff + pytest, eslint + vitest, on every push.

## 11. Repo deliverables

- `README.md` in English: demo GIF, "Try it live" link, architecture diagram, design decisions (why hand-written orchestration, why a deterministic validator), and how to run it locally.
- `docker-compose.yml` to run the backend and frontend with one command.
- `.env.example` listing every setting.
