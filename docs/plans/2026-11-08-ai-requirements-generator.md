# AI Requirements Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a web app where a pipeline of AI agents (PO → Architect → QA) plus a deterministic validator turns a requirement (text/PDF/DOCX) into stories, a data model, endpoints and tests. Teams can refine the result and export it to Jira, GitHub, OpenAPI and SQL.

**Architecture:**
- A stateless FastAPI backend runs a hand-written async orchestrator over an `LLMProvider` interface (Claude, OpenAI, Fake) and streams progress over SSE.
- Exporters are pure functions.
- A React + Vite SPA keeps the `PipelineResult` client-side and sends it back for refine/export.

**Tech Stack:**
- Backend: Python ≥3.12, FastAPI, Pydantic v2, pydantic-settings, python-multipart, pypdf, python-docx, anthropic, openai, httpx, PyYAML. Dev: pytest, pytest-asyncio, ruff, openapi-spec-validator, fpdf2.
- Frontend: React 18, Vite, TypeScript, mermaid 11, Vitest, ESLint.

**Spec:** `docs/specs/2026-11-08-ai-requirements-generator-design.md`

## Global Constraints

- Python `requires-python = ">=3.12"` (local machine has 3.15; CI uses 3.12).
- UI copy in English. Every agent prompt instructs: all generated content in Spanish, Gherkin keywords `Característica`, `Escenario`, `Dado`, `Cuando`, `Entonces`.
- Default Claude model `claude-sonnet-5-5`; OpenAI model from env `OPENAI_MODEL` (no hardcoded default beyond `.env.example`).
- Limits: upload 5 MB, text truncated to 30 000 chars, team context to 2 000, feedback to 2 000, `FREE_RUNS_PER_DAY=3`, `MAX_FREE_RUNS_TOTAL_PER_DAY=100`, max 2 correction rounds, 1 schema retry per agent call.
- User LLM keys and GitHub tokens: read from headers only (`X-LLM-Provider`, `X-LLM-Key`, `X-GitHub-Token`); never stored, never logged.
- No LangChain/LangGraph, no database, no Redis.
- Commit messages in English, conventional style, **no `Co-Authored-By` or Claude trailers**.
- Frontend visual work follows `.agents/skills/impeccable/SKILL.md`.

## Review Focus

1. **Free-tier IP behind Render's proxy:** without proxy headers every visitor shares one IP and the free quota runs out globally after 3 runs. Run uvicorn with `--proxy-headers --forwarded-allow-ips="*"` and have `client_ip()` read `request.client.host` (Task 8, Task 16).
2. **A bad upload must not burn a free run:** a 400 (wrong type, >5 MB, scanned PDF, empty text) must leave the quota unchanged. Quota is consumed only after input validation (Task 9 test).
3. **IDs the LLM formats inconsistently** (`us-1`, `" US-1 "`) should still link, not raise false validator issues. Normalize all ids and id references with `strip().upper()` in the schemas (Task 1 test).
4. **DOCX requirements written inside tables:** the extractor must include table cell text, not just paragraphs (Task 3 test).
5. **Endpoints with several path params** (`/owners/{ownerId}/pets/{petId}`) must declare every param in OpenAPI or the spec is invalid (Task 11 test).

---

## File Structure

```
backend/
  pyproject.toml           # deps, ruff, pytest config
  Dockerfile
  app/
    config.py              # Settings (pydantic-settings)
    schemas.py             # all Pydantic contracts
    extract.py             # extract_text()
    validator.py           # validate()
    logging_filter.py      # SecretMaskingFilter
    rate_limit.py          # QuotaTracker, client_ip()
    providers/{base,fake,claude,openai,factory}.py
    agents/{base,product_owner,architect,qa}.py
    agents/prompts/{product_owner,architect,qa}.md
    orchestrator.py        # Orchestrator.run / .refine
    sse.py                 # format_sse()
    exporters/{markdown,jira_csv,openapi,sql,github}.py
    main.py                # FastAPI app + routes
  tests/
    conftest.py            # sample_result fixture, PDF/DOCX fixture builders
    test_*.py
frontend/
  package.json, vite.config.ts, tsconfig.json, eslint.config.js, Dockerfile
  src/
    types.ts               # mirrors schemas.py
    api/sse.ts             # parseSSE()
    api/client.ts          # startRun, refine, getQuota, downloadExport, exportGithub
    lib/mermaid.ts         # toErDiagram()
    examples.ts
    App.tsx
    components/{InputPanel,KeyPanel,PipelineView,ResultsTabs,RefineBox,ExportTab}.tsx
    components/tabs/{StoriesTab,DataModelTab,ApiTab,TestsTab,ValidationTab}.tsx
docker-compose.yml, .env.example, .gitignore, README.md, .github/workflows/ci.yml
```

All backend commands run from `backend/`; all frontend commands from `frontend/`.

---

### Task 1: Backend scaffold and data contracts

**Files:**
- Create: `backend/pyproject.toml`, `backend/app/__init__.py`, `backend/app/config.py`, `backend/app/schemas.py`, `backend/tests/conftest.py`, `.gitignore`
- Test: `backend/tests/test_schemas.py`

**Interfaces:**
- Produces:
  - `schemas.py`: `RunInput`, `Story`, `ColumnType`, `Column`, `Table`, `Endpoint`, `ArchitectOutput`, `TestCase`, `Issue`, `ValidationReport`, `PipelineResult`, exactly as in spec §4. Also `ProductOwnerOutput(stories: list[Story])`, `QAOutput(tests: list[TestCase])`, `Section = Literal["product_owner","architect","qa"]`, `RefineRequest(result: PipelineResult, section: Section, feedback: str = Field(min_length=1, max_length=2000))`, `GithubExportRequest(result: PipelineResult, repo: str = Field(pattern=r"^[\w.-]+/[\w.-]+$"))`.
  - `config.py`: `Settings` with `anthropic_api_key: str = ""`, `openai_api_key: str = ""`, `default_provider: Literal["claude","openai"] = "claude"`, `claude_model = "claude-sonnet-5-5"`, `openai_model: str = ""`, `free_runs_per_day = 3`, `max_free_runs_total_per_day = 100`, `max_upload_mb = 5`, `max_text_chars = 30000`, `max_context_chars = 2000`, `max_body_kb = 1024`, `allowed_origins: list[str] = ["http://localhost:5173"]`; `get_settings()` cached.
  - `conftest.py`: fixture `sample_result() -> PipelineResult`. It is valid: 2 stories, 2 tables with an FK, 3 endpoints (one with path `/owners/{ownerId}/pets/{petId}`), one test per endpoint, and Gherkin with a comma and a newline.

- [ ] **Step 1:** `pyproject.toml` with the deps from Tech Stack. Set `[tool.pytest.ini_options] asyncio_mode = "auto"` and enable ruff rules `E,F,I,UP,B`. Root `.gitignore` covers `.venv/`, `__pycache__/`, `node_modules/`, `dist/`, `.env`. Create a venv and `pip install -e ".[dev]"`.
- [ ] **Step 2: Write failing tests**

```python
def test_ids_are_normalized():
    s = Story(id=" us-1 ", title="t", as_a="a", i_want="b", so_that="c",
              gherkin="Escenario: x\nDado a\nCuando b\nEntonces c", priority="alta")
    assert s.id == "US-1"
    ep = Endpoint(id="ep-1", method="GET", path="/x", description="d", story_ids=["us-1 "])
    assert ep.story_ids == ["US-1"]
    tc = TestCase(id="tc-1", title="t", endpoint_id="ep-1", story_id="us-1",
                  steps=["s"], expected="e", type="happy_path")
    assert (tc.endpoint_id, tc.story_id) == ("EP-1", "US-1")

def test_column_type_is_closed_set():
    with pytest.raises(ValidationError):
        Column(name="x", type="varchar(255)")

def test_sample_result_roundtrips(sample_result):
    assert PipelineResult.model_validate_json(sample_result.model_dump_json()) == sample_result
```

- [ ] **Step 3:** Run `pytest tests/test_schemas.py -v` → FAIL (import error).
- [ ] **Step 4:** Implement `schemas.py` and `config.py`. Use a single `normalize_id(v: str) -> str` (strip + upper) applied with `field_validator` (mode `before`) on every `id`, `story_ids` item, `endpoint_id` and `story_id`.
- [ ] **Step 5:** `pytest -v` → PASS; `ruff check .` → clean.
- [ ] **Step 6:** Commit `feat(backend): scaffold project and data contracts`.

---

### Task 2: Deterministic validator

**Files:** Create `backend/app/validator.py`; Test `backend/tests/test_validator.py`

**Interfaces:**
- Consumes: Task 1 schemas.
- Produces: `validate(stories: list[Story], arch: ArchitectOutput, tests: list[TestCase]) -> list[Issue]`. Only pure checks; the orchestrator builds the `ValidationReport`.

- [ ] **Step 1: Write failing tests.**
  - `test_sample_result_has_no_issues` asserts `validate(...) == []` on the fixture.
  - One test per code in spec §5 (9 codes), each mutating a `model_copy(deep=True)` of the fixture and asserting `[i.code for i in issues] == ["<CODE>"]` and the expected `owner`. For `DUPLICATE_ID` the owner follows the list (stories → product_owner, endpoints → architect, tests → qa).
  - `GHERKIN_INVALID` fires when any of `Escenario`, `Dado`, `Cuando`, `Entonces` is missing.
  - `FK_BROKEN` covers both an unknown table and an unknown column.
- [ ] **Step 2:** Run `pytest tests/test_validator.py -v` → FAIL.
- [ ] **Step 3:** Implement `validate`. Messages are Spanish, name the offending id, and say what to fix, e.g. `"La historia US-3 no está cubierta por ningún endpoint."`.
- [ ] **Step 4:** `pytest tests/test_validator.py -v` → PASS.
- [ ] **Step 5:** Commit `feat(backend): add deterministic validator`.

---

### Task 3: Text extraction

**Files:** Create `backend/app/extract.py`; Modify `backend/tests/conftest.py` (fixture builders); Test `backend/tests/test_extract.py`

**Interfaces:**
- Produces:
  - `class ExtractionError(ValueError)` with a user-facing English message.
  - `extract_text(filename: str | None, data: bytes | None, text: str | None, max_chars: int) -> str`.
    - Exactly one of `text` / `data` must be given.
    - Supported files: `.pdf`, `.docx`, `.txt`, `.md`, chosen by extension.
    - Returns stripped text truncated to `max_chars`.
    - Raises `ExtractionError` for: an unsupported type, a corrupt file, empty text, or a PDF with no extractable text (`"This PDF has no selectable text (scanned?)"`).
- conftest builders: `make_pdf(text) -> bytes` (fpdf2), `make_blank_pdf() -> bytes` (pypdf `PdfWriter.add_blank_page`), `make_docx(paragraphs, table_rows) -> bytes` (python-docx).

- [ ] **Step 1: Write failing tests:**
  - `test_pdf`: the result contains the text.
  - `test_docx_includes_table_cells`: a paragraph "Intro" plus a table cell "El usuario puede reservar" → both present.
  - `test_plain_text_truncated`: `"a"*50, max_chars=10` → `len == 10`.
  - `test_blank_pdf_rejected` raises `ExtractionError`.
  - `test_whitespace_text_rejected` raises.
  - `test_unsupported_extension_rejected` (`.exe`).
  - `test_corrupt_docx_rejected` (`b"not a zip"`).
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement. For DOCX, walk `document.paragraphs` and then every `table.rows[].cells[].text`. Wrap library exceptions in `ExtractionError`.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(backend): extract text from PDF, DOCX and plain text`.

---

### Task 4: LLM providers

**Files:** Create `backend/app/providers/{__init__,base,fake,claude,openai,factory}.py`; Test `backend/tests/test_providers.py`

**Interfaces:**
- Produces:
  - `base.py`:
    - `class LLMProvider(Protocol): async def generate_structured(self, system: str, user: str, schema: type[T]) -> T`. Raises `pydantic.ValidationError` on a bad shape.
    - `class ProviderError(Exception)` with `code: Literal["auth","rate_limited","upstream"]` and `message: str`. The message never includes the key.
  - `fake.py`: `FakeProvider(responses: list[dict | Exception])`. It pops responses in order, `model_validate`s each against `schema`, and records `calls: list[tuple[str, str, str]]` (system, user, schema name).
  - `claude.py`: `ClaudeProvider(api_key, model, http_client: httpx.AsyncClient | None = None)`. It uses `anthropic.AsyncAnthropic` with one tool `{"name": "submit", "input_schema": schema.model_json_schema()}` and `tool_choice={"type":"tool","name":"submit"}`, then validates the `tool_use` block's `input`. `max_tokens=8000`.
  - `openai.py`: `OpenAIProvider(api_key, model, http_client=None)`. It uses chat completions with `response_format={"type":"json_schema","json_schema":{"name": schema.__name__, "schema": ..., "strict": False}}` and validates the JSON content.
  - Both map SDK errors: authentication/permission → `auth`, rate limit / insufficient quota → `rate_limited`, anything else → `upstream`.
  - `factory.py`: `make_provider(provider: str | None, user_key: str | None, settings: Settings) -> LLMProvider`.
    - Uses the user key when given; otherwise the owner's key for `settings.default_provider`.
    - Raises `ProviderError("auth", ...)` if no key is available.

- [ ] **Step 1: Write failing tests.** Use `httpx.MockTransport` passed to the SDK clients:
  - `test_claude_forces_tool_and_parses`: the mock asserts the request body has `tool_choice.name == "submit"` and returns a `tool_use` payload → a `ProductOwnerOutput` instance.
  - `test_claude_401_maps_to_auth`: the error message does not contain the key `"sk-ant-secret"`.
  - `test_openai_parses_json_schema_response`.
  - `test_openai_429_maps_to_rate_limited`.
  - `test_fake_provider_replays_in_order`.
  - `test_factory_prefers_user_key`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(backend): add Claude, OpenAI and fake LLM providers`.

---

### Task 5: Agents and prompts

**Files:** Create `backend/app/agents/{__init__,base,product_owner,architect,qa}.py`, `backend/app/agents/prompts/{product_owner,architect,qa}.md`; Test `backend/tests/test_agents.py`

**Interfaces:**
- Consumes: `LLMProvider`, schemas.
- Produces:
  - `base.py`:
    - `@dataclass AgentContext(input: RunInput, stories: list[Story] | None = None, architecture: ArchitectOutput | None = None)`.
    - `class Agent(Generic[T])` with class attributes `name: Section`, `output_model: type[T]`, `prompt_file: str`, and `async run(self, ctx, issues: list[Issue] | None = None, feedback: str | None = None, previous: T | None = None) -> T`.
    - The user message is built from labelled blocks, included only when present: `## Requerimiento`, `## Contexto del equipo`, `## Historias`, `## Arquitectura`, `## Resultado anterior`, `## Feedback del usuario`, `## Problemas a corregir`. Upstream and previous outputs are rendered as JSON.
    - On `ValidationError` it retries once, appending `## Error de formato` with the error text, then re-raises.
  - `ProductOwnerAgent` (output `ProductOwnerOutput`), `ArchitectAgent` (`ArchitectOutput`), `QAAgent` (`QAOutput`).
- Prompt content (each .md, written in Spanish):
  - **Role and output language:** Spanish only, with the Gherkin keywords listed in Global Constraints.
  - **ID formats:**
    - `US-n`, `EP-n`, `TC-n`.
    - Keep existing ids when a previous result is given; when a story is split, add new ids.
  - **Respect the team context** when it is present.
  - **Architect:** only the 9 `ColumnType` values; FK as `table.column`; set `request_table` / `response_table` when the endpoint has a body or response.
  - **QA:** at least one test per endpoint; mix `happy_path`, `edge_case` and `error`.

- [ ] **Step 1: Write failing tests (FakeProvider):**
  - `test_architect_prompt_includes_stories_and_team_context`: inspect `fake.calls[0][1]` for `"## Historias"`, `"US-1"` and `"## Contexto del equipo"`.
  - `test_feedback_and_previous_included_when_refining`.
  - `test_schema_error_retries_once_with_error`: responses `[{"bad": 1}, valid]` → returns the valid one; the second call's user text contains `"## Error de formato"`.
  - `test_schema_error_twice_raises`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(backend): add PO, architect and QA agents`.

---

### Task 6: Orchestrator with correction loop

**Files:** Create `backend/app/orchestrator.py`; Test `backend/tests/test_orchestrator.py`

**Interfaces:**
- Consumes: agents, `validate`, `ProviderError`.
- Produces:
  - `Event = tuple[Literal["stage","validation","result","error"], dict]`.
  - `class Orchestrator(provider: LLMProvider, max_rounds: int = 2)` with `async def run(self, input: RunInput) -> AsyncIterator[Event]`.
  - Event payloads:
    - `stage`: `{"agent": Section | "validator", "status": "started"|"done"|"retry", "detail": str}`. A `retry` stage is emitted per agent re-run in a correction round, with `detail` like `"2 problemas: ENDPOINT_WITHOUT_TEST"`.
    - `validation`: `ValidationReport.model_dump()` after each validation.
    - `result`: `PipelineResult.model_dump()`.
    - `error`: `{"code": str, "message": str}`. Raised for a `ProviderError` (its code) or a final `ValidationError` (`"llm_output_invalid"`); no `result` follows it.
- Algorithm (spec §3.3):

```
order = [product_owner, architect, qa]
run all three in order; for round in 0..max_rounds:
    issues = validate(...); emit validation(passed=not issues, issues, rounds=round)
    if not issues or round == max_rounds: break
    start = min(order.index(i.owner) for i in issues)
    for agent in order[start:]: re-run with issues owned by that agent
emit result
```

- [ ] **Step 1: Write failing tests (FakeProvider with canned dicts derived from `sample_result`):**
  - `test_happy_path_events`: the event types are `stage×6, stage(validator)…, validation, result`; the final `validation.passed` is true; `rounds == 0`.
  - `test_qa_issue_reruns_only_qa`: the first QA output is missing a test → exactly 4 provider calls before the second validation, and the 4th call contains `"## Problemas a corregir"` and `"ENDPOINT_WITHOUT_TEST"`.
  - `test_architect_issue_reruns_architect_and_qa`.
  - `test_gives_up_after_two_rounds_and_still_returns_result`: `rounds == 2`, `passed is False`, a `result` event exists.
  - `test_provider_error_emits_error_event`: `FakeProvider([ProviderError("auth","bad key")])` → the last event is `("error", {"code":"auth", ...})`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(backend): orchestrate agents with validator correction loop`.

---

### Task 7: Refinement

**Files:** Modify `backend/app/orchestrator.py`; Test `backend/tests/test_orchestrator.py`

**Interfaces:**
- Produces: `async def refine(self, result: PipelineResult, section: Section, feedback: str) -> AsyncIterator[Event]`. It uses the same event types as `run`; `result.input` supplies the requirement.

- [ ] **Step 1: Write failing tests:**
  - `test_refine_architect_reruns_architect_then_qa_with_previous`: 2 calls before validation. The architect call contains `"## Feedback del usuario"` and `"## Resultado anterior"`. The QA call contains `"## Resultado anterior"` and not `"## Feedback del usuario"`. Stories are unchanged.
  - `test_refine_qa_only_one_call`.
  - `test_refine_runs_correction_loop`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement: re-run `order[order.index(section):]`, passing `feedback` only to the chosen agent and `previous` to each re-run agent, then reuse the same validation-loop helper as `run` (extract it into one private method; no duplication).
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(backend): refine a section from user feedback`.

---

### Task 8: Quota tracking and secret masking

**Files:** Create `backend/app/rate_limit.py`, `backend/app/logging_filter.py`; Test `backend/tests/test_rate_limit.py`, `backend/tests/test_logging_filter.py`

**Interfaces:**
- Produces:
  - `QuotaTracker(per_ip: int, global_cap: int, today: Callable[[], date] = date.today)`:
    - `remaining(ip) -> int`;
    - `try_consume(ip) -> bool`, which is False when the IP or the global cap is exhausted;
    - counts reset when `today()` changes;
    - a code comment: `# shortcut: in-memory counter, resets on restart and only works with one instance; move to Redis if scaled out.`
  - `client_ip(request: Request) -> str`. Returns `request.client.host`; correctness behind Render depends on uvicorn `--proxy-headers` (Task 16).
  - `SecretMaskingFilter(logging.Filter)` masks `sk-[A-Za-z0-9_-]{8,}`, `sk-ant-[...]`, `gh[pousr]_[A-Za-z0-9]{20,}`, `github_pat_[A-Za-z0-9_]{20,}` → `***`, in both `record.msg` and `record.args`.
  - `install_logging()` attaches the filter to the root handler.

- [ ] **Step 1: Write failing tests:**
  - per-IP limit (3 then False);
  - global cap across IPs;
  - reset on a new day (inject `today`);
  - `remaining` never negative;
  - the filter masks an Anthropic key, an OpenAI key and a GitHub PAT in an f-string message and in `%s` args.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(backend): add free-tier quota and secret-masking log filter`.

---

### Task 9: API — health, quota, runs, refine (SSE)

**Files:** Create `backend/app/main.py`, `backend/app/sse.py`; Test `backend/tests/test_api_runs.py`

**Interfaces:**
- Consumes: `extract_text`, `make_provider`, `Orchestrator`, `QuotaTracker`, `client_ip`, `install_logging`, `get_settings`.
- Produces:
  - `format_sse(event: str, data: dict) -> str` returns `f"event: {event}\ndata: {json}\n\n"`.
  - `app` with routes per spec §7.
  - Dependencies are overridable in tests:
    - `get_provider_factory()` returns `make_provider`; tests override it to return a `FakeProvider`.
    - `get_quota()` returns the app-level `QuotaTracker`.
  - Routes:
    - `GET /api/health` → `{"status":"ok"}`.
    - `GET /api/quota` → `{"remaining": int, "limit": int}`.
    - `POST /api/runs`: multipart `text?`, `file?`, `team_context?` + headers. Steps in order:
      1. Check the upload size (`max_upload_mb`) → 413.
      2. `extract_text` → 400 `{"detail": msg}` on `ExtractionError`.
      3. Truncate `team_context` to 2000 characters.
      4. If there is no `X-LLM-Key`, call `try_consume` → 429 `{"detail":"free_quota_exhausted"}`.
      5. Build the provider (`ProviderError` → 401).
      6. Return a `StreamingResponse(media_type="text/event-stream")` with headers `Cache-Control: no-cache` and `X-Accel-Buffering: no`.
    - `POST /api/refine`: JSON `RefineRequest`. Same header, quota and provider logic. Reject when the body exceeds `max_body_kb` → 413 (check `Content-Length`).
  - CORS from `allowed_origins`, with `expose_headers` for `Content-Disposition`.

- [ ] **Step 1: Write failing tests (`TestClient`, overrides):**
  - `test_run_streams_events_in_order`: parse the SSE body; the event names end with `validation`, `result`.
  - `test_bad_file_returns_400_and_does_not_consume_quota`: `remaining` is unchanged.
  - `test_oversized_upload_413`.
  - `test_quota_exhausted_429_without_key`: the 4th run gets 429.
  - `test_user_key_bypasses_quota`.
  - `test_refine_streams_result`.
  - `test_tampered_result_422`: refine with `section="hacker"`.
  - `test_user_key_never_logged`: use `caplog` with header `X-LLM-Key: sk-ant-supersecret123` and the fake provider raising `ProviderError` → `"supersecret" not in caplog.text`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `pytest -v` (whole suite) → PASS.
- [ ] **Step 5:** Smoke test with a real key (optional, costs one run): `uvicorn app.main:app --reload`, then `curl -N -F text="App de reservas para veterinaria" http://localhost:8000/api/runs` → the stream ends with `event: result`.
- [ ] **Step 6:** Commit `feat(backend): expose runs and refine over SSE`.

---

### Task 10: Markdown, JSON and Jira CSV exports + export route

**Files:** Create `backend/app/exporters/{__init__,markdown,jira_csv}.py`; Modify `backend/app/main.py`; Test `backend/tests/test_exporters_basic.py`, `backend/tests/test_api_export.py`

**Interfaces:**
- Produces:
  - `to_markdown(r: PipelineResult) -> str`. Sections: `# Requerimiento`, `## Historias de usuario` (Gherkin in ```gherkin fences), `## Modelo de datos` (```mermaid erDiagram), `## API` (table), `## Casos de prueba`, `## Validación`.
  - `er_diagram(arch: ArchitectOutput) -> str` in `markdown.py`. It must produce the same output as the frontend `toErDiagram` (Task 14):
    - one entity block per table: `type name PK|FK`;
    - one relation per FK: `parent ||--o{ child : "<fkcol>"`.
  - `to_jira_csv(r) -> str`:
    - written with the `csv` module (`QUOTE_MINIMAL`);
    - header `Summary,Description,Issue Type,Priority,Labels`;
    - priority map `alta→High, media→Medium, baja→Low`.
  - `story_body(r, story) -> str`: the shared description used by Jira and GitHub. Contains the user story sentence, Gherkin, `Endpoints:` lines and `Tests:` lines.
  - Route `POST /api/export/{format}` with `format ∈ {markdown,json,jira-csv,openapi,sql}`.
    - Returns `Response` with `Content-Disposition: attachment; filename=requirements.<ext>` (`md`, `json`, `csv`, `yaml`, `sql`).
    - An unknown format → 404.
    - The same `max_body_kb` → 413 check as `/api/refine` applies to every export route (including GitHub in Task 13).
    - The `openapi` and `sql` formats return 501 until Tasks 11–12.

- [ ] **Step 1: Write failing tests:**
  - `test_markdown_contains_mermaid_and_gherkin`.
  - `test_er_diagram_relation`: the output contains `owners ||--o{ pets : "owner_id"`.
  - `test_jira_csv_roundtrips_commas_and_newlines`: parse with `csv.DictReader`; the row count equals the story count; the `Description` of the fixture story still contains the comma and newline from its Gherkin; `Priority == "High"`.
  - `test_export_markdown_download_headers`.
  - `test_export_unknown_format_404`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(backend): export markdown, json and Jira CSV`.

---

### Task 11: OpenAPI export

**Files:** Create `backend/app/exporters/openapi.py`; Modify `backend/app/main.py` (wire `openapi`); Test `backend/tests/test_exporter_openapi.py`

**Interfaces:**
- Produces: `to_openapi(r: PipelineResult, title: str = "Generated API") -> str`, YAML via `yaml.safe_dump(sort_keys=False, allow_unicode=True)`.
- Mapping (deterministic):
  - `ColumnType → JSON Schema`: `uuid→string/uuid`, `text→string`, `integer→integer`, `bigint→integer/int64`, `decimal→number`, `boolean→boolean`, `date→string/date`, `timestamp→string/date-time`, `json→object`.
  - `required` = non-nullable columns.
  - Every `{param}` in the path becomes a `parameters` entry (`in: path`, `required: true`, `schema: {type: string}`).
  - `requestBody` is present only when `request_table` is set (`$ref` to the component). It is omitted for GET and DELETE even if set.
  - The 200 response uses `$ref`, or `type: array, items: $ref` when `response_is_list` is set; with no `response_table` it is just a description.
  - `operationId` = endpoint id; `summary` = description; `tags` = `story_ids`.

- [ ] **Step 1: Write failing tests:**
  - `test_openapi_is_valid`: `openapi_spec_validator.validate(yaml.safe_load(out))` does not raise.
  - `test_multiple_path_params_declared`: the operation for `/owners/{ownerId}/pets/{petId}` has parameter names `{"ownerId","petId"}`.
  - `test_list_response_is_array`.
  - `test_export_openapi_route_200`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(backend): export OpenAPI 3.1 spec`.

---

### Task 12: PostgreSQL DDL export

**Files:** Create `backend/app/exporters/sql.py`; Modify `backend/app/main.py` (wire `sql`); Test `backend/tests/test_exporter_sql.py`

**Interfaces:**
- Produces: `to_sql(r: PipelineResult) -> str`.
- Rules:
  - Type map: `uuid→UUID`, `text→TEXT`, `integer→INTEGER`, `bigint→BIGINT`, `decimal→NUMERIC(12,2)`, `boolean→BOOLEAN`, `date→DATE`, `timestamp→TIMESTAMPTZ`, `json→JSONB`.
  - Identifiers are double-quoted.
  - `NOT NULL` for non-nullable columns and PK columns; a table-level `PRIMARY KEY (...)` (composite PKs supported).
  - Tables are ordered by a topological sort on FK dependencies, with inline `FOREIGN KEY ... REFERENCES`. FKs that are part of a cycle (and self-references) are omitted inline and emitted at the end as `ALTER TABLE ... ADD CONSTRAINT "fk_<table>_<col>" FOREIGN KEY ...`.
  - The first line is `-- Generated by AI Requirements Generator (PostgreSQL)`.

- [ ] **Step 1: Write failing tests:**
  - `test_parent_created_before_child`: the index of `CREATE TABLE "owners"` is less than that of `"pets"`.
  - `test_cycle_uses_alter_table`: tables a→b and b→a → both `CREATE` statements plus an `ALTER TABLE` statement present.
  - `test_types_and_not_null`.
  - `test_export_sql_route_200`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement (Kahn's algorithm; the remaining nodes are the cycle members).
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(backend): export PostgreSQL DDL`.

---

### Task 13: GitHub Issues export

**Files:** Create `backend/app/exporters/github.py`; Modify `backend/app/main.py`; Test `backend/tests/test_exporter_github.py`

**Interfaces:**
- Consumes: `story_body` (Task 10).
- Produces:
  - `async def create_issues(r: PipelineResult, repo: str, token: str, client: httpx.AsyncClient) -> tuple[list[dict], str | None]`.
    - It POSTs `https://api.github.com/repos/{repo}/issues`, sequentially, once per story, with title `"[US-1] <title>"`, the body, and labels `["ai-generated"]`.
    - Headers: `Authorization: Bearer <token>`, `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28`.
    - Returns `(created=[{"story_id","url"}], error)`. On the first non-2xx response it stops and returns GitHub's `message` as `error`.
  - Route `POST /api/export/github`: body `GithubExportRequest`, header `X-GitHub-Token` (missing → 400).
    - All created → 200 `{"issues": [...]}`.
    - Partial or total failure → 502 `{"issues": [...], "error": str}`.
  - `get_http_client()` dependency, overridable in tests.

- [ ] **Step 1: Write failing tests (`httpx.MockTransport`):**
  - `test_creates_one_issue_per_story`: the request URLs, the label, and the title prefix.
  - `test_stops_on_error_and_reports_created`: the 2nd request returns 404 `{"message":"Not Found"}` → 1 created and error `"Not Found"`.
  - `test_route_requires_token_400`.
  - `test_token_not_in_logs`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run → PASS; run the full `pytest -v` and `ruff check .` → clean.
- [ ] **Step 5:** Commit `feat(backend): create GitHub issues from stories`.

---

### Task 14: Frontend scaffold, types, API client and Mermaid builder

**Files:** Create `frontend/` via `npm create vite@latest frontend -- --template react-ts`, then `src/types.ts`, `src/api/sse.ts`, `src/api/client.ts`, `src/lib/mermaid.ts`; Test `src/api/sse.test.ts`, `src/lib/mermaid.test.ts`

**Interfaces:**
- Produces:
  - `types.ts`: TS mirrors of every schema in Task 1, plus `type PipelineEvent = {event: "stage"|"validation"|"result"|"error"; data: any}`.
  - `parseSSE(body: ReadableStream<Uint8Array>): AsyncGenerator<PipelineEvent>`. It handles events split across chunks and multiple events in one chunk.
  - `client.ts`:
    - `type LlmAuth = {provider: "claude"|"openai"; key: string} | null`;
    - `startRun(input: {text?: string; file?: File; teamContext?: string}, auth: LlmAuth, signal?: AbortSignal): AsyncGenerator<PipelineEvent>`;
    - `refine(result, section, feedback, auth, signal?)`;
    - `getQuota(): Promise<{remaining:number; limit:number}>`;
    - `downloadExport(result, format): Promise<void>` (Blob plus an anchor click);
    - `exportGithub(result, repo, token): Promise<{issues:{story_id:string;url:string}[]; error?:string}>`;
    - a non-2xx response throws `ApiError(status, detail)`;
    - `API_URL = import.meta.env.VITE_API_URL ?? ""`.
  - `toErDiagram(arch: ArchitectOutput): string`. Same rules as backend `er_diagram`.
  - `vite.config.ts` proxies `/api` to `http://localhost:8000`.

- [ ] **Step 1:** Scaffold; `npm i mermaid@11`; `npm i -D vitest`. Add the scripts `test: vitest run` and `lint: eslint .`.
- [ ] **Step 2: Write failing tests:**
  - `parseSSE` yields 2 events when they are split across 3 chunks, including a split inside the JSON;
  - `toErDiagram` contains `owners ||--o{ pets : "owner_id"`, using a fixture equivalent to the backend `sample_result`.
- [ ] **Step 3:** Run `npm test` → FAIL.
- [ ] **Step 4:** Implement.
- [ ] **Step 5:** `npm test` → PASS; `npm run lint` → clean.
- [ ] **Step 6:** Commit `feat(frontend): scaffold app with typed API client and SSE parser`.

---

### Task 15: Frontend UI — input, live pipeline, results, refine, export

**Files:** Create `src/examples.ts`, `src/App.tsx`, `src/components/*.tsx`, `src/components/tabs/*.tsx`, styles; Test `src/components/PipelineView.test.tsx` (`@testing-library/react`, jsdom)

**Interfaces:**
- Consumes: Task 14 client and types.
- `App` state: `result: PipelineResult | null`, `stages: Record<Section|"validator", {status, detail}>`, `log: string[]`, `auth: LlmAuth` (React state only, never storage), `quota`, `error`.
- An `error` SSE event, a dropped stream (generator ends without `result`) or a network failure shows the message and a **Retry** button that repeats the last run/refine.
- Components follow spec §9 exactly:
  - **InputPanel:** textarea, PDF/DOCX dropzone, a collapsible Team context field, 3 example buttons, the quota badge, a "Use your own key" toggle, and Import JSON (validates the parsed object has `stories`, `architecture` and `tests`, otherwise shows an error).
  - **KeyPanel:** opens automatically on `ApiError.status === 429`.
  - **PipelineView:** 4 steps and a retry log line per `retry` stage.
  - **ResultsTabs:** Stories (Gherkin keyword highlighting via a regex over the 5 Spanish keywords, priority badge), Data Model (mermaid render of `toErDiagram`), API, Tests, Validation, Export.
  - **RefineBox:** in Stories, Data Model/API and Tests.
  - **ExportTab:** 5 download buttons and a GitHub form (repo + token in state) listing the created links and any error.
- `examples.ts`: 3 Spanish ideas: a veterinary booking app, a gym membership system, and a restaurant order tracker.

- [ ] **Step 1:** Run `.agents/skills/impeccable/scripts/impeccable.cmd context` from the repo root and follow the skill (reference/new-work.md, then craft-floor.md) for the visual direction before writing UI.
- [ ] **Step 2: Write failing test** `PipelineView` given stages `{product_owner: done, architect: retry "2 problemas: FK_BROKEN"}` → it renders "Architect" as retrying and shows the detail text.
- [ ] **Step 3:** Run → FAIL.
- [ ] **Step 4:** Implement the components.
- [ ] **Step 5:** `npm test` and `npm run lint` → PASS.
- [ ] **Step 6:** Manual check with the backend running (`npm run dev`). Pass when all of these work:
  - an example run streams all four steps;
  - the tabs render, including the ER diagram;
  - Refine on Tests updates the result;
  - every export downloads;
  - the layout works at 375 px wide;
  - a 4th free run opens the key panel.
- [ ] **Step 7:** Commit `feat(frontend): build input, live pipeline, results, refine and export UI`.

---

### Task 16: Packaging, CI and README

**Files:** Create `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml`, `.env.example`, `.github/workflows/ci.yml`, `README.md`

- [ ] **Step 1:** `backend/Dockerfile`:
  - based on `python:3.12-slim`;
  - installs the package;
  - `CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips="*"` (Review Focus 1).
- [ ] **Step 2:** `frontend/Dockerfile`: a node build stage, then `nginx:alpine` serving `dist`. `docker-compose.yml` runs the backend on 8000 with `env_file: .env` and the frontend on 5173 with `VITE_API_URL=http://localhost:8000`.
- [ ] **Step 3:** `.env.example` with every `Settings` field and short comments (`OPENAI_MODEL=` left for the user to fill).
- [ ] **Step 4:** `ci.yml` on push/PR has two jobs:
  - backend: Python 3.12, `pip install -e ".[dev]"`, `ruff check .`, `pytest`;
  - frontend: Node 22, `npm ci`, `npm run lint`, `npm test`, `npm run build`.
- [ ] **Step 5:** `README.md` in English, following spec §12:
  - title and one-liner;
  - demo GIF placeholder path `docs/demo.gif` (recorded after deploy) and a "Try it live" link placeholder;
  - a Mermaid architecture diagram;
  - "Why hand-written orchestration", "Why a deterministic validator", "Why stateless";
  - "Use it in your team" (docker compose, BYOK, team context, export formats);
  - local dev commands;
  - the env var table.
- [ ] **Step 6:** Verify `pytest`, `npm test` and `npm run build` all pass locally. Docker is not installed on the dev machine, so the Docker files are verified by CI/Render, not locally.
- [ ] **Step 7:** Commit `chore: add Docker, CI workflow and README`.

**Deploy (manual, by the user; not part of the plan's verification):**
- Render web service from `backend/Dockerfile` with the env vars.
- Vercel project rooted at `frontend/` with `VITE_API_URL` set to the Render URL.
- Add the Vercel URL to `ALLOWED_ORIGINS`.
