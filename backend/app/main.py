import logging
from collections.abc import AsyncIterator, Callable

import httpx
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse

from app.config import Settings, get_settings
from app.exporters.github import create_issues
from app.exporters.jira_csv import to_jira_csv
from app.exporters.markdown import to_markdown
from app.exporters.openapi import to_openapi
from app.exporters.sql import to_sql
from app.extract import ExtractionError, extract_text
from app.logging_filter import install_logging
from app.orchestrator import Event, Orchestrator
from app.providers.base import LLMProvider, ProviderError
from app.providers.factory import make_provider
from app.rate_limit import QuotaTracker, client_ip
from app.schemas import GithubExportRequest, PipelineResult, RefineRequest, RunInput
from app.sse import format_sse

install_logging()
log = logging.getLogger("app")
settings = get_settings()
app = FastAPI(title="AI Requirements Generator")
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins,
                   allow_methods=["*"], allow_headers=["*"],
                   expose_headers=["Content-Disposition"])

_quota = QuotaTracker(settings.free_runs_per_day, settings.max_free_runs_total_per_day)
PROVIDER_STATUS = {"auth": 401, "rate_limited": 429, "upstream": 502}
ProviderFactory = Callable[[str | None, str | None, Settings], LLMProvider]


def get_quota() -> QuotaTracker:
    return _quota


def get_provider_factory() -> ProviderFactory:
    return make_provider


@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    if request.method == "POST":
        limit = (settings.max_upload_mb * 1024 + 64 if request.url.path == "/api/runs"
                 else settings.max_body_kb) * 1024
        length = request.headers.get("content-length")
        # Chunked bodies have no length to check; browsers always send one.
        if not (length and length.isdigit()):
            return JSONResponse({"detail": "Content-Length required."}, status_code=411)
        if int(length) > limit:
            return JSONResponse({"detail": "Request body too large."}, status_code=413)
    return await call_next(request)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/quota")
def quota(request: Request, q: QuotaTracker = Depends(get_quota)) -> dict:
    return {"remaining": q.remaining(client_ip(request, settings.trust_proxy)), "limit": q.per_ip}


def _start(request: Request, provider: str | None, key: str | None, q: QuotaTracker,
           factory: ProviderFactory) -> Orchestrator:
    """Build the provider first (no network), then charge the free quota only if it worked."""
    try:
        llm = factory(provider, key, settings)
    except ProviderError as e:
        raise HTTPException(PROVIDER_STATUS[e.code], e.message) from e
    if not key and not q.try_consume(client_ip(request, settings.trust_proxy)):
        raise HTTPException(429, "free_quota_exhausted")
    log.info("pipeline start provider=%s byok=%s", provider or settings.default_provider,
             bool(key))
    return Orchestrator(llm)


def _stream(events: AsyncIterator[Event]) -> StreamingResponse:
    async def body():
        async for event, data in events:
            if event == "error":
                log.warning("pipeline error code=%s", data["code"])
            yield format_sse(event, data)

    return StreamingResponse(body(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/runs")
async def create_run(
    request: Request,
    text: str | None = Form(None),
    file: UploadFile | None = File(None),
    team_context: str = Form(""),
    x_llm_provider: str | None = Header(None),
    x_llm_key: str | None = Header(None),
    q: QuotaTracker = Depends(get_quota),
    factory: ProviderFactory = Depends(get_provider_factory),
):
    data = None
    if file is not None:
        limit = settings.max_upload_mb * 1024 * 1024
        data = await file.read(limit + 1)
        if len(data) > limit:
            raise HTTPException(413, f"File larger than {settings.max_upload_mb} MB.")
    try:
        requirement = extract_text(file.filename if file else None, data, text,
                                   settings.max_text_chars)
    except ExtractionError as e:
        raise HTTPException(400, str(e)) from e
    run_input = RunInput(text=requirement,
                         team_context=team_context.strip()[: settings.max_context_chars])
    orch = _start(request, x_llm_provider, x_llm_key, q, factory)
    return _stream(orch.run(run_input))


@app.post("/api/refine")
async def refine(
    request: Request,
    body: RefineRequest,
    x_llm_provider: str | None = Header(None),
    x_llm_key: str | None = Header(None),
    q: QuotaTracker = Depends(get_quota),
    factory: ProviderFactory = Depends(get_provider_factory),
):
    orch = _start(request, x_llm_provider, x_llm_key, q, factory)
    return _stream(orch.refine(body.result, body.section, body.feedback))


async def get_http_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(timeout=20) as client:
        yield client


# Declared before /api/export/{fmt} so "github" is not taken as a format.
@app.post("/api/export/github")
async def export_github(
    body: GithubExportRequest,
    x_github_token: str | None = Header(None),
    client: httpx.AsyncClient = Depends(get_http_client),
):
    if not x_github_token:
        raise HTTPException(400, "Missing X-GitHub-Token header.")
    created, error = await create_issues(body.result, body.repo, x_github_token, client)
    if error:
        log.warning("github export failed after %d issues", len(created))
        return JSONResponse({"issues": created, "error": error}, status_code=502)
    return {"issues": created}


EXPORTS: dict[str, tuple[Callable[[PipelineResult], str] | None, str, str]] = {
    "markdown": (to_markdown, "md", "text/markdown; charset=utf-8"),
    "json": (lambda r: r.model_dump_json(indent=2), "json", "application/json"),
    "jira-csv": (to_jira_csv, "csv", "text/csv; charset=utf-8"),
    "openapi": (to_openapi, "yaml", "application/yaml"),
    "sql": (to_sql, "sql", "application/sql"),
}


@app.post("/api/export/{fmt}")
def export(fmt: str, result: PipelineResult) -> Response:
    if fmt not in EXPORTS:
        raise HTTPException(404, f"Unknown export format '{fmt}'.")
    render, ext, media = EXPORTS[fmt]
    if render is None:
        raise HTTPException(501, "Not implemented yet.")
    return Response(render(result), media_type=media,
                    headers={"Content-Disposition": f"attachment; filename=requirements.{ext}"})
