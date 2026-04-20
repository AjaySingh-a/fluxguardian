"""
test_claude_reporter.py — Unit tests for ClaudeReporter.

Strategy
--------
* All tests mock the Anthropic client so no real API calls are made.
* Three fixture reports cover the required scenarios:
    1. rename_hero   — rename users.email → contact_email (high severity, PII)
    2. drop_critical — drop orders.amount_cents (critical severity, financial PII)
    3. safe_add      — add orders.promo_code (low severity, no PII, no downstream)

Each test verifies that the markdown comment contains expected keywords and
structure without asserting the exact wording (Claude's phrasing may vary).

Run:
    pytest backend/tests/test_claude_reporter.py -v
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.engine.blast_radius import AffectedAsset, BlastRadiusReport
from app.llm.claude_reporter import ClaudeReporter, _build_prompt
from app.parsers.schema_diff import SchemaChange


# ---------------------------------------------------------------------------
# Fixtures — three canonical BlastRadiusReport scenarios
# ---------------------------------------------------------------------------

def _sc(**kwargs) -> SchemaChange:
    defaults = dict(
        change_type="rename_column",
        table="users",
        old_column="email",
        new_column="contact_email",
        risk="high",
        raw_sql="ALTER TABLE users RENAME COLUMN email TO contact_email;",
        line_number=1,
    )
    defaults.update(kwargs)
    return SchemaChange(**defaults)


def _asset(name: str, asset_type: str, severity: str, email: str) -> AffectedAsset:
    handle = "@" + email.split("@")[0]
    return AffectedAsset(
        id=name,
        name=name,
        fqn=f"FoodieExpress.{name}",
        asset_type=asset_type,
        owner_name=email.split("@")[0].capitalize(),
        owner_email=email,
        slack_handle=handle,
        severity=severity,  # type: ignore[arg-type]
        reason="Direct dependency via lineage",
    )


@pytest.fixture()
def rename_hero() -> BlastRadiusReport:
    """Hero case: rename users.email → contact_email. PII, high severity, 3 downstream."""
    return BlastRadiusReport(
        schema_change=_sc(
            change_type="rename_column",
            table="users",
            old_column="email",
            new_column="contact_email",
            risk="high",
            raw_sql="ALTER TABLE users RENAME COLUMN email TO contact_email;",
        ),
        affected_assets=[
            _asset("CFO_Weekly_Revenue", "dashboard", "high",  "priya@foodie.com"),
            _asset("Churn_Predictor_v2", "mlmodel",   "high",  "arjun@foodie.com"),
            _asset("daily_revenue_etl",  "pipeline",  "medium","priya@foodie.com"),
        ],
        affected_columns=["FoodieExpressPostgres.foodieexpress.public.users.email"],
        pii_involved=True,
        pii_classifications=["PII.Email"],
        overall_severity="high",
        requires_governance_approval=True,
        total_owners_to_notify=2,
        unique_owner_emails=["arjun@foodie.com", "priya@foodie.com"],
        summary_one_line="Renaming users.email will impact 3 downstream assets [PII involved]",
        analysis_timestamp=datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc),
    )


@pytest.fixture()
def drop_critical() -> BlastRadiusReport:
    """Critical drop: drop orders.amount_cents. Financial PII, 2 downstream."""
    return BlastRadiusReport(
        schema_change=_sc(
            change_type="drop_column",
            table="orders",
            old_column="amount_cents",
            new_column=None,
            risk="critical",
            raw_sql="ALTER TABLE orders DROP COLUMN amount_cents;",
        ),
        affected_assets=[
            _asset("CFO_Weekly_Revenue",  "dashboard", "critical", "priya@foodie.com"),
            _asset("Fraud_Detection_v4",  "mlmodel",   "critical", "arjun@foodie.com"),
        ],
        affected_columns=["FoodieExpressPostgres.foodieexpress.public.orders.amount_cents"],
        pii_involved=True,
        pii_classifications=["PII.Financial"],
        overall_severity="critical",
        requires_governance_approval=True,
        total_owners_to_notify=2,
        unique_owner_emails=["arjun@foodie.com", "priya@foodie.com"],
        summary_one_line="Dropping orders.amount_cents will impact 2 downstream assets [PII involved]",
        analysis_timestamp=datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc),
    )


@pytest.fixture()
def safe_add() -> BlastRadiusReport:
    """Safe add: add orders.promo_code. No PII, no downstream, low severity."""
    return BlastRadiusReport(
        schema_change=_sc(
            change_type="add_column",
            table="orders",
            old_column=None,
            new_column="promo_code",
            risk="low",
            raw_sql="ALTER TABLE orders ADD COLUMN promo_code TEXT;",
        ),
        affected_assets=[],
        affected_columns=[],
        pii_involved=False,
        pii_classifications=[],
        overall_severity="low",
        requires_governance_approval=False,
        total_owners_to_notify=0,
        unique_owner_emails=[],
        summary_one_line="Adding orders.promo_code has no detected downstream impact",
        analysis_timestamp=datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_response(text: str) -> MagicMock:
    """Build a minimal mock that looks like an anthropic.Message."""
    block = MagicMock()
    block.text = text
    usage = MagicMock()
    usage.input_tokens  = 500
    usage.output_tokens = 150
    msg = MagicMock()
    msg.content = [block]
    msg.usage   = usage
    return msg


def _make_reporter(mock_text: str) -> tuple[ClaudeReporter, MagicMock]:
    """Return a ClaudeReporter whose Anthropic client is fully mocked."""
    with patch("app.llm.claude_reporter.anthropic.Anthropic") as MockCls:
        mock_client = MagicMock()
        MockCls.return_value = mock_client
        mock_client.messages.create.return_value = _fake_response(mock_text)
        reporter = ClaudeReporter(api_key="test-key", model="claude-haiku-4-5-20251001")
    reporter._client = mock_client
    return reporter, mock_client


# ---------------------------------------------------------------------------
# Prompt-builder unit tests (no API call)
# ---------------------------------------------------------------------------

class TestBuildPrompt:
    def test_contains_report_json(self, rename_hero: BlastRadiusReport) -> None:
        prompt = _build_prompt(rename_hero)
        assert "rename_column" in prompt
        assert "users" in prompt
        assert "contact_email" in prompt

    def test_contains_few_shot_example(self, rename_hero: BlastRadiusReport) -> None:
        prompt = _build_prompt(rename_hero)
        assert "EXAMPLE INPUT" in prompt
        assert "EXAMPLE OUTPUT" in prompt

    def test_pii_report_prompt_mentions_pii(self, rename_hero: BlastRadiusReport) -> None:
        prompt = _build_prompt(rename_hero)
        assert "PII" in prompt

    def test_safe_report_prompt_no_pii_flag(self, safe_add: BlastRadiusReport) -> None:
        prompt = _build_prompt(safe_add)
        # pii_involved == false, but the word PII is still in the prompt template
        assert '"pii_involved": false' in prompt


# ---------------------------------------------------------------------------
# rename_hero tests — high severity, PII, 3 downstream
# ---------------------------------------------------------------------------

class TestRenameHero:
    _MOCK_MARKDOWN = """\
## 🔴 FluxGuardian — HIGH severity schema change detected

**`RENAME COLUMN users.email → contact_email`**

This PR renames the `email` column in the `users` table to `contact_email`.
Three downstream consumers depend on this column: the CFO Weekly Revenue
dashboard, Churn Predictor v2 ML model, and the daily_revenue_etl pipeline.
All three will fail to read the old column name after this migration.

### Affected assets

| Asset | Type | Severity | Owner |
|-------|------|----------|-------|
| CFO_Weekly_Revenue | dashboard | 🔴 HIGH | @priya |
| Churn_Predictor_v2 | mlmodel | 🔴 HIGH | @arjun |
| daily_revenue_etl | pipeline | 🟠 MEDIUM | @priya |

### Safe migration plan

```sql
-- Step 1: deploy code reading from new column name contact_email
-- Step 2: run rename while both names co-exist via a view
ALTER TABLE users RENAME COLUMN email TO email_deprecated;
CREATE VIEW users_compat AS SELECT *, email_deprecated AS contact_email FROM users;

-- Step 3: after validation, drop the view and old column
-- DROP VIEW users_compat;
-- ALTER TABLE users DROP COLUMN email_deprecated;
```

> ⚠️ **PII Warning** — This column carries a `PII.Email` classification.
> Governance approval is required before merging.

> **Owners to ping:** @priya @arjun

---
*🤖 Generated by [FluxGuardian](https://github.com/fluxguardian)*"""

    def test_title_contains_severity(self, rename_hero: BlastRadiusReport) -> None:
        reporter, _ = _make_reporter(self._MOCK_MARKDOWN)
        result = reporter.generate(rename_hero)
        assert "FluxGuardian" in result.markdown
        assert "HIGH" in result.markdown

    def test_contains_severity_emoji(self, rename_hero: BlastRadiusReport) -> None:
        reporter, _ = _make_reporter(self._MOCK_MARKDOWN)
        result = reporter.generate(rename_hero)
        assert "🔴" in result.markdown

    def test_affected_assets_table_present(self, rename_hero: BlastRadiusReport) -> None:
        reporter, _ = _make_reporter(self._MOCK_MARKDOWN)
        result = reporter.generate(rename_hero)
        assert "Affected assets" in result.markdown
        assert "CFO_Weekly_Revenue" in result.markdown
        assert "Churn_Predictor_v2" in result.markdown

    def test_pii_warning_present(self, rename_hero: BlastRadiusReport) -> None:
        reporter, _ = _make_reporter(self._MOCK_MARKDOWN)
        result = reporter.generate(rename_hero)
        assert "PII" in result.markdown
        assert "⚠️" in result.markdown

    def test_migration_sql_block_present(self, rename_hero: BlastRadiusReport) -> None:
        reporter, _ = _make_reporter(self._MOCK_MARKDOWN)
        result = reporter.generate(rename_hero)
        assert "migration plan" in result.markdown.lower()
        assert "```sql" in result.markdown

    def test_owner_pings_present(self, rename_hero: BlastRadiusReport) -> None:
        reporter, _ = _make_reporter(self._MOCK_MARKDOWN)
        result = reporter.generate(rename_hero)
        assert "@priya" in result.markdown
        assert "@arjun" in result.markdown

    def test_footer_present(self, rename_hero: BlastRadiusReport) -> None:
        reporter, _ = _make_reporter(self._MOCK_MARKDOWN)
        result = reporter.generate(rename_hero)
        assert "FluxGuardian" in result.markdown
        assert "🤖" in result.markdown

    def test_tokens_tracked(self, rename_hero: BlastRadiusReport) -> None:
        reporter, _ = _make_reporter(self._MOCK_MARKDOWN)
        result = reporter.generate(rename_hero)
        assert result.tokens_used == 650  # 500 input + 150 output (mocked)


# ---------------------------------------------------------------------------
# drop_critical tests — critical severity, financial PII
# ---------------------------------------------------------------------------

class TestDropCritical:
    _MOCK_MARKDOWN = """\
## 🔴 FluxGuardian — CRITICAL severity schema change detected

**`DROP COLUMN orders.amount_cents`**

This PR permanently removes the `amount_cents` column from `orders`.
Two mission-critical assets depend on this column: the CFO Weekly Revenue
dashboard and the Fraud Detection v4 ML model. Dropping this column will
cause immediate runtime failures in both consumers.

### Affected assets

| Asset | Type | Severity | Owner |
|-------|------|----------|-------|
| CFO_Weekly_Revenue | dashboard | 🔴 CRITICAL | @priya |
| Fraud_Detection_v4 | mlmodel | 🔴 CRITICAL | @arjun |

### Safe migration plan

```sql
-- Step 1: migrate all consumers to read from a new column or alias
-- Step 2: deprecate safely first
ALTER TABLE orders
  RENAME COLUMN amount_cents TO amount_cents_deprecated;

-- Step 3: after all consumers updated, drop permanently
-- ALTER TABLE orders DROP COLUMN amount_cents_deprecated;
```

> ⚠️ **PII Warning** — `amount_cents` carries a `PII.Financial` classification.
> This change requires governance team sign-off.

> **Owners to ping:** @priya @arjun

---
*🤖 Generated by [FluxGuardian](https://github.com/fluxguardian)*"""

    def test_critical_emoji_in_title(self, drop_critical: BlastRadiusReport) -> None:
        reporter, _ = _make_reporter(self._MOCK_MARKDOWN)
        result = reporter.generate(drop_critical)
        assert "🔴" in result.markdown
        assert "CRITICAL" in result.markdown

    def test_financial_pii_warning(self, drop_critical: BlastRadiusReport) -> None:
        reporter, _ = _make_reporter(self._MOCK_MARKDOWN)
        result = reporter.generate(drop_critical)
        assert "PII" in result.markdown
        assert "Financial" in result.markdown or "⚠️" in result.markdown

    def test_both_owners_mentioned(self, drop_critical: BlastRadiusReport) -> None:
        reporter, _ = _make_reporter(self._MOCK_MARKDOWN)
        result = reporter.generate(drop_critical)
        assert "@priya" in result.markdown
        assert "@arjun" in result.markdown

    def test_sql_block_uses_rename_not_drop(self, drop_critical: BlastRadiusReport) -> None:
        reporter, _ = _make_reporter(self._MOCK_MARKDOWN)
        result = reporter.generate(drop_critical)
        # Safe plan should use RENAME first, not DROP directly
        assert "RENAME" in result.markdown.upper() or "deprecated" in result.markdown


# ---------------------------------------------------------------------------
# safe_add tests — low severity, no PII, no downstream
# ---------------------------------------------------------------------------

class TestSafeAdd:
    _MOCK_MARKDOWN = """\
## 🟢 FluxGuardian — SAFE schema change detected

**`ADD COLUMN orders.promo_code`**

This PR adds a new nullable `promo_code` column to the `orders` table.
No existing downstream consumers reference this column, so there is no
risk of breakage. This is an additive, backwards-compatible change.

### Affected assets

✅ No downstream consumers detected.

### Safe migration plan

```sql
-- Step 1: apply migration (additive change — no coordination needed)
ALTER TABLE orders ADD COLUMN promo_code TEXT;

-- Step 2: update application code to start writing to promo_code
-- Step 3: add NOT NULL constraint once backfill is complete (optional)
-- ALTER TABLE orders ALTER COLUMN promo_code SET NOT NULL;
```

> **Owners to ping:** _(no owners found)_

---
*🤖 Generated by [FluxGuardian](https://github.com/fluxguardian)*"""

    def test_safe_emoji_in_title(self, safe_add: BlastRadiusReport) -> None:
        reporter, _ = _make_reporter(self._MOCK_MARKDOWN)
        result = reporter.generate(safe_add)
        assert "🟢" in result.markdown
        assert "SAFE" in result.markdown

    def test_no_pii_warning_in_safe_report(self, safe_add: BlastRadiusReport) -> None:
        reporter, _ = _make_reporter(self._MOCK_MARKDOWN)
        result = reporter.generate(safe_add)
        assert "⚠️" not in result.markdown

    def test_no_downstream_message(self, safe_add: BlastRadiusReport) -> None:
        reporter, _ = _make_reporter(self._MOCK_MARKDOWN)
        result = reporter.generate(safe_add)
        assert "No downstream" in result.markdown or "✅" in result.markdown

    def test_add_column_sql_present(self, safe_add: BlastRadiusReport) -> None:
        reporter, _ = _make_reporter(self._MOCK_MARKDOWN)
        result = reporter.generate(safe_add)
        assert "ADD COLUMN" in result.markdown.upper()

    def test_footer_always_present(self, safe_add: BlastRadiusReport) -> None:
        reporter, _ = _make_reporter(self._MOCK_MARKDOWN)
        result = reporter.generate(safe_add)
        assert "FluxGuardian" in result.markdown
        assert "🤖" in result.markdown


# ---------------------------------------------------------------------------
# /api/report HTTP endpoint tests
# ---------------------------------------------------------------------------

class TestReportEndpoint:
    """Integration-style tests hitting the FastAPI app directly."""

    def _report_payload(self, report: BlastRadiusReport) -> dict:
        return {"report": report.model_dump(mode="json")}

    def test_rename_hero_returns_200(self, rename_hero: BlastRadiusReport) -> None:
        from fastapi.testclient import TestClient
        from app.main import app

        mock_md = "## 🔴 FluxGuardian — HIGH\n\nTest markdown"
        with patch("app.llm.claude_reporter.anthropic.Anthropic") as MockCls:
            mock_client = MagicMock()
            MockCls.return_value = mock_client
            mock_client.messages.create.return_value = _fake_response(mock_md)

            client = TestClient(app)
            resp = client.post("/api/report", json=self._report_payload(rename_hero))

        assert resp.status_code == 200
        body = resp.json()
        assert "markdown" in body
        assert "tokens_used" in body
        assert isinstance(body["markdown"], str)
        assert len(body["markdown"]) > 0

    def test_endpoint_returns_tokens_used(self, rename_hero: BlastRadiusReport) -> None:
        from fastapi.testclient import TestClient
        from app.main import app

        with patch("app.llm.claude_reporter.anthropic.Anthropic") as MockCls:
            mock_client = MagicMock()
            MockCls.return_value = mock_client
            mock_client.messages.create.return_value = _fake_response("# Test")

            client = TestClient(app)
            resp = client.post("/api/report", json=self._report_payload(rename_hero))

        assert resp.status_code == 200
        assert resp.json()["tokens_used"] == 650
