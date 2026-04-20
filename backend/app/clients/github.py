"""
github.py — Async GitHub API client with GitHub App JWT authentication.

Handles:
- JWT generation from App private key (RS256, 10-min expiry)
- Installation access token exchange (per-repo, 1-hour TTL)
- Fetching PR file diffs
- Posting PR comments
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import httpx
import jwt

from app.config import settings

logger = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com"
_ACCEPT_V3  = "application/vnd.github.v3+json"
_ACCEPT_DIFF = "application/vnd.github.v3.diff"

# Simple in-memory token cache: installation_id → (token, expires_at)
_token_cache: dict[int, tuple[str, float]] = {}


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def _load_private_key() -> str:
    path = settings.github_app_private_key_path
    if not path:
        raise RuntimeError(
            "GITHUB_APP_PRIVATE_KEY_PATH is not set. "
            "Download the .pem from your GitHub App settings."
        )
    return Path(path).read_text()


def _make_app_jwt() -> str:
    """Generate a 10-minute GitHub App JWT signed with the private key."""
    now = int(time.time())
    payload = {
        "iat": now - 60,          # issued 60 s ago (clock skew tolerance)
        "exp": now + (9 * 60),    # valid for 9 minutes
        "iss": settings.github_app_id,
    }
    private_key = _load_private_key()
    return jwt.encode(payload, private_key, algorithm="RS256")


# ---------------------------------------------------------------------------
# GitHubAppClient
# ---------------------------------------------------------------------------

class GitHubAppClient:
    """
    Async client that authenticates as a GitHub App installation.

    Usage:
        async with GitHubAppClient(installation_id=12345678) as gh:
            files = await gh.get_pr_files("owner", "repo", 42)
            await gh.post_pr_comment("owner", "repo", 42, "Hello!")
    """

    def __init__(self, installation_id: int) -> None:
        self._installation_id = installation_id
        self._http: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Context-manager lifecycle
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "GitHubAppClient":
        token = await self._get_installation_token()
        self._http = httpx.AsyncClient(
            base_url=_GITHUB_API,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": _ACCEPT_V3,
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "FluxGuardian-Bot/1.0",
            },
            timeout=30.0,
        )
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._http:
            await self._http.aclose()
            self._http = None

    # ------------------------------------------------------------------
    # Token management
    # ------------------------------------------------------------------

    async def _get_installation_token(self) -> str:
        """Return a cached installation token, refreshing if within 5 min of expiry."""
        now = time.monotonic()
        cached = _token_cache.get(self._installation_id)
        if cached:
            token, expires_at = cached
            if now < expires_at - 300:   # 5-min buffer
                logger.debug("Using cached installation token for %d", self._installation_id)
                return token

        logger.info("Fetching new installation token for %d", self._installation_id)
        app_jwt  = _make_app_jwt()
        url      = f"{_GITHUB_API}/app/installations/{self._installation_id}/access_tokens"
        async with httpx.AsyncClient(timeout=15.0) as tmp:
            resp = await tmp.post(
                url,
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": _ACCEPT_V3,
                    "X-GitHub-Api-Version": "2022-11-28",
                    "User-Agent": "FluxGuardian-Bot/1.0",
                },
            )
        resp.raise_for_status()
        data  = resp.json()
        token = data["token"]

        # GitHub installation tokens live for 1 hour
        _token_cache[self._installation_id] = (token, now + 3600)
        return token

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    @property
    def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            raise RuntimeError("Client not open — use 'async with GitHubAppClient(...)'")
        return self._http

    async def _get(self, path: str, **kwargs: Any) -> Any:
        resp = await self._client.get(path, **kwargs)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_pr_files(
        self, owner: str, repo: str, pull_number: int
    ) -> list[dict]:
        """
        GET /repos/{owner}/{repo}/pulls/{pull_number}/files
        Returns a list of file objects with patch/diff content.
        """
        path = f"/repos/{owner}/{repo}/pulls/{pull_number}/files"
        return await self._get(path, params={"per_page": 100})

    async def get_pr_diff(
        self, owner: str, repo: str, pull_number: int
    ) -> str:
        """
        GET the unified diff for the entire PR (application/vnd.github.v3.diff).
        """
        path = f"/repos/{owner}/{repo}/pulls/{pull_number}"
        resp = await self._client.get(
            path,
            headers={**self._client.headers, "Accept": _ACCEPT_DIFF},
        )
        resp.raise_for_status()
        return resp.text

    async def post_pr_comment(
        self, owner: str, repo: str, pull_number: int, body: str
    ) -> dict:
        """
        POST /repos/{owner}/{repo}/issues/{pull_number}/comments
        Posts a markdown comment on the PR.
        """
        path = f"/repos/{owner}/{repo}/issues/{pull_number}/comments"
        resp = await self._client.post(path, json={"body": body})
        resp.raise_for_status()
        return resp.json()

    async def get_installation_id(self, owner: str, repo: str) -> int | None:
        """
        GET /repos/{owner}/{repo}/installation
        Returns the installation ID for the GitHub App on this repo.
        Uses App JWT auth (not installation token).
        """
        app_jwt = _make_app_jwt()
        url = f"{_GITHUB_API}/repos/{owner}/{repo}/installation"
        async with httpx.AsyncClient(timeout=15.0) as tmp:
            resp = await tmp.get(
                url,
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": _ACCEPT_V3,
                    "X-GitHub-Api-Version": "2022-11-28",
                    "User-Agent": "FluxGuardian-Bot/1.0",
                },
            )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json().get("id")


# ---------------------------------------------------------------------------
# Convenience: extract SQL diffs from PR file list
# ---------------------------------------------------------------------------

def extract_sql_diffs(pr_files: list[dict]) -> str:
    """
    Given the list of file objects from GitHub's PR files API,
    extract patch content for .sql files and return a unified diff string
    suitable for passing to parse_schema_diff().
    """
    parts: list[str] = []
    for f in pr_files:
        filename: str = f.get("filename", "")
        patch: str    = f.get("patch", "") or ""
        if not filename.endswith(".sql") or not patch:
            continue
        parts.append(
            f"--- a/{filename}\n"
            f"+++ b/{filename}\n"
            f"{patch}\n"
        )
    return "\n".join(parts)
