"""
claude_client.py — Claude API wrapper with tool-use loop.

Tools call the FluxGuardian backend at FLUXGUARDIAN_BACKEND.
Tool implementations are stubbed with FoodieExpress demo data until
Person A wires the real backend endpoints (Day 3).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import anthropic
import httpx
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
BACKEND_URL = os.getenv("FLUXGUARDIAN_BACKEND", "http://localhost:8000").rstrip("/")
# Use haiku for cheap dev; swap to claude-sonnet-4-6 for prod
MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")

SYSTEM_PROMPT = """\
You are FluxGuardian, an AI assistant for data teams using OpenMetadata.
You help engineers understand data lineage, ownership, PII classifications,
and the impact of schema changes. Use the provided tools to answer questions
about tables, columns, dashboards, and their relationships.

When reporting blast radius, use emoji indicators:
🔴 Critical  🟠 High  🟡 Medium  🟢 Low

Always mention asset owners so engineers know who to ping. Use Slack
markdown formatting: bold, italic, code, > blockquote.

Be concise. Answer in under 400 words unless asked for detail.\
"""

# ---------------------------------------------------------------------------
# Tool definitions (Claude sees these as its available tools)
# ---------------------------------------------------------------------------

TOOLS: list[dict[str, Any]] = [
    {
        "name": "search_assets",
        "description": (
            "Search for data assets (tables, dashboards, ML models, pipelines) "
            "by name or keyword. Returns matching asset names, types, and owners."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search term — e.g. 'users', 'revenue', 'email'",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_column_impact",
        "description": (
            "Get the blast radius for a specific column — which downstream dashboards, "
            "ML models, and pipelines would break if this column changed or was dropped. "
            "Also returns PII status and tags."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "column_fqn": {
                    "type": "string",
                    "description": (
                        "Fully-qualified column name, e.g. "
                        "'foodieexpress.public.users.email' or 'users.email'"
                    ),
                }
            },
            "required": ["column_fqn"],
        },
    },
    {
        "name": "find_owner",
        "description": "Look up who owns a data asset (table, dashboard, ML model, pipeline).",
        "input_schema": {
            "type": "object",
            "properties": {
                "asset_fqn": {
                    "type": "string",
                    "description": (
                        "Asset fully-qualified name, e.g. "
                        "'foodieexpress.public.users' or 'Looker.cfo_weekly_revenue'"
                    ),
                }
            },
            "required": ["asset_fqn"],
        },
    },
    {
        "name": "list_pii_columns",
        "description": "List every column in the database that has a PII classification tag.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]

# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------
# Each function first tries the real backend endpoint.
# Falls back to FoodieExpress stub data if the endpoint isn't built yet.
# Replace stubs with real backend calls on Day 3.
# ---------------------------------------------------------------------------

_STUB_ASSETS = [
    {"name": "users", "type": "table", "fqn": "FoodieExpressPostgres.foodieexpress.public.users", "owner": "raj@foodie.com"},
    {"name": "orders", "type": "table", "fqn": "FoodieExpressPostgres.foodieexpress.public.orders", "owner": "raj@foodie.com"},
    {"name": "restaurants", "type": "table", "fqn": "FoodieExpressPostgres.foodieexpress.public.restaurants", "owner": None},
    {"name": "deliveries", "type": "table", "fqn": "FoodieExpressPostgres.foodieexpress.public.deliveries", "owner": None},
    {"name": "payments", "type": "table", "fqn": "FoodieExpressPostgres.foodieexpress.public.payments", "owner": None},
    {"name": "cfo_weekly_revenue", "type": "dashboard", "fqn": "Looker.cfo_weekly_revenue", "owner": "priya@foodie.com"},
    {"name": "support_agent_console", "type": "dashboard", "fqn": "Metabase.support_agent_console", "owner": "kavya@foodie.com"},
    {"name": "marketing_regional_cohorts", "type": "dashboard", "fqn": "Tableau.marketing_regional_cohorts", "owner": "raj@foodie.com"},
    {"name": "fraud_alerts_live", "type": "dashboard", "fqn": "Superset.fraud_alerts_live", "owner": "kavya@foodie.com"},
    {"name": "churn_predictor_v2", "type": "mlmodel", "fqn": "InternalML.churn_predictor_v2", "owner": "arjun@foodie.com"},
    {"name": "fraud_detection_v4", "type": "mlmodel", "fqn": "InternalML.fraud_detection_v4", "owner": "arjun@foodie.com"},
    {"name": "daily_revenue_etl", "type": "pipeline", "fqn": "Airflow.daily_revenue_etl", "owner": "priya@foodie.com"},
    {"name": "customer_enrichment_etl", "type": "pipeline", "fqn": "dbt.customer_enrichment_etl", "owner": None},
]

_STUB_COLUMN_IMPACTS: dict[str, dict] = {
    "users.email": {
        "column": "users.email",
        "affected_assets": [
            {"name": "CFO Weekly Revenue", "type": "dashboard", "fqn": "Looker.cfo_weekly_revenue", "owner": "priya@foodie.com", "severity": "high"},
            {"name": "Churn Predictor v2", "type": "mlmodel", "fqn": "InternalML.churn_predictor_v2", "owner": "arjun@foodie.com", "severity": "high"},
            {"name": "daily_revenue_etl", "type": "pipeline", "fqn": "Airflow.daily_revenue_etl", "owner": "priya@foodie.com", "severity": "medium"},
            {"name": "marketing_regional_cohorts", "type": "dashboard", "fqn": "Tableau.marketing_regional_cohorts", "owner": "raj@foodie.com", "severity": "medium"},
        ],
        "pii": True,
        "tags": ["PII.Email"],
    },
    "users.phone": {
        "column": "users.phone",
        "affected_assets": [
            {"name": "Support Agent Console", "type": "dashboard", "fqn": "Metabase.support_agent_console", "owner": "kavya@foodie.com", "severity": "high"},
            {"name": "customer_enrichment_etl", "type": "pipeline", "fqn": "dbt.customer_enrichment_etl", "owner": None, "severity": "medium"},
        ],
        "pii": True,
        "tags": ["PII.Phone"],
    },
    "orders.amount_cents": {
        "column": "orders.amount_cents",
        "affected_assets": [
            {"name": "CFO Weekly Revenue", "type": "dashboard", "fqn": "Looker.cfo_weekly_revenue", "owner": "priya@foodie.com", "severity": "high"},
            {"name": "Fraud Detection v4", "type": "mlmodel", "fqn": "InternalML.fraud_detection_v4", "owner": "arjun@foodie.com", "severity": "high"},
        ],
        "pii": False,
        "tags": [],
    },
    "payments.card_last_4": {
        "column": "payments.card_last_4",
        "affected_assets": [
            {"name": "Fraud Detection v4", "type": "mlmodel", "fqn": "InternalML.fraud_detection_v4", "owner": "arjun@foodie.com", "severity": "high"},
        ],
        "pii": True,
        "tags": ["PII.Financial"],
    },
}

_STUB_PII_COLUMNS = [
    {"table": "users", "column": "email", "fqn": "FoodieExpressPostgres.foodieexpress.public.users.email", "tags": ["PII.Email"]},
    {"table": "users", "column": "phone", "fqn": "FoodieExpressPostgres.foodieexpress.public.users.phone", "tags": ["PII.Phone"]},
    {"table": "orders", "column": "amount_cents", "fqn": "FoodieExpressPostgres.foodieexpress.public.orders.amount_cents", "tags": ["PII.Financial"]},
    {"table": "payments", "column": "card_last_4", "fqn": "FoodieExpressPostgres.foodieexpress.public.payments.card_last_4", "tags": ["PII.Financial"]},
    {"table": "restaurants", "column": "owner_contact", "fqn": "FoodieExpressPostgres.foodieexpress.public.restaurants.owner_contact", "tags": ["PII.Phone"]},
    {"table": "deliveries", "column": "driver_phone", "fqn": "FoodieExpressPostgres.foodieexpress.public.deliveries.driver_phone", "tags": ["PII.Phone"]},
]


def _call_backend(path: str, params: dict | None = None) -> dict | list | None:
    """Try calling the real backend; returns None if endpoint not found yet."""
    try:
        r = httpx.get(f"{BACKEND_URL}{path}", params=params, timeout=5.0)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
        log.debug("Backend call to %s failed: %s — using stub", path, exc)
        return None


def _tool_search_assets(query: str) -> dict:
    live = _call_backend("/api/search", {"q": query})
    if live is not None:
        return live

    # Stub: case-insensitive substring match across name and fqn
    q = query.lower()
    matches = [
        a for a in _STUB_ASSETS
        if q in a["name"].lower()
        or q in a["fqn"].lower()
        or (a["owner"] and q in a["owner"].lower())
    ]
    return {"query": query, "results": matches, "total": len(matches), "source": "stub"}


def _tool_get_column_impact(column_fqn: str) -> dict:
    live = _call_backend("/api/column-impact", {"fqn": column_fqn})
    if live is not None:
        return live

    # Normalise to "table.column" key used in stub dict
    parts = column_fqn.lower().split(".")
    key = ".".join(parts[-2:]) if len(parts) >= 2 else column_fqn.lower()
    result = _STUB_COLUMN_IMPACTS.get(key)
    if result:
        return result | {"source": "stub"}

    return {
        "column": column_fqn,
        "affected_assets": [],
        "pii": False,
        "tags": [],
        "note": "Column not found in stub data. Wire real backend on Day 3.",
        "source": "stub",
    }


def _tool_find_owner(asset_fqn: str) -> dict:
    live = _call_backend("/api/owner", {"fqn": asset_fqn})
    if live is not None:
        return live

    fqn_lower = asset_fqn.lower()
    for asset in _STUB_ASSETS:
        if fqn_lower in asset["fqn"].lower() or fqn_lower in asset["name"].lower():
            return {
                "asset": asset["fqn"],
                "asset_type": asset["type"],
                "owner_email": asset["owner"],
                "owner_name": asset["owner"].split("@")[0].capitalize() if asset["owner"] else None,
                "slack_handle": "@" + asset["owner"].split("@")[0] if asset["owner"] else None,
                "source": "stub",
            }

    return {"asset": asset_fqn, "owner_email": None, "owner_name": None, "note": "Asset not found", "source": "stub"}


def _tool_list_pii_columns() -> dict:
    live = _call_backend("/api/pii-columns")
    if live is not None:
        return live

    return {"pii_columns": _STUB_PII_COLUMNS, "total": len(_STUB_PII_COLUMNS), "source": "stub"}


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

_TOOL_FNS = {
    "search_assets": lambda inp: _tool_search_assets(inp["query"]),
    "get_column_impact": lambda inp: _tool_get_column_impact(inp["column_fqn"]),
    "find_owner": lambda inp: _tool_find_owner(inp["asset_fqn"]),
    "list_pii_columns": lambda inp: _tool_list_pii_columns(),
}


def _run_tool(name: str, inputs: dict) -> str:
    fn = _TOOL_FNS.get(name)
    if not fn:
        return json.dumps({"error": f"Unknown tool: {name}"})
    try:
        result = fn(inputs)
        return json.dumps(result, default=str)
    except Exception as exc:
        log.exception("Tool %s raised", name)
        return json.dumps({"error": str(exc)})


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def ask_with_tools(question: str) -> str:
    """
    Send the question to Claude with tools available.
    Runs the tool-use agentic loop until Claude produces a final text answer.
    Returns the final Slack-formatted answer string.
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    messages: list[dict] = [{"role": "user", "content": question}]

    max_iterations = 8
    for iteration in range(max_iterations):
        log.debug("Claude iteration %d, messages: %d", iteration, len(messages))

        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        log.debug("stop_reason=%s", response.stop_reason)

        # Collect all text blocks for a potential final answer
        text_parts = [b.text for b in response.content if b.type == "text"]

        # If no tool use, we're done
        if response.stop_reason == "end_turn":
            return "\n".join(text_parts) or "I couldn't find an answer to that question."

        # Process tool_use blocks
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:
            # stop_reason was something else (e.g. max_tokens) but no tools
            return "\n".join(text_parts) or "I ran out of space answering that."

        # Append Claude's response (including tool_use blocks) to messages
        messages.append({"role": "assistant", "content": response.content})

        # Execute all tools and build tool_result blocks
        tool_results = []
        for tu in tool_uses:
            log.info("Calling tool: %s(%s)", tu.name, tu.input)
            result_json = _run_tool(tu.name, tu.input)
            log.debug("Tool result for %s: %s", tu.name, result_json[:200])
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": result_json,
            })

        messages.append({"role": "user", "content": tool_results})

    # Safety valve — shouldn't reach here in practice
    log.warning("Reached max iterations (%d) without final answer", max_iterations)
    return "I hit my thinking limit on that one. Try a more specific question."
