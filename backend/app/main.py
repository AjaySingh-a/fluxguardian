from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup: place any resource initialisation here (DB pools, etc.)
    yield
    # Shutdown: clean up resources here


app = FastAPI(
    title="FluxGuardian",
    description="Analyzes GitHub PRs for breaking database schema changes.",
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/version", tags=["meta"])
async def version() -> dict[str, Any]:
    return {"version": settings.app_version}
