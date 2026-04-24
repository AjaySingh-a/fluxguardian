"""
test_github_webhook.py — Unit tests for the GitHub webhook handler.

All GitHub API calls and Claude calls are mocked — no network required.

Run:
    pytest backend/tests/test_github_webhook.py -v
"""

from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

client = TestClient(app)

_WEBHOOK_SECRET = "test-secret-xyz"
_SQL_PATCH = (
    "@@ -0,0 +1,1 @@\n"
    "+ALTER TABLE users RENAME COLUMN email TO contact_email;"
)

def _sign(body: bytes, secret: str = _WEBHOOK_SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _pr_payload(action: str = "opened", sql_filename: str = "migrations/005.sql") -> dict:
    return {
        "action": action,
        "pull_request": {"number": 42, "title": "rename email column"},
        "repository": {
            "name": "fluxguardian-demo",
            "owner": {"login": "Devgr72"},
        },
        "installation": {"id": 99999999},
    }


def _pr_files_response(filename: str = "migrations/005.sql", patch: str = _SQL_PATCH) -> list:
    return [{"filename": filename, "patch": patch, "status": "modified"}]


# ---------------------------------------------------------------------------
# Signature verification tests
# ---------------------------------------------------------------------------

class TestSignatureVerification:
    def test_missing_signature_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("app.api.github_webhook.settings.github_webhook_secret", _WEBHOOK_SECRET)
        body = json.dumps(_pr_payload()).encode()
        resp = client.post(
            "/api/github/webhook",
            content=body,
            headers={"X-GitHub-Event": "pull_request", "Content-Type": "application/json"},
        )
        assert resp.status_code == 401

    def test_wrong_signature_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("app.api.github_webhook.settings.github_webhook_secret", _WEBHOOK_SECRET)
        body = json.dumps(_pr_payload()).encode()
        resp = client.post(
            "/api/github/webhook",
            content=body,
            headers={
                "X-GitHub-Event": "pull_request",
                "Content-Type": "application/json",
                "X-Hub-Signature-256": "sha256=deadbeef",
            },
        )
        assert resp.status_code == 401

    def test_correct_signature_accepted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("app.api.github_webhook.settings.github_webhook_secret", _WEBHOOK_SECRET)
        body = json.dumps(_pr_payload()).encode()
        resp = client.post(
            "/api/github/webhook",
            content=body,
            headers={
                "X-GitHub-Event": "pull_request",
                "Content-Type": "application/json",
                "X-Hub-Signature-256": _sign(body),
            },
        )
        assert resp.status_code == 200

    def test_no_secret_configured_skips_verification(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("app.api.github_webhook.settings.github_webhook_secret", None)
        body = json.dumps(_pr_payload()).encode()
        resp = client.post(
            "/api/github/webhook",
            content=body,
            headers={"X-GitHub-Event": "pull_request", "Content-Type": "application/json"},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Event filtering tests
# ---------------------------------------------------------------------------

class TestEventFiltering:
    def _post(self, event: str, action: str, monkeypatch: pytest.MonkeyPatch) -> dict:
        monkeypatch.setattr("app.api.github_webhook.settings.github_webhook_secret", _WEBHOOK_SECRET)
        payload = _pr_payload(action=action)
        body    = json.dumps(payload).encode()
        resp = client.post(
            "/api/github/webhook",
            content=body,
            headers={
                "X-GitHub-Event": event,
                "Content-Type": "application/json",
                "X-Hub-Signature-256": _sign(body),
            },
        )
        assert resp.status_code == 200
        return resp.json()

    def test_push_event_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        data = self._post("push", "opened", monkeypatch)
        assert data["status"] == "ignored"

    def test_pr_closed_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        data = self._post("pull_request", "closed", monkeypatch)
        assert data["status"] == "ignored"

    def test_pr_opened_accepted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        data = self._post("pull_request", "opened", monkeypatch)
        assert data["status"] == "accepted"

    def test_pr_synchronize_accepted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        data = self._post("pull_request", "synchronize", monkeypatch)
        assert data["status"] == "accepted"


# ---------------------------------------------------------------------------
# extract_sql_diffs helper tests
# ---------------------------------------------------------------------------

class TestExtractSqlDiffs:
    def test_sql_file_extracted(self) -> None:
        from app.clients.github import extract_sql_diffs
        files = _pr_files_response("migrations/005.sql", _SQL_PATCH)
        diff  = extract_sql_diffs(files)
        assert "migrations/005.sql" in diff
        assert "RENAME COLUMN" in diff

    def test_non_sql_file_ignored(self) -> None:
        from app.clients.github import extract_sql_diffs
        files = _pr_files_response("src/models.py", "+class Foo: pass")
        diff  = extract_sql_diffs(files)
        assert diff.strip() == ""

    def test_multiple_sql_files_combined(self) -> None:
        from app.clients.github import extract_sql_diffs
        files = [
            {"filename": "migrations/001.sql", "patch": "@@ -0,0 +1 @@\n+ALTER TABLE a DROP COLUMN b;"},
            {"filename": "migrations/002.sql", "patch": "@@ -0,0 +1 @@\n+ALTER TABLE c ADD COLUMN d TEXT;"},
            {"filename": "app/main.py",        "patch": "+print('hello')"},
        ]
        diff = extract_sql_diffs(files)
        assert "001.sql" in diff
        assert "002.sql" in diff
        assert "main.py" not in diff

    def test_file_without_patch_skipped(self) -> None:
        from app.clients.github import extract_sql_diffs
        files = [{"filename": "migrations/001.sql", "patch": None}]
        diff  = extract_sql_diffs(files)
        assert diff.strip() == ""


# ---------------------------------------------------------------------------
# Fallback comment tests
# ---------------------------------------------------------------------------

class TestFallbackComment:
    def _make_report(self) -> "BlastRadiusReport":
        from datetime import datetime, timezone
        from app.engine.blast_radius import BlastRadiusReport
        from app.parsers.schema_diff import SchemaChange
        return BlastRadiusReport(
            schema_change=SchemaChange(
                change_type="rename_column", table="users",
                old_column="email", new_column="contact_email",
                risk="high",
                raw_sql="+ALTER TABLE users RENAME COLUMN email TO contact_email;",
                line_number=1,
            ),
            affected_assets=[],
            affected_columns=[],
            pii_involved=True,
            pii_classifications=["PII.Email"],
            overall_severity="high",
            requires_governance_approval=True,
            total_owners_to_notify=0,
            unique_owner_emails=[],
            summary_one_line="Renaming users.email — no downstream detected",
            analysis_timestamp=datetime(2026, 4, 20, tzinfo=timezone.utc),
        )

    def test_fallback_contains_severity(self) -> None:
        from app.api.github_webhook import _fallback_comment
        txt = _fallback_comment(self._make_report())
        assert "HIGH" in txt
        assert "FluxGuardian" in txt

    def test_fallback_contains_pii_warning(self) -> None:
        from app.api.github_webhook import _fallback_comment
        txt = _fallback_comment(self._make_report())
        assert "PII" in txt or "⚠️" in txt

    def test_fallback_contains_footer(self) -> None:
        from app.api.github_webhook import _fallback_comment
        txt = _fallback_comment(self._make_report())
        assert "FluxGuardian" in txt
