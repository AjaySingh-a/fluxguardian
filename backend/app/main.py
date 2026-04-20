from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.api.assets import router as assets_router
from app.api.github_webhook import router as github_router
from app.clients.openmetadata import OpenMetadataClient
from app.config import settings
from app.engine.blast_radius import BlastRadiusEngine, BlastRadiusReport
from app.llm.claude_reporter import ClaudeReporter
from app.parsers.schema_diff import parse_schema_diff


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield


app = FastAPI(
    title="FluxGuardian",
    description="Analyzes GitHub PRs for breaking database schema changes.",
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(assets_router)
app.include_router(github_router)

# ---------------------------------------------------------------------------
# Meta endpoints
# ---------------------------------------------------------------------------


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/version", tags=["meta"])
async def version() -> dict[str, Any]:
    return {"version": settings.app_version}


# ---------------------------------------------------------------------------
# Analysis endpoint
# ---------------------------------------------------------------------------


class AnalyzeRequest(BaseModel):
    diff: str
    om_service: str = "FoodieExpressPostgres"
    om_database: str = "foodieexpress"
    om_schema: str = "public"


@app.post("/api/analyze", tags=["analysis"], response_model=list[BlastRadiusReport])
async def analyze_diff(request: AnalyzeRequest) -> list[BlastRadiusReport]:
    """
    Parse a unified git diff for schema changes and return a BlastRadiusReport
    for each detected change.

    Body:
      - diff: raw unified diff text (as produced by `git diff`)
      - om_service / om_database / om_schema: override the OM FQN prefix
        (defaults point at the seeded FoodieExpress demo data)
    """
    changes = parse_schema_diff(request.diff)
    if not changes:
        return []

    reports: list[BlastRadiusReport] = []
    async with OpenMetadataClient() as om:
        engine = BlastRadiusEngine(om)
        for change in changes:
            try:
                report = await engine.analyze(
                    change,
                    om_service=request.om_service,
                    om_database=request.om_database,
                    om_schema=request.om_schema,
                )
                reports.append(report)
            except Exception as exc:
                # Log and skip individual failures so one bad change doesn't
                # block the entire response.
                import logging
                logging.getLogger(__name__).error(
                    "analyze failed for change %s on %s: %s",
                    change.change_type, change.table, exc, exc_info=True,
                )
    return reports


# ---------------------------------------------------------------------------
# Report endpoint — BlastRadiusReport → GitHub PR markdown comment
# ---------------------------------------------------------------------------


class ReportRequest(BaseModel):
    report: BlastRadiusReport


class ReportResponse(BaseModel):
    markdown: str
    tokens_used: int


@app.post("/api/report", tags=["reporting"], response_model=ReportResponse)
async def generate_report(request: ReportRequest) -> ReportResponse:
    """
    Convert a BlastRadiusReport into a formatted GitHub PR comment.

    Body:
      - report: a BlastRadiusReport object (output of /api/analyze)

    Returns:
      - markdown: ready-to-post GitHub PR comment string
      - tokens_used: total Claude tokens consumed
    """
    reporter = ClaudeReporter()
    try:
        result = await reporter.agenerate(request.report)
        return ReportResponse(markdown=result.markdown, tokens_used=result.tokens_used)
    except Exception as exc:
        import logging as _logging
        _logging.getLogger(__name__).error("generate_report failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Claude reporter error: {exc}") from exc
