"""
tools.py — MCP tool implementations for FluxGuardian.

Each public function calls the FluxGuardian FastAPI backend.
Stub fallbacks (FoodieExpress demo data) are used when the backend
endpoint returns 404 or is unreachable — Day 3 wires these fully.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx
from pydantic import BaseModel, field_validator

log = logging.getLogger(__name__)

BACKEND = os.getenv("FLUXGUARDIAN_BACKEND", "http://localhost:8000").rstrip("/")

# ---------------------------------------------------------------------------
# Input models (Pydantic validates what Claude passes in)
# ---------------------------------------------------------------------------

class SearchAssetsInput(BaseModel):
    query: str
    type: str | None = None  # table | dashboard | mlmodel | pipeline

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str | None) -> str | None:
        allowed = {"table", "dashboard", "mlmodel", "pipeline", None}
        if v not in allowed:
            raise ValueError(f"type must be one of {allowed - {None}}")
        return v


class GetColumnLineageInput(BaseModel):
    column_fqn: str


class GetBlastRadiusInput(BaseModel):
    table: str
    column: str
    change_type: str

    @field_validator("change_type")
    @classmethod
    def validate_change_type(cls, v: str) -> str:
        allowed = {"drop_column", "add_column", "rename_column", "alter_column_type", "drop_table"}
        if v not in allowed:
            raise ValueError(f"change_type must be one of {allowed}")
        return v


class FindOwnerInput(BaseModel):
    asset_fqn: str


class GetTableSchemaInput(BaseModel):
    table_fqn: str


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def _get(path: str, params: dict | None = None) -> Any | None:
    """GET from backend; returns None on 404 or connection error."""
    try:
        r = httpx.get(f"{BACKEND}{path}", params=params, timeout=8.0)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        log.warning("Backend unreachable at %s%s: %s", BACKEND, path, exc)
        return None
    except httpx.HTTPStatusError as exc:
        log.warning("Backend error %s for %s: %s", exc.response.status_code, path, exc)
        return None


def _post(path: str, body: dict) -> Any | None:
    """POST to backend; returns None on error."""
    try:
        r = httpx.post(f"{BACKEND}{path}", json=body, timeout=15.0)
        r.raise_for_status()
        return r.json()
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        log.warning("Backend unreachable at %s%s: %s", BACKEND, path, exc)
        return None
    except httpx.HTTPStatusError as exc:
        log.warning("Backend error %s for %s: %s", exc.response.status_code, path, exc)
        return None


# ---------------------------------------------------------------------------
# Stub data (FoodieExpress demo — replaced by real OM data on Day 3)
# ---------------------------------------------------------------------------

_STUB_ASSETS = [
    {"name": "users",                    "type": "table",     "fqn": "FoodieExpressPostgres.foodieexpress.public.users",       "owner": "raj@foodie.com"},
    {"name": "orders",                   "type": "table",     "fqn": "FoodieExpressPostgres.foodieexpress.public.orders",      "owner": "raj@foodie.com"},
    {"name": "restaurants",              "type": "table",     "fqn": "FoodieExpressPostgres.foodieexpress.public.restaurants", "owner": None},
    {"name": "deliveries",               "type": "table",     "fqn": "FoodieExpressPostgres.foodieexpress.public.deliveries",  "owner": None},
    {"name": "payments",                 "type": "table",     "fqn": "FoodieExpressPostgres.foodieexpress.public.payments",    "owner": None},
    {"name": "cfo_weekly_revenue",       "type": "dashboard", "fqn": "Looker.cfo_weekly_revenue",                             "owner": "priya@foodie.com"},
    {"name": "support_agent_console",    "type": "dashboard", "fqn": "Metabase.support_agent_console",                        "owner": "kavya@foodie.com"},
    {"name": "marketing_regional_cohorts","type": "dashboard","fqn": "Tableau.marketing_regional_cohorts",                    "owner": "raj@foodie.com"},
    {"name": "fraud_alerts_live",        "type": "dashboard", "fqn": "Superset.fraud_alerts_live",                            "owner": "kavya@foodie.com"},
    {"name": "churn_predictor_v2",       "type": "mlmodel",   "fqn": "InternalML.churn_predictor_v2",                         "owner": "arjun@foodie.com"},
    {"name": "fraud_detection_v4",       "type": "mlmodel",   "fqn": "InternalML.fraud_detection_v4",                         "owner": "arjun@foodie.com"},
    {"name": "daily_revenue_etl",        "type": "pipeline",  "fqn": "Airflow.daily_revenue_etl",                             "owner": "priya@foodie.com"},
    {"name": "customer_enrichment_etl",  "type": "pipeline",  "fqn": "dbt.customer_enrichment_etl",                           "owner": None},
]

_STUB_SCHEMAS: dict[str, list[dict]] = {
    "users": [
        {"name": "id",         "type": "UUID",    "nullable": False, "pii": False, "tags": []},
        {"name": "email",      "type": "VARCHAR", "nullable": False, "pii": True,  "tags": ["PII.Email"]},
        {"name": "phone",      "type": "VARCHAR", "nullable": True,  "pii": True,  "tags": ["PII.Phone"]},
        {"name": "full_name",  "type": "VARCHAR", "nullable": False, "pii": False, "tags": []},
        {"name": "created_at", "type": "TIMESTAMP","nullable": False,"pii": False, "tags": []},
        {"name": "city",       "type": "VARCHAR", "nullable": True,  "pii": False, "tags": []},
    ],
    "orders": [
        {"name": "id",            "type": "UUID",    "nullable": False, "pii": False, "tags": []},
        {"name": "user_id",       "type": "UUID",    "nullable": False, "pii": False, "tags": []},
        {"name": "restaurant_id", "type": "UUID",    "nullable": False, "pii": False, "tags": []},
        {"name": "amount_cents",  "type": "INT",     "nullable": False, "pii": True,  "tags": ["PII.Financial"]},
        {"name": "status",        "type": "VARCHAR", "nullable": False, "pii": False, "tags": []},
        {"name": "created_at",    "type": "TIMESTAMP","nullable": False,"pii": False, "tags": []},
    ],
    "payments": [
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
    "deliveries": [
        {"name": "id",           "type": "UUID",    "nullable": False, "pii": False, "tags": []},
        {"name": "order_id",     "type": "UUID",    "nullable": False, "pii": False, "tags": []},
        {"name": "driver_id",    "type": "UUID",    "nullable": True,  "pii": False, "tags": []},
        {"name": "driver_phone", "type": "VARCHAR", "nullable": True,  "pii": True,  "tags": ["PII.Phone"]},
        {"name": "status",       "type": "VARCHAR", "nullable": False, "pii": False, "tags": []},
        {"name": "delivered_at", "type": "TIMESTAMP","nullable": True, "pii": False, "tags": []},
    ],
}

_STUB_LINEAGE: dict[str, dict] = {
    "users.email": {
        "column": "users.email",
        "upstream": [],
        "downstream": [
            {"asset": "Looker.cfo_weekly_revenue",           "type": "dashboard", "owner": "priya@foodie.com"},
            {"asset": "InternalML.churn_predictor_v2",       "type": "mlmodel",   "owner": "arjun@foodie.com"},
            {"asset": "Airflow.daily_revenue_etl",           "type": "pipeline",  "owner": "priya@foodie.com"},
            {"asset": "Tableau.marketing_regional_cohorts",  "type": "dashboard", "owner": "raj@foodie.com"},
        ],
        "pii_tags": ["PII.Email"],
    },
    "users.phone": {
        "column": "users.phone",
        "upstream": [],
        "downstream": [
            {"asset": "Metabase.support_agent_console",  "type": "dashboard", "owner": "kavya@foodie.com"},
            {"asset": "dbt.customer_enrichment_etl",     "type": "pipeline",  "owner": None},
        ],
        "pii_tags": ["PII.Phone"],
    },
    "orders.amount_cents": {
        "column": "orders.amount_cents",
        "upstream": [],
        "downstream": [
            {"asset": "Looker.cfo_weekly_revenue",       "type": "dashboard", "owner": "priya@foodie.com"},
            {"asset": "InternalML.fraud_detection_v4",  "type": "mlmodel",   "owner": "arjun@foodie.com"},
        ],
        "pii_tags": ["PII.Financial"],
    },
    "payments.card_last_4": {
        "column": "payments.card_last_4",
        "upstream": [],
        "downstream": [
            {"asset": "InternalML.fraud_detection_v4", "type": "mlmodel", "owner": "arjun@foodie.com"},
        ],
        "pii_tags": ["PII.Financial"],
    },
}


# ---------------------------------------------------------------------------
# SQL templates for get_blast_radius → /api/analyze
# Constructs a synthetic diff so the real BlastRadiusEngine can run.
# ---------------------------------------------------------------------------

_SQL_TEMPLATES: dict[str, str] = {
    "drop_column":       "ALTER TABLE {table} DROP COLUMN {column};",
    "add_column":        "ALTER TABLE {table} ADD COLUMN {column} TEXT;",
    "rename_column":     "ALTER TABLE {table} RENAME COLUMN {column} TO {column}_new;",
    "alter_column_type": "ALTER TABLE {table} ALTER COLUMN {column} TYPE TEXT;",
    "drop_table":        "DROP TABLE IF EXISTS {table};",
}

_DIFF_WRAPPER = """\
--- a/migrations/schema.sql
+++ b/migrations/schema.sql
@@ -1,0 +1,1 @@
+{sql}
"""


# ---------------------------------------------------------------------------
# Public tool functions
# ---------------------------------------------------------------------------

def search_assets(inp: SearchAssetsInput) -> str:
    """Search data assets by keyword, optionally filtered by type."""
    live = _get("/api/search", {"q": inp.query})
    if live is not None:
        results = live.get("results", live)
        if inp.type:
            results = [r for r in results if r.get("type") == inp.type]
        return json.dumps({"query": inp.query, "type_filter": inp.type, "results": results, "total": len(results)})

    # Stub fallback
    q = inp.query.lower()
    results = [
        a for a in _STUB_ASSETS
        if q in a["name"].lower()
        or q in a["fqn"].lower()
        or (a["owner"] and q in a["owner"].lower())
    ]
    if inp.type:
        results = [r for r in results if r["type"] == inp.type]
    return json.dumps({"query": inp.query, "type_filter": inp.type, "results": results, "total": len(results), "source": "stub"})


def get_column_lineage(inp: GetColumnLineageInput) -> str:
    """Get full lineage (upstream + downstream) for a column."""
    live = _get("/api/column-impact", {"fqn": inp.column_fqn})
    if live is not None:
        # Normalize backend response → consistent MCP schema
        return json.dumps({
            "column": live.get("column", inp.column_fqn),
            "upstream": [],
            "downstream": live.get("affected_assets", []),
            "pii_tags": live.get("tags", []),
            "pii": live.get("pii", False),
        })

    # Stub fallback
    parts = inp.column_fqn.lower().split(".")
    key = ".".join(parts[-2:])
    result = _STUB_LINEAGE.get(key)
    if result:
        return json.dumps(result | {"source": "stub"})
    return json.dumps({
        "column": inp.column_fqn,
        "upstream": [],
        "downstream": [],
        "pii_tags": [],
        "note": "Column not in stub data.",
        "source": "stub",
    })


def get_blast_radius(inp: GetBlastRadiusInput) -> str:
    """
    Compute blast radius for a schema change.
    Calls the real /api/analyze endpoint using a synthetic SQL diff.
    Falls back to stub data if the backend is unreachable.
    """
    sql_template = _SQL_TEMPLATES.get(inp.change_type)
    if not sql_template:
        return json.dumps({"error": f"Unsupported change_type: {inp.change_type}"})

    sql = sql_template.format(table=inp.table, column=inp.column)
    diff = _DIFF_WRAPPER.format(sql=sql)

    live = _post("/api/analyze", {"diff": diff})
    if live is not None:
        return json.dumps({"change": {"table": inp.table, "column": inp.column, "type": inp.change_type}, "reports": live})

    # Stub fallback — mirror column-impact data
    col_key = f"{inp.table}.{inp.column}".lower()
    lineage = _STUB_LINEAGE.get(col_key, {})
    affected = [
        {"name": a["asset"].split(".")[-1], "type": a["type"], "owner": a["owner"], "severity": "high"}
        for a in lineage.get("downstream", [])
    ]
    return json.dumps({
        "change": {"table": inp.table, "column": inp.column, "type": inp.change_type},
        "affected_assets": affected,
        "pii_involved": bool(lineage.get("pii_tags")),
        "pii_tags": lineage.get("pii_tags", []),
        "overall_severity": "critical" if inp.change_type in ("drop_column", "drop_table") else "high",
        "source": "stub",
    })


def find_owner(inp: FindOwnerInput) -> str:
    """Find the owner of any data asset."""
    live = _get("/api/owner", {"fqn": inp.asset_fqn})
    if live is not None:
        return json.dumps(live)

    fqn_lower = inp.asset_fqn.lower()
    for asset in _STUB_ASSETS:
        if fqn_lower in asset["fqn"].lower() or fqn_lower in asset["name"].lower():
            owner = asset["owner"]
            return json.dumps({
                "asset": asset["fqn"],
                "asset_type": asset["type"],
                "owner_email": owner,
                "owner_name": owner.split("@")[0].capitalize() if owner else None,
                "slack_handle": "@" + owner.split("@")[0] if owner else None,
                "source": "stub",
            })
    return json.dumps({"asset": inp.asset_fqn, "owner_email": None, "owner_name": None, "note": "Asset not found", "source": "stub"})


def list_pii_columns(_inp: None = None) -> str:
    """List every column with a PII classification tag."""
    live = _get("/api/pii-columns")
    if live is not None:
        return json.dumps(live)

    stub = [
        {"table": "users",       "column": "email",        "fqn": "FoodieExpressPostgres.foodieexpress.public.users.email",        "tags": ["PII.Email"]},
        {"table": "users",       "column": "phone",        "fqn": "FoodieExpressPostgres.foodieexpress.public.users.phone",        "tags": ["PII.Phone"]},
        {"table": "orders",      "column": "amount_cents", "fqn": "FoodieExpressPostgres.foodieexpress.public.orders.amount_cents", "tags": ["PII.Financial"]},
        {"table": "payments",    "column": "card_last_4",  "fqn": "FoodieExpressPostgres.foodieexpress.public.payments.card_last_4","tags": ["PII.Financial"]},
        {"table": "restaurants", "column": "owner_contact","fqn": "FoodieExpressPostgres.foodieexpress.public.restaurants.owner_contact","tags": ["PII.Phone"]},
        {"table": "deliveries",  "column": "driver_phone", "fqn": "FoodieExpressPostgres.foodieexpress.public.deliveries.driver_phone","tags": ["PII.Phone"]},
    ]
    return json.dumps({"pii_columns": stub, "total": len(stub), "source": "stub"})


def get_table_schema(inp: GetTableSchemaInput) -> str:
    """Get the full column schema for a table including types and PII tags."""
    live = _get("/api/table-schema", {"fqn": inp.table_fqn})
    if live is not None:
        return json.dumps(live)

    # Stub: match on the last segment of the FQN
    table_name = inp.table_fqn.split(".")[-1].lower()
    columns = _STUB_SCHEMAS.get(table_name)
    if columns:
        return json.dumps({
            "table": inp.table_fqn,
            "columns": columns,
            "column_count": len(columns),
            "pii_column_count": sum(1 for c in columns if c["pii"]),
            "source": "stub",
        })
    return json.dumps({
        "table": inp.table_fqn,
        "columns": [],
        "note": "Table not found in stub data.",
        "source": "stub",
    })
