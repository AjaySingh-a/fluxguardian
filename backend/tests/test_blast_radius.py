"""
Integration tests for BlastRadiusEngine.

These hit the REAL OpenMetadata instance — skip automatically when unreachable.

Run with:
    pytest backend/tests/test_blast_radius.py -v
"""

import pytest
import pytest_asyncio
import httpx

from app.clients.openmetadata import OpenMetadataClient
from app.engine.blast_radius import BlastRadiusEngine, BlastRadiusReport
from app.parsers.schema_diff import SchemaChange
from app.config import settings

# ---------------------------------------------------------------------------
# Constants matching actual seeded FoodieExpress data in OM
# ---------------------------------------------------------------------------

OM_SERVICE = "FoodieExpressPostgres"
OM_DATABASE = "foodieexpress"
OM_SCHEMA = "public"


# ---------------------------------------------------------------------------
# Reachability guard
# ---------------------------------------------------------------------------


def is_om_reachable() -> bool:
    try:
        r = httpx.get(
            f"{settings.openmetadata_host}/api/v1/system/version",
            headers={"Authorization": f"Bearer {settings.openmetadata_jwt_token}"},
            timeout=5.0,
        )
        return r.status_code == 200
    except Exception:
        return False


om_available = pytest.mark.skipif(
    not is_om_reachable(),
    reason="OpenMetadata is not reachable at the configured host",
)


@pytest_asyncio.fixture
async def engine() -> BlastRadiusEngine:  # type: ignore[misc]
    async with OpenMetadataClient() as om:
        yield BlastRadiusEngine(om)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _change(**kwargs) -> SchemaChange:
    """Build a SchemaChange with sensible defaults for missing optional fields."""
    defaults = {
        "change_type": "rename_column",
        "table": "users",
        "risk": "high",
        "raw_sql": "+ALTER TABLE users RENAME COLUMN email TO contact_email;",
        "line_number": 1,
    }
    defaults.update(kwargs)
    return SchemaChange(**defaults)


def _analyze_kwargs() -> dict:
    return {"om_service": OM_SERVICE, "om_database": OM_DATABASE, "om_schema": OM_SCHEMA}


# ---------------------------------------------------------------------------
# Scenario A — Rename users.email (hero demo case)
# ---------------------------------------------------------------------------


@om_available
@pytest.mark.asyncio
class TestScenarioARenameUsersEmail:
    change = _change(
        change_type="rename_column",
        table="users",
        old_column="email",
        new_column="contact_email",
        risk="high",
        raw_sql="+ALTER TABLE users RENAME COLUMN email TO contact_email;",
        line_number=1,
    )

    async def test_returns_report(self, engine: BlastRadiusEngine):
        report = await engine.analyze(self.change, **_analyze_kwargs())
        assert isinstance(report, BlastRadiusReport)

    async def test_affected_assets_present(self, engine: BlastRadiusEngine):
        report = await engine.analyze(self.change, **_analyze_kwargs())
        # Seeded data: users → 5 direct (2 pipelines, 2 dashboards, 1 mlmodel)
        #              + 2 transitive (cfo dashboard, fraud mlmodel) = 7 total
        assert len(report.affected_assets) >= 2, (
            f"Expected ≥2 downstream assets, got {len(report.affected_assets)}"
        )

    async def test_affected_columns_contains_email(self, engine: BlastRadiusEngine):
        report = await engine.analyze(self.change, **_analyze_kwargs())
        assert any("email" in fqn for fqn in report.affected_columns)

    async def test_overall_severity_not_low(self, engine: BlastRadiusEngine):
        report = await engine.analyze(self.change, **_analyze_kwargs())
        # rename → high (depth-1 assets) so overall must be at least high
        assert report.overall_severity in ("critical", "high")

    async def test_summary_mentions_table_and_column(self, engine: BlastRadiusEngine):
        report = await engine.analyze(self.change, **_analyze_kwargs())
        assert "users" in report.summary_one_line
        assert "email" in report.summary_one_line

    async def test_assets_have_valid_structure(self, engine: BlastRadiusEngine):
        report = await engine.analyze(self.change, **_analyze_kwargs())
        for asset in report.affected_assets:
            assert asset.id
            assert asset.name
            assert asset.fqn
            assert asset.asset_type
            assert asset.severity in ("critical", "high", "medium", "low")
            assert asset.reason
            assert asset.depth >= 1 if hasattr(asset, "depth") else True

    async def test_depth1_assets_are_high_severity(self, engine: BlastRadiusEngine):
        report = await engine.analyze(self.change, **_analyze_kwargs())
        # All depth-1 assets should be "high" for a rename_column
        # (depth-2 would be "medium")
        severities = {a.severity for a in report.affected_assets}
        assert "high" in severities or "critical" in severities

    async def test_owners_partially_resolved(self, engine: BlastRadiusEngine):
        report = await engine.analyze(self.change, **_analyze_kwargs())
        # At least some assets should have owner info (seeded in Day 1)
        owners_with_email = [a for a in report.affected_assets if a.owner_email]
        assert len(owners_with_email) >= 1, (
            "Expected at least one asset to have an owner email"
        )

    async def test_slack_handles_derived_from_email(self, engine: BlastRadiusEngine):
        report = await engine.analyze(self.change, **_analyze_kwargs())
        for asset in report.affected_assets:
            if asset.owner_email:
                expected_handle = "@" + asset.owner_email.split("@")[0]
                assert asset.slack_handle == expected_handle

    async def test_unique_owner_emails_list(self, engine: BlastRadiusEngine):
        report = await engine.analyze(self.change, **_analyze_kwargs())
        assert len(report.unique_owner_emails) == len(set(report.unique_owner_emails))
        assert report.total_owners_to_notify == len(report.unique_owner_emails)

    async def test_pii_fields_are_bool_and_list(self, engine: BlastRadiusEngine):
        report = await engine.analyze(self.change, **_analyze_kwargs())
        assert isinstance(report.pii_involved, bool)
        assert isinstance(report.pii_classifications, list)

    async def test_analysis_timestamp_present(self, engine: BlastRadiusEngine):
        report = await engine.analyze(self.change, **_analyze_kwargs())
        assert report.analysis_timestamp is not None

    async def test_schema_change_preserved(self, engine: BlastRadiusEngine):
        report = await engine.analyze(self.change, **_analyze_kwargs())
        assert report.schema_change.change_type == "rename_column"
        assert report.schema_change.table == "users"
        assert report.schema_change.old_column == "email"


# ---------------------------------------------------------------------------
# Scenario B — Drop orders.amount_cents (critical)
# ---------------------------------------------------------------------------


@om_available
@pytest.mark.asyncio
class TestScenarioBDropOrdersColumn:
    change = _change(
        change_type="drop_column",
        table="orders",
        old_column="amount_cents",
        risk="critical",
        raw_sql="+ALTER TABLE orders DROP COLUMN amount_cents;",
        line_number=1,
    )

    async def test_overall_severity_is_critical(self, engine: BlastRadiusEngine):
        report = await engine.analyze(self.change, **_analyze_kwargs())
        assert report.overall_severity == "critical"

    async def test_affected_assets_all_critical(self, engine: BlastRadiusEngine):
        report = await engine.analyze(self.change, **_analyze_kwargs())
        for asset in report.affected_assets:
            assert asset.severity == "critical", (
                f"Asset {asset.name} should be critical but got {asset.severity}"
            )

    async def test_governance_approval_if_pii(self, engine: BlastRadiusEngine):
        report = await engine.analyze(self.change, **_analyze_kwargs())
        if report.pii_involved:
            assert report.requires_governance_approval is True

    async def test_report_structure_valid(self, engine: BlastRadiusEngine):
        report = await engine.analyze(self.change, **_analyze_kwargs())
        assert isinstance(report, BlastRadiusReport)
        assert report.schema_change.change_type == "drop_column"


# ---------------------------------------------------------------------------
# Scenario C — Add column (safe change)
# ---------------------------------------------------------------------------


@om_available
@pytest.mark.asyncio
class TestScenarioCAddColumn:
    change = _change(
        change_type="add_column",
        table="users",
        new_column="loyalty_tier",
        old_column=None,
        risk="low",
        raw_sql="+ALTER TABLE users ADD COLUMN loyalty_tier VARCHAR(20);",
        line_number=1,
    )

    async def test_no_affected_assets(self, engine: BlastRadiusEngine):
        report = await engine.analyze(self.change, **_analyze_kwargs())
        assert report.affected_assets == []

    async def test_affected_columns_empty(self, engine: BlastRadiusEngine):
        report = await engine.analyze(self.change, **_analyze_kwargs())
        assert report.affected_columns == []

    async def test_overall_severity_is_low(self, engine: BlastRadiusEngine):
        report = await engine.analyze(self.change, **_analyze_kwargs())
        assert report.overall_severity == "low"

    async def test_no_governance_approval_required(self, engine: BlastRadiusEngine):
        report = await engine.analyze(self.change, **_analyze_kwargs())
        assert report.requires_governance_approval is False

    async def test_pii_not_involved(self, engine: BlastRadiusEngine):
        report = await engine.analyze(self.change, **_analyze_kwargs())
        assert report.pii_involved is False

    async def test_zero_owners_to_notify(self, engine: BlastRadiusEngine):
        report = await engine.analyze(self.change, **_analyze_kwargs())
        assert report.total_owners_to_notify == 0

    async def test_summary_mentions_no_impact(self, engine: BlastRadiusEngine):
        report = await engine.analyze(self.change, **_analyze_kwargs())
        assert "no detected downstream impact" in report.summary_one_line.lower()


# ---------------------------------------------------------------------------
# Scenario D — Non-existent table (graceful failure)
# ---------------------------------------------------------------------------


@om_available
@pytest.mark.asyncio
class TestScenarioDNonexistentTable:
    change = _change(
        change_type="drop_column",
        table="nonexistent_table_xyz",
        old_column="foo",
        risk="critical",
        raw_sql="+ALTER TABLE nonexistent_table_xyz DROP COLUMN foo;",
        line_number=1,
    )

    async def test_no_crash(self, engine: BlastRadiusEngine):
        # Should not raise — engine must be forgiving
        report = await engine.analyze(self.change, **_analyze_kwargs())
        assert isinstance(report, BlastRadiusReport)

    async def test_no_affected_assets(self, engine: BlastRadiusEngine):
        report = await engine.analyze(self.change, **_analyze_kwargs())
        assert report.affected_assets == []

    async def test_pii_not_involved(self, engine: BlastRadiusEngine):
        report = await engine.analyze(self.change, **_analyze_kwargs())
        assert report.pii_involved is False

    async def test_summary_is_string(self, engine: BlastRadiusEngine):
        report = await engine.analyze(self.change, **_analyze_kwargs())
        assert isinstance(report.summary_one_line, str)
        assert len(report.summary_one_line) > 0


# ---------------------------------------------------------------------------
# Scenario E — End-to-end via /api/analyze HTTP endpoint
# ---------------------------------------------------------------------------


@om_available
@pytest.mark.asyncio
async def test_analyze_endpoint_rename_column():
    """POST /api/analyze returns a list of BlastRadiusReport dicts."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app

    diff = (
        "--- a/m.sql\n"
        "+++ b/m.sql\n"
        "@@ -0,0 +1,1 @@\n"
        "+ALTER TABLE users RENAME COLUMN email TO contact_email;\n"
    )
    payload = {
        "diff": diff,
        "om_service": OM_SERVICE,
        "om_database": OM_DATABASE,
        "om_schema": OM_SCHEMA,
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/analyze", json=payload, timeout=60.0)

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    report = data[0]
    assert report["schema_change"]["change_type"] == "rename_column"
    assert report["schema_change"]["table"] == "users"
    assert isinstance(report["affected_assets"], list)
    assert isinstance(report["pii_involved"], bool)
    assert report["overall_severity"] in ("critical", "high", "medium", "low")
    assert "summary_one_line" in report


@om_available
@pytest.mark.asyncio
async def test_analyze_endpoint_non_sql_diff_returns_empty():
    from httpx import ASGITransport, AsyncClient
    from app.main import app

    diff = "--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n-old\n+new\n"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/analyze", json={"diff": diff})

    assert response.status_code == 200
    assert response.json() == []
