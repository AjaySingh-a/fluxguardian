"""
assets.py — Query endpoints backed by real OpenMetadata data.

Each endpoint tries the live OM instance first; on any exception
(OM unreachable, 404, etc.) it falls back to FoodieExpress stub data
so demos always work without OM running.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Query

from app.clients.openmetadata import OpenMetadataClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["assets"])

# ---------------------------------------------------------------------------
# OM FQN constants for the seeded FoodieExpress dataset
# ---------------------------------------------------------------------------

_OM_SERVICE  = "FoodieExpressPostgres"
_OM_DATABASE = "foodieexpress"
_OM_SCHEMA   = "public"
_OM_PREFIX   = f"{_OM_SERVICE}.{_OM_DATABASE}.{_OM_SCHEMA}"
_KNOWN_TABLES = ["users", "orders", "payments", "restaurants", "deliveries"]

# ---------------------------------------------------------------------------
# Stub data — used as fallback when OM is unreachable
# ---------------------------------------------------------------------------

_STUB_ASSETS = [
    {"name": "users",        "type": "table",     "fqn": f"{_OM_PREFIX}.users",                     "owner": "raj@foodie.com"},
    {"name": "orders",       "type": "table",     "fqn": f"{_OM_PREFIX}.orders",                    "owner": "raj@foodie.com"},
    {"name": "restaurants",  "type": "table",     "fqn": f"{_OM_PREFIX}.restaurants",               "owner": None},
    {"name": "deliveries",   "type": "table",     "fqn": f"{_OM_PREFIX}.deliveries",               "owner": None},
    {"name": "payments",     "type": "table",     "fqn": f"{_OM_PREFIX}.payments",                  "owner": None},
    {"name": "cfo_weekly_revenue",          "type": "dashboard", "fqn": "Looker.cfo_weekly_revenue",                 "owner": "priya@foodie.com"},
    {"name": "support_agent_console",       "type": "dashboard", "fqn": "Metabase.support_agent_console",            "owner": "kavya@foodie.com"},
    {"name": "marketing_regional_cohorts",  "type": "dashboard", "fqn": "Tableau.marketing_regional_cohorts",        "owner": "raj@foodie.com"},
    {"name": "fraud_alerts_live",           "type": "dashboard", "fqn": "Superset.fraud_alerts_live",                "owner": "kavya@foodie.com"},
    {"name": "churn_predictor_v2",          "type": "mlmodel",   "fqn": "InternalML.churn_predictor_v2",             "owner": "arjun@foodie.com"},
    {"name": "fraud_detection_v4",          "type": "mlmodel",   "fqn": "InternalML.fraud_detection_v4",             "owner": "arjun@foodie.com"},
    {"name": "daily_revenue_etl",           "type": "pipeline",  "fqn": "Airflow.daily_revenue_etl",                 "owner": "priya@foodie.com"},
    {"name": "customer_enrichment_etl",     "type": "pipeline",  "fqn": "dbt.customer_enrichment_etl",               "owner": None},
]

_STUB_COLUMN_IMPACTS: dict[str, dict] = {
    "users.email": {
        "column": "users.email", "pii": True, "tags": ["PII.Email"],
        "affected_assets": [
            {"name": "CFO Weekly Revenue",          "type": "dashboard", "fqn": "Looker.cfo_weekly_revenue",          "owner": "priya@foodie.com", "severity": "high"},
            {"name": "Churn Predictor v2",          "type": "mlmodel",   "fqn": "InternalML.churn_predictor_v2",      "owner": "arjun@foodie.com", "severity": "high"},
            {"name": "daily_revenue_etl",           "type": "pipeline",  "fqn": "Airflow.daily_revenue_etl",          "owner": "priya@foodie.com", "severity": "medium"},
            {"name": "marketing_regional_cohorts",  "type": "dashboard", "fqn": "Tableau.marketing_regional_cohorts", "owner": "raj@foodie.com",   "severity": "medium"},
        ],
    },
    "users.phone": {
        "column": "users.phone", "pii": True, "tags": ["PII.Phone"],
        "affected_assets": [
            {"name": "Support Agent Console",  "type": "dashboard", "fqn": "Metabase.support_agent_console",  "owner": "kavya@foodie.com", "severity": "high"},
            {"name": "customer_enrichment_etl","type": "pipeline",  "fqn": "dbt.customer_enrichment_etl",     "owner": None,               "severity": "medium"},
        ],
    },
    "orders.amount_cents": {
        "column": "orders.amount_cents", "pii": False, "tags": [],
        "affected_assets": [
            {"name": "CFO Weekly Revenue",  "type": "dashboard", "fqn": "Looker.cfo_weekly_revenue",     "owner": "priya@foodie.com", "severity": "high"},
            {"name": "Fraud Detection v4",  "type": "mlmodel",   "fqn": "InternalML.fraud_detection_v4", "owner": "arjun@foodie.com", "severity": "high"},
        ],
    },
    "payments.card_last_4": {
        "column": "payments.card_last_4", "pii": True, "tags": ["PII.Financial"],
        "affected_assets": [
            {"name": "Fraud Detection v4", "type": "mlmodel", "fqn": "InternalML.fraud_detection_v4", "owner": "arjun@foodie.com", "severity": "high"},
        ],
    },
}

_STUB_PII_COLUMNS = [
    {"table": "users",       "column": "email",        "fqn": f"{_OM_PREFIX}.users.email",              "tags": ["PII.Email"]},
    {"table": "users",       "column": "phone",        "fqn": f"{_OM_PREFIX}.users.phone",              "tags": ["PII.Phone"]},
    {"table": "orders",      "column": "amount_cents", "fqn": f"{_OM_PREFIX}.orders.amount_cents",      "tags": ["PII.Financial"]},
    {"table": "payments",    "column": "card_last_4",  "fqn": f"{_OM_PREFIX}.payments.card_last_4",     "tags": ["PII.Financial"]},
    {"table": "restaurants", "column": "owner_contact","fqn": f"{_OM_PREFIX}.restaurants.owner_contact","tags": ["PII.Phone"]},
    {"table": "deliveries",  "column": "driver_phone", "fqn": f"{_OM_PREFIX}.deliveries.driver_phone",  "tags": ["PII.Phone"]},
]

_STUB_TABLE_SCHEMAS: dict[str, list[dict]] = {
    "users":       [
        {"name": "id",         "type": "UUID",      "nullable": False, "pii": False, "tags": []},
        {"name": "email",      "type": "VARCHAR",   "nullable": False, "pii": True,  "tags": ["PII.Email"]},
        {"name": "phone",      "type": "VARCHAR",   "nullable": True,  "pii": True,  "tags": ["PII.Phone"]},
        {"name": "full_name",  "type": "VARCHAR",   "nullable": False, "pii": False, "tags": []},
        {"name": "created_at", "type": "TIMESTAMP", "nullable": False, "pii": False, "tags": []},
        {"name": "city",       "type": "VARCHAR",   "nullable": True,  "pii": False, "tags": []},
    ],
    "orders":      [
        {"name": "id",            "type": "UUID",      "nullable": False, "pii": False, "tags": []},
        {"name": "user_id",       "type": "UUID",      "nullable": False, "pii": False, "tags": []},
        {"name": "restaurant_id", "type": "UUID",      "nullable": False, "pii": False, "tags": []},
        {"name": "amount_cents",  "type": "INT",       "nullable": False, "pii": True,  "tags": ["PII.Financial"]},
        {"name": "status",        "type": "VARCHAR",   "nullable": False, "pii": False, "tags": []},
        {"name": "created_at",    "type": "TIMESTAMP", "nullable": False, "pii": False, "tags": []},
    ],
    "payments":    [
        {"name": "id",           "type": "UUID",    "nullable": False, "pii": False, "tags": []},
        {"name": "order_id",     "type": "UUID",    "nullable": False, "pii": False, "tags": []},
        {"name": "card_last_4",  "type": "VARCHAR", "nullable": True,  "pii": True,  "tags": ["PII.Financial"]},
        {"name": "amount_cents", "type": "INT",     "nullable": False, "pii": False, "tags": []},
        {"name": "status",       "type": "VARCHAR", "nullable": False, "pii": False, "tags": []},
    ],
    "restaurants": [
        {"name": "id",            "type": "UUID",    "nullable": False, "pii": False, "tags": []},
        {"name": "name",          "type": "VARCHAR", "nullable": False, "pii": False, "tags": []},
        {"name": "cuisine",       "type": "VARCHAR", "nullable": True,  "pii": False, "tags": []},
        {"name": "city",          "type": "VARCHAR", "nullable": True,  "pii": False, "tags": []},
        {"name": "rating",        "type": "DECIMAL", "nullable": True,  "pii": False, "tags": []},
        {"name": "owner_contact", "type": "VARCHAR", "nullable": True,  "pii": True,  "tags": ["PII.Phone"]},
    ],
    "deliveries":  [
        {"name": "id",           "type": "UUID",      "nullable": False, "pii": False, "tags": []},
        {"name": "order_id",     "type": "UUID",      "nullable": False, "pii": False, "tags": []},
        {"name": "driver_id",    "type": "UUID",      "nullable": True,  "pii": False, "tags": []},
        {"name": "driver_phone", "type": "VARCHAR",   "nullable": True,  "pii": True,  "tags": ["PII.Phone"]},
        {"name": "status",       "type": "VARCHAR",   "nullable": False, "pii": False, "tags": []},
        {"name": "delivered_at", "type": "TIMESTAMP", "nullable": True,  "pii": False, "tags": []},
    ],
}

_RECENT_PRS = [
    {
        "id": "1842", "prNumber": 1842, "repo": "foodieexpress/warehouse",
        "title": "Drop legacy users.email column", "severity": "breaking",
        "columnsAffected": [{"table": "users", "column": "email"}],
        "downstreamCount": 4,
        "downstreamSummary": "Marketing Cohorts · Churn Predictor v2 · daily_revenue_etl · CFO Weekly",
        "owners": [{"id": "priya", "name": "Priya Sharma", "role": "Finance"}, {"id": "arjun", "name": "Arjun Verma", "role": "ML Platform"}],
        "author": "ananya.k", "createdAt": "2026-04-20T10:00:00Z",
    },
    {
        "id": "1841", "prNumber": 1841, "repo": "foodieexpress/payments-svc",
        "title": "Rename payments.captured_at → payments.settled_at", "severity": "breaking",
        "columnsAffected": [{"table": "payments", "column": "captured_at"}],
        "downstreamCount": 2, "downstreamSummary": "daily_revenue_etl · Fraud Detection v4",
        "owners": [{"id": "priya", "name": "Priya Sharma", "role": "Finance"}, {"id": "arjun", "name": "Arjun Verma", "role": "ML Platform"}],
        "author": "neel.k", "createdAt": "2026-04-20T09:35:00Z",
    },
    {
        "id": "1840", "prNumber": 1840, "repo": "foodieexpress/orders-svc",
        "title": "Rename orders.amount_cents → orders.total_cents", "severity": "breaking",
        "columnsAffected": [{"table": "orders", "column": "amount_cents"}],
        "downstreamCount": 3, "downstreamSummary": "daily_revenue_etl · CFO Weekly · Fraud Detection v4",
        "owners": [{"id": "priya", "name": "Priya Sharma", "role": "Finance"}],
        "author": "vikram.s", "createdAt": "2026-04-20T09:09:00Z",
    },
    {
        "id": "1839", "prNumber": 1839, "repo": "foodieexpress/payments-svc",
        "title": "Change payments.card_last_4 to NUMERIC(4)", "severity": "breaking",
        "columnsAffected": [{"table": "payments", "column": "card_last_4"}],
        "downstreamCount": 1, "downstreamSummary": "Fraud Detection v4",
        "owners": [{"id": "arjun", "name": "Arjun Verma", "role": "ML Platform"}, {"id": "kavya", "name": "Kavya Iyer", "role": "Compliance"}],
        "author": "neel.k", "createdAt": "2026-04-20T08:27:00Z",
    },
    {
        "id": "1838", "prNumber": 1838, "repo": "foodieexpress/warehouse",
        "title": "Tighten users.email NOT NULL", "severity": "warning",
        "columnsAffected": [{"table": "users", "column": "email"}],
        "downstreamCount": 2, "downstreamSummary": "Marketing Cohorts · customer_enrichment_etl",
        "owners": [{"id": "priya", "name": "Priya Sharma", "role": "Finance"}],
        "author": "ananya.k", "createdAt": "2026-04-20T07:43:00Z",
    },
    {
        "id": "1837", "prNumber": 1837, "repo": "foodieexpress/delivery-svc",
        "title": "Drop deliveries.driver_phone (replaced by driver_id)", "severity": "warning",
        "columnsAffected": [{"table": "deliveries", "column": "driver_phone"}],
        "downstreamCount": 1, "downstreamSummary": "Support Agent Console",
        "owners": [{"id": "kavya", "name": "Kavya Iyer", "role": "Compliance"}],
        "author": "rohan.m", "createdAt": "2026-04-20T06:53:00Z",
    },
    {
        "id": "1836", "prNumber": 1836, "repo": "foodieexpress/orders-svc",
        "title": "Add nullable orders.promo_code", "severity": "safe",
        "columnsAffected": [{"table": "orders", "column": "promo_code"}],
        "downstreamCount": 0, "downstreamSummary": "no downstream consumers",
        "owners": [{"id": "raj", "name": "Raj Khanna", "role": "Data Platform"}],
        "author": "vikram.s", "createdAt": "2026-04-20T06:18:00Z",
    },
]

# ---------------------------------------------------------------------------
# Helper — normalise the OM column data-type field
# ---------------------------------------------------------------------------

def _col_type(col: dict) -> str:
    return col.get("dataType") or col.get("columnDataType") or col.get("dataTypeDisplay") or "UNKNOWN"

def _is_not_null(col: dict) -> bool:
    return col.get("constraint") == "NOT_NULL"

def _pii_tags(col: dict) -> list[str]:
    return [
        t.get("tagFQN", t.get("name", ""))
        for t in col.get("tags", [])
        if "PII" in t.get("tagFQN", t.get("name", "")).upper()
    ]

def _all_tags(col: dict) -> list[str]:
    return [t.get("tagFQN", t.get("name", "")) for t in col.get("tags", []) if t]

def _depth_severity(depth: int, change_type: str = "rename_column") -> str:
    if change_type in ("drop_column", "drop_table"):
        return "high"
    return "high" if depth <= 1 else "medium"

def _slack_handle(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    return "@" + email.split("@")[0]

def _owner_from_table(table: dict) -> str | None:
    owners = table.get("owners") or table.get("owner") or []
    if isinstance(owners, dict):
        owners = [owners]
    if owners:
        first = owners[0]
        return first.get("email") or first.get("name") or None
    return None

# ---------------------------------------------------------------------------
# /api/search
# ---------------------------------------------------------------------------


@router.get("/search")
async def search_assets(q: str = Query(..., description="Search keyword")) -> dict[str, Any]:
    """Search assets by name or FQN. Tries live OM, falls back to stub."""
    try:
        async with OpenMetadataClient() as om:
            hits = await om.search_assets(q)
            if hits:
                results = [
                    {
                        "name": h.get("name", ""),
                        "type": h.get("type", ""),
                        "fqn":  h.get("fullyQualifiedName", ""),
                        "owner": None,
                    }
                    for h in hits
                ]
                return {"query": q, "results": results, "total": len(results), "source": "om"}
    except Exception as exc:
        logger.warning("search_assets OM call failed: %s", exc)

    ql = q.lower()
    matches = [
        a for a in _STUB_ASSETS
        if ql in a["name"].lower()
        or ql in a["fqn"].lower()
        or (a["owner"] and ql in a["owner"].lower())
    ]
    return {"query": q, "results": matches, "total": len(matches), "source": "stub"}


# ---------------------------------------------------------------------------
# /api/column-impact
# ---------------------------------------------------------------------------


@router.get("/column-impact")
async def get_column_impact(
    fqn: str = Query(..., description="Column FQN e.g. users.email"),
) -> dict[str, Any]:
    """Return blast radius for a column. Tries live OM, falls back to stub."""
    try:
        async with OpenMetadataClient() as om:
            parts = fqn.split(".")
            if len(parts) >= 2:
                col_name  = parts[-1]
                table_fqn = ".".join(parts[:-1])
            else:
                col_name  = fqn
                table_fqn = f"{_OM_PREFIX}.{fqn}"

            # Walk downstream lineage from the table
            assets = await om.get_downstream_assets(table_fqn)

            # Check PII tags on the column
            tags  = await om.get_column_tags(table_fqn, col_name)
            is_pii = any(t.upper().startswith("PII") for t in tags)

            affected = [
                {
                    "name":     a.get("name", ""),
                    "type":     a.get("type", ""),
                    "fqn":      a.get("fullyQualifiedName", ""),
                    "owner":    a.get("owner_email"),
                    "severity": _depth_severity(a.get("depth", 1)),
                }
                for a in assets
            ]
            if affected or is_pii:
                return {
                    "column":          fqn,
                    "affected_assets": affected,
                    "pii":             is_pii,
                    "tags":            tags,
                    "source":          "om",
                }
    except Exception as exc:
        logger.warning("get_column_impact OM call failed: %s", exc)

    # Stub fallback
    parts = fqn.lower().split(".")
    key   = ".".join(parts[-2:]) if len(parts) >= 2 else fqn.lower()
    result = _STUB_COLUMN_IMPACTS.get(key)
    if result:
        return {**result, "source": "stub"}
    return {"column": fqn, "affected_assets": [], "pii": False, "tags": [], "source": "stub"}


# ---------------------------------------------------------------------------
# /api/owner
# ---------------------------------------------------------------------------


@router.get("/owner")
async def find_owner(fqn: str = Query(..., description="Asset FQN")) -> dict[str, Any]:
    """Return the owner of an asset. Tries live OM, falls back to stub."""
    try:
        async with OpenMetadataClient() as om:
            table_fqn = fqn if "." in fqn else f"{_OM_PREFIX}.{fqn}"
            table     = await om.get_table_by_fqn(table_fqn)
            if table:
                email = _owner_from_table(table)
                name  = None
                owners = table.get("owners") or []
                if isinstance(owners, dict):
                    owners = [owners]
                if owners:
                    name  = owners[0].get("displayName") or owners[0].get("name")
                    email = email or owners[0].get("email")
                return {
                    "asset":       table.get("fullyQualifiedName", fqn),
                    "asset_type":  "table",
                    "owner_email": email,
                    "owner_name":  name,
                    "slack_handle": _slack_handle(email),
                    "source":      "om",
                }
    except Exception as exc:
        logger.warning("find_owner OM call failed: %s", exc)

    # Stub fallback
    fqn_lower = fqn.lower()
    for asset in _STUB_ASSETS:
        if fqn_lower in asset["fqn"].lower() or fqn_lower in asset["name"].lower():
            return {
                "asset":        asset["fqn"],
                "asset_type":   asset["type"],
                "owner_email":  asset["owner"],
                "owner_name":   asset["owner"].split("@")[0].capitalize() if asset["owner"] else None,
                "slack_handle": _slack_handle(asset["owner"]),
                "source":       "stub",
            }
    return {"asset": fqn, "owner_email": None, "owner_name": None, "source": "stub"}


# ---------------------------------------------------------------------------
# /api/pii-columns
# ---------------------------------------------------------------------------


@router.get("/pii-columns")
async def list_pii_columns() -> dict[str, Any]:
    """List all PII-tagged columns. Tries live OM, falls back to stub."""
    try:
        async with OpenMetadataClient() as om:
            pii_cols: list[dict] = []
            for table_name in _KNOWN_TABLES:
                table_fqn = f"{_OM_PREFIX}.{table_name}"
                table     = await om.get_table_by_fqn(table_fqn)
                if not table:
                    continue
                for col in table.get("columns", []):
                    ptags = _pii_tags(col)
                    if ptags:
                        col_name = col.get("name", "")
                        pii_cols.append({
                            "table":  table_name,
                            "column": col_name,
                            "fqn":    col.get("fullyQualifiedName", f"{table_fqn}.{col_name}"),
                            "tags":   ptags,
                        })
            if pii_cols:
                return {"pii_columns": pii_cols, "total": len(pii_cols), "source": "om"}
    except Exception as exc:
        logger.warning("list_pii_columns OM call failed: %s", exc)

    return {"pii_columns": _STUB_PII_COLUMNS, "total": len(_STUB_PII_COLUMNS), "source": "stub"}


# ---------------------------------------------------------------------------
# /api/table-schema
# ---------------------------------------------------------------------------


@router.get("/table-schema")
async def get_table_schema(
    fqn: str = Query(..., description="Table name or full FQN"),
) -> dict[str, Any]:
    """Return column schema for a table. Tries live OM, falls back to stub."""
    try:
        async with OpenMetadataClient() as om:
            table_fqn = fqn if fqn.count(".") >= 3 else f"{_OM_PREFIX}.{fqn.split('.')[-1]}"
            table     = await om.get_table_by_fqn(table_fqn)
            if table:
                columns = [
                    {
                        "name":     col.get("name", ""),
                        "type":     _col_type(col),
                        "nullable": not _is_not_null(col),
                        "pii":      bool(_pii_tags(col)),
                        "tags":     _all_tags(col),
                    }
                    for col in table.get("columns", [])
                ]
                return {
                    "table":            fqn,
                    "columns":          columns,
                    "column_count":     len(columns),
                    "pii_column_count": sum(1 for c in columns if c["pii"]),
                    "source":           "om",
                }
    except Exception as exc:
        logger.warning("get_table_schema OM call failed: %s", exc)

    # Stub fallback
    table_name = fqn.split(".")[-1].lower()
    columns    = _STUB_TABLE_SCHEMAS.get(table_name, [])
    return {
        "table":            fqn,
        "columns":          columns,
        "column_count":     len(columns),
        "pii_column_count": sum(1 for c in columns if c["pii"]),
        "source":           "stub",
    }


# ---------------------------------------------------------------------------
# /api/pr/recent
# ---------------------------------------------------------------------------


@router.get("/pr/recent")
async def get_recent_prs() -> list[dict[str, Any]]:
    """Recent PR analyses for the home page feed."""
    return _RECENT_PRS


@router.get("/pr/{pr_id}")
async def get_pr_detail(pr_id: str) -> dict[str, Any]:
    """Return a single PR analysis by ID."""
    for pr in _RECENT_PRS:
        if pr["id"] == pr_id:
            return pr
    return {"error": "PR not found", "id": pr_id}


# ---------------------------------------------------------------------------
# /api/governance/pulse
# ---------------------------------------------------------------------------


@router.get("/governance/pulse")
async def get_governance_pulse() -> dict[str, Any]:
    """Governance health snapshot. Tries live OM, falls back to stub."""
    try:
        async with OpenMetadataClient() as om:
            untagged_pii   = 0
            assets_no_owner = 0

            # PII columns with no PII tag (untagged): look for columns whose
            # name looks PII-ish but have no PII tag applied.
            _PII_NAME_PATTERNS = ("email", "phone", "card", "ssn", "passport", "dob", "address")
            for table_name in _KNOWN_TABLES:
                table_fqn = f"{_OM_PREFIX}.{table_name}"
                table = await om.get_table_by_fqn(table_fqn)
                if not table:
                    continue
                # Check owner
                if not _owner_from_table(table):
                    assets_no_owner += 1
                # Check columns
                for col in table.get("columns", []):
                    col_name_lower = col.get("name", "").lower()
                    looks_pii = any(pat in col_name_lower for pat in _PII_NAME_PATTERNS)
                    has_pii_tag = bool(_pii_tags(col))
                    if looks_pii and not has_pii_tag:
                        untagged_pii += 1

            return {
                "untagged_pii":     untagged_pii,
                "assets_no_owner":  assets_no_owner,
                "orphaned_nodes":   2,   # requires lineage walk — use stub value
                "source":           "om",
            }
    except Exception as exc:
        logger.warning("get_governance_pulse OM call failed: %s", exc)

    return {"untagged_pii": 3, "assets_no_owner": 7, "orphaned_nodes": 2, "source": "stub"}


# ---------------------------------------------------------------------------
# /api/assets/{fqn}/lineage
# ---------------------------------------------------------------------------


@router.get("/assets/{fqn:path}/lineage")
async def get_asset_lineage(fqn: str) -> dict[str, Any]:
    """Lineage graph for an asset. Tries live OM, falls back to stub."""
    try:
        async with OpenMetadataClient() as om:
            table_fqn = fqn if fqn.count(".") >= 3 else f"{_OM_PREFIX}.{fqn.split('.')[-1]}"
            graph = await om.get_column_lineage(
                table_fqn, upstream_depth=1, downstream_depth=3, entity_type="table"
            )

            # Build nodes list — root + all neighbours
            nodes: list[dict] = []
            seen_ids: set[str] = set()

            def _add_node(node: dict) -> None:
                nid = node.get("id", "")
                if not nid or nid in seen_ids:
                    return
                seen_ids.add(nid)
                nodes.append({
                    "id":    nid,
                    "label": node.get("displayName") or node.get("name", ""),
                    "type":  (node.get("type") or node.get("entityType") or "table").lower(),
                })

            root = graph.get("entity", {})
            _add_node(root)
            for n in graph.get("nodes", []):
                _add_node(n)

            # Edges
            edges: list[dict] = []
            for edge in graph.get("downstreamEdges", []):
                frm = edge.get("fromEntity", "")
                to  = edge.get("toEntity", "")
                if frm and to:
                    edges.append({"from": frm, "to": to, "direction": "downstream"})
            for edge in graph.get("upstreamEdges", []):
                frm = edge.get("fromEntity", "")
                to  = edge.get("toEntity", "")
                if frm and to:
                    edges.append({"from": frm, "to": to, "direction": "upstream"})

            if nodes:
                return {"fqn": fqn, "nodes": nodes, "edges": edges, "source": "om"}
    except Exception as exc:
        logger.warning("get_asset_lineage OM call failed for %s: %s", fqn, exc)

    # Stub fallback
    table_name = fqn.split(".")[-1].lower()
    _STUB_LINEAGE: dict[str, dict] = {
        "users": {
            "nodes": [
                {"id": "users",              "label": "users",                     "type": "table"},
                {"id": "cfo_weekly_revenue", "label": "CFO Weekly Revenue",        "type": "dashboard"},
                {"id": "churn_predictor_v2", "label": "Churn Predictor v2",        "type": "mlmodel"},
                {"id": "daily_revenue_etl",  "label": "daily_revenue_etl",         "type": "pipeline"},
                {"id": "marketing_cohorts",  "label": "Marketing Regional Cohorts","type": "dashboard"},
            ],
            "edges": [
                {"from": "users", "to": "cfo_weekly_revenue",  "direction": "downstream"},
                {"from": "users", "to": "churn_predictor_v2",  "direction": "downstream"},
                {"from": "users", "to": "daily_revenue_etl",   "direction": "downstream"},
                {"from": "users", "to": "marketing_cohorts",   "direction": "downstream"},
            ],
        },
        "orders": {
            "nodes": [
                {"id": "orders",             "label": "orders",            "type": "table"},
                {"id": "cfo_weekly_revenue", "label": "CFO Weekly Revenue","type": "dashboard"},
                {"id": "fraud_detection_v4", "label": "Fraud Detection v4","type": "mlmodel"},
                {"id": "daily_revenue_etl",  "label": "daily_revenue_etl", "type": "pipeline"},
            ],
            "edges": [
                {"from": "orders", "to": "cfo_weekly_revenue",  "direction": "downstream"},
                {"from": "orders", "to": "fraud_detection_v4",  "direction": "downstream"},
                {"from": "orders", "to": "daily_revenue_etl",   "direction": "downstream"},
            ],
        },
    }
    stub = _STUB_LINEAGE.get(table_name, {"nodes": [], "edges": []})
    return {"fqn": fqn, **stub, "source": "stub"}
