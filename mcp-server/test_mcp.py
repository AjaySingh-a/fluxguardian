"""
test_mcp.py — Smoke tests for every MCP tool.

Calls each tool directly (bypasses MCP transport) to verify:
- Input validation doesn't crash
- Stub data returns expected structure
- Backend calls fall back gracefully when backend is unreachable

Run:
    python test_mcp.py                  # uses stub data (no backend needed)
    FLUXGUARDIAN_BACKEND=http://localhost:8000 python test_mcp.py  # uses real backend
"""

from __future__ import annotations

import json
import os
import sys

# Ensure we can import from this directory
sys.path.insert(0, os.path.dirname(__file__))

import tools as T

PASS = "✅"
FAIL = "❌"
results: list[tuple[str, bool, str]] = []


def check(test_name: str, result_json: str, *required_keys: str) -> None:
    try:
        data = json.loads(result_json)
        missing = [k for k in required_keys if k not in data]
        if missing:
            results.append((test_name, False, f"Missing keys: {missing}\nGot: {json.dumps(data, indent=2)[:300]}"))
        else:
            results.append((test_name, True, json.dumps(data, indent=2)[:200]))
    except json.JSONDecodeError as exc:
        results.append((test_name, False, f"Invalid JSON: {exc}\nRaw: {result_json[:200]}"))
    except Exception as exc:
        results.append((test_name, False, str(exc)))


# ---------------------------------------------------------------------------
# search_assets
# ---------------------------------------------------------------------------

check(
    "search_assets — by name (users)",
    T.search_assets(T.SearchAssetsInput(query="users")),
    "query", "results", "total",
)

check(
    "search_assets — by owner (priya)",
    T.search_assets(T.SearchAssetsInput(query="priya")),
    "query", "results", "total",
)

check(
    "search_assets — with type filter (dashboard)",
    T.search_assets(T.SearchAssetsInput(query="revenue", type="dashboard")),
    "query", "results", "total",
)

check(
    "search_assets — no results query",
    T.search_assets(T.SearchAssetsInput(query="zzz_nonexistent_zzz")),
    "query", "results", "total",
)

# ---------------------------------------------------------------------------
# get_column_lineage
# ---------------------------------------------------------------------------

check(
    "get_column_lineage — users.email (known PII column)",
    T.get_column_lineage(T.GetColumnLineageInput(column_fqn="users.email")),
    "column", "downstream",
)

check(
    "get_column_lineage — fully-qualified FQN",
    T.get_column_lineage(T.GetColumnLineageInput(column_fqn="FoodieExpressPostgres.foodieexpress.public.users.phone")),
    "column", "downstream",
)

check(
    "get_column_lineage — unknown column (graceful)",
    T.get_column_lineage(T.GetColumnLineageInput(column_fqn="orders.unknown_col")),
    "column", "downstream",
)

# ---------------------------------------------------------------------------
# get_blast_radius
# ---------------------------------------------------------------------------

check(
    "get_blast_radius — drop_column users.email",
    T.get_blast_radius(T.GetBlastRadiusInput(table="users", column="email", change_type="drop_column")),
    "change",
)

check(
    "get_blast_radius — alter_column_type",
    T.get_blast_radius(T.GetBlastRadiusInput(table="orders", column="amount_cents", change_type="alter_column_type")),
    "change",
)

check(
    "get_blast_radius — add_column (low risk)",
    T.get_blast_radius(T.GetBlastRadiusInput(table="users", column="middle_name", change_type="add_column")),
    "change",
)

# Validation error test
try:
    T.get_blast_radius(T.GetBlastRadiusInput(table="users", column="email", change_type="invalid_type"))
    results.append(("get_blast_radius — invalid change_type rejected", False, "Should have raised ValueError"))
except Exception:
    results.append(("get_blast_radius — invalid change_type rejected", True, "Correctly raised validation error"))

# ---------------------------------------------------------------------------
# find_owner
# ---------------------------------------------------------------------------

check(
    "find_owner — users table",
    T.find_owner(T.FindOwnerInput(asset_fqn="users")),
    "asset", "owner_email",
)

check(
    "find_owner — CFO dashboard by short name",
    T.find_owner(T.FindOwnerInput(asset_fqn="cfo_weekly_revenue")),
    "asset", "owner_email",
)

check(
    "find_owner — fully-qualified FQN",
    T.find_owner(T.FindOwnerInput(asset_fqn="InternalML.churn_predictor_v2")),
    "asset", "owner_email",
)

check(
    "find_owner — unknown asset (graceful)",
    T.find_owner(T.FindOwnerInput(asset_fqn="nonexistent.asset")),
    "asset", "owner_email",
)

# ---------------------------------------------------------------------------
# list_pii_columns
# ---------------------------------------------------------------------------

check(
    "list_pii_columns — returns all PII columns",
    T.list_pii_columns(),
    "pii_columns", "total",
)

pii_result = json.loads(T.list_pii_columns())
assert pii_result["total"] >= 1, "Expected at least 1 PII column"
results.append(("list_pii_columns — total >= 1", True, f"Found {pii_result['total']} PII columns"))

# ---------------------------------------------------------------------------
# get_table_schema
# ---------------------------------------------------------------------------

check(
    "get_table_schema — users (by short name)",
    T.get_table_schema(T.GetTableSchemaInput(table_fqn="users")),
    "table", "columns",
)

check(
    "get_table_schema — orders (by short name)",
    T.get_table_schema(T.GetTableSchemaInput(table_fqn="orders")),
    "table", "columns",
)

check(
    "get_table_schema — fully-qualified FQN",
    T.get_table_schema(T.GetTableSchemaInput(table_fqn="FoodieExpressPostgres.foodieexpress.public.payments")),
    "table", "columns",
)

check(
    "get_table_schema — unknown table (graceful)",
    T.get_table_schema(T.GetTableSchemaInput(table_fqn="nonexistent_table")),
    "table", "columns",
)

# ---------------------------------------------------------------------------
# MCP server --test mode
# ---------------------------------------------------------------------------

import subprocess, sys as _sys
proc = subprocess.run(
    [_sys.executable, "server.py", "--test"],
    capture_output=True, text=True,
    cwd=os.path.dirname(__file__),
)
if proc.returncode == 0 and "6 tools" in proc.stdout:
    results.append(("server.py --test lists 6 tools", True, proc.stdout.strip()))
else:
    results.append(("server.py --test lists 6 tools", False, proc.stdout + proc.stderr))

# ---------------------------------------------------------------------------
# Print results
# ---------------------------------------------------------------------------

print(f"\n{'='*60}")
print(f"  FluxGuardian MCP Tool Smoke Tests")
print(f"  Backend: {os.getenv('FLUXGUARDIAN_BACKEND', 'http://localhost:8000')} (stub fallback if unreachable)")
print(f"{'='*60}\n")

passed = sum(1 for _, ok, _ in results if ok)
for name, ok, detail in results:
    icon = PASS if ok else FAIL
    print(f"{icon} {name}")
    if not ok:
        print(f"   {detail}")

print(f"\n{passed}/{len(results)} tests passed")
if passed < len(results):
    sys.exit(1)
