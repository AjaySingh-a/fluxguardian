"""
github_webhook.py — GitHub App webhook receiver.

Flow for pull_request.opened / pull_request.synchronize:
  1. Verify X-Hub-Signature-256 HMAC
  2. Extract owner / repo / PR number / installation_id
  3. Fetch PR files → extract .sql patches
  4. Run parse_schema_diff → BlastRadiusEngine (per change)
  5. Run ClaudeReporter on the most severe report
  6. Post the markdown comment back to the PR
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from app.clients.github import GitHubAppClient, extract_sql_diffs
from app.clients.openmetadata import OpenMetadataClient
from app.config import settings
from app.engine.blast_radius import BlastRadiusEngine, BlastRadiusReport
from app.llm.claude_reporter import ClaudeReporter
from app.parsers.schema_diff import parse_schema_diff

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/github", tags=["github"])

# Severity ordering for picking the "worst" report to comment
_SEV_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1}

# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------


def _verify_signature(secret: str, body: bytes, sig_header: str | None) -> None:
    """Raise HTTP 401 if the HMAC-SHA256 signature doesn't match."""
    if not sig_header or not sig_header.startswith("sha256="):
        raise HTTPException(status_code=401, detail="Missing X-Hub-Signature-256 header")

    expected = "sha256=" + hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, sig_header):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")


# ---------------------------------------------------------------------------
# Pipeline helpers
# ---------------------------------------------------------------------------


async def _analyze_and_comment(
    owner: str,
    repo: str,
    pull_number: int,
    installation_id: int,
    sql_diff: str,
) -> None:
    """
    Core pipeline: analyze diff → generate report → post comment.
    Runs in a background task so the webhook returns 200 immediately.
    """
    logger.info("[GH] Starting pipeline for %s/%s #%d", owner, repo, pull_number)

    # 1. Parse diff into SchemaChange list
    changes = parse_schema_diff(sql_diff)
    if not changes:
        logger.info("[GH] No SQL schema changes detected — skipping comment")
        return

    # 2. Run blast-radius analysis (tolerates OM being down)
    reports: list[BlastRadiusReport] = []
    async with OpenMetadataClient() as om:
        engine = BlastRadiusEngine(om)
        for change in changes:
            try:
                report = await engine.analyze(change)
                reports.append(report)
            except Exception as exc:
                logger.warning("[GH] engine.analyze failed for %s: %s", change.change_type, exc)

    if not reports:
        logger.info("[GH] All analyses failed or returned no results — skipping comment")
        return

    # 3. Pick the most severe report to drive the PR comment
    worst = max(reports, key=lambda r: _SEV_ORDER.get(r.overall_severity, 0))

    # 4. Generate markdown via Claude
    reporter = ClaudeReporter()
    try:
        result = await reporter.agenerate(worst)
        markdown = result.markdown
        logger.info("[GH] Claude report generated (%d tokens)", result.tokens_used)
    except Exception as exc:
        logger.error("[GH] ClaudeReporter failed: %s", exc)
        # Fallback to a plain-text summary so the PR still gets a comment
        markdown = _fallback_comment(worst)

    # 5. Post the comment
    try:
        async with GitHubAppClient(installation_id) as gh:
            comment = await gh.post_pr_comment(owner, repo, pull_number, markdown)
            logger.info("[GH] Posted comment %s on %s/%s #%d", comment.get("id"), owner, repo, pull_number)
    except Exception as exc:
        logger.error("[GH] Failed to post PR comment: %s", exc)


def _fallback_comment(report: BlastRadiusReport) -> str:
    """Minimal plain-text comment when Claude is unavailable."""
    sc  = report.schema_change
    sev = report.overall_severity.upper()
    n   = len(report.affected_assets)
    pii = " ⚠️ PII involved." if report.pii_involved else ""
    return (
        f"## FluxGuardian — {sev} severity change detected\n\n"
        f"`{sc.change_type.replace('_', ' ').upper()} {sc.table}`"
        f" — {n} downstream asset{'s' if n != 1 else ''} affected.{pii}\n\n"
        f"_{report.summary_one_line}_\n\n"
        "---\n*🤖 FluxGuardian (Claude unavailable — plain summary)*"
    )


# ---------------------------------------------------------------------------
# Webhook endpoint
# ---------------------------------------------------------------------------


@router.post("/webhook")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(default=None),
    x_github_event: str | None = Header(default=None),
) -> dict[str, str]:
    """
    Receive GitHub App webhook events.
    Always returns 200 quickly; real work runs in a background task.
    """
    body = await request.body()

    # Verify signature if a secret is configured
    if settings.github_webhook_secret:
        _verify_signature(settings.github_webhook_secret, body, x_hub_signature_256)

    payload: dict[str, Any] = await request.json()
    action  = payload.get("action", "")

    logger.info("[GH] Received event=%s action=%s", x_github_event, action)

    # Only handle PR open / update events
    if x_github_event != "pull_request" or action not in ("opened", "synchronize"):
        return {"status": "ignored", "reason": f"event={x_github_event} action={action}"}

    # Extract PR metadata
    pr_data      = payload.get("pull_request", {})
    repo_data    = payload.get("repository", {})
    installation = payload.get("installation", {})

    pull_number     = pr_data.get("number")
    owner           = repo_data.get("owner", {}).get("login")
    repo            = repo_data.get("name")
    installation_id = installation.get("id")

    if not all([pull_number, owner, repo, installation_id]):
        logger.warning("[GH] Missing required fields in payload")
        return {"status": "error", "reason": "incomplete payload"}

    # Fetch PR files and extract SQL diffs inside a background task
    async def _run() -> None:
        try:
            async with GitHubAppClient(installation_id) as gh:
                pr_files = await gh.get_pr_files(owner, repo, pull_number)
            sql_diff = extract_sql_diffs(pr_files)

            if not sql_diff.strip():
                logger.info("[GH] No .sql files changed in PR — skipping")
                return

            await _analyze_and_comment(
                owner, repo, pull_number, installation_id, sql_diff
            )
        except Exception as exc:
            logger.error("[GH] Background pipeline failed: %s", exc, exc_info=True)

    background_tasks.add_task(_run)
    return {"status": "accepted", "pr": f"{owner}/{repo}#{pull_number}"}
