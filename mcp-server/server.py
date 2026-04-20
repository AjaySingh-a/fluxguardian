"""
server.py — FluxGuardian MCP server.

Exposes OpenMetadata capabilities as tools for Claude Desktop,
Claude Code, and any other MCP-compatible client.

Run:
    python server.py          # stdio transport (default, for Claude Desktop)
    python server.py --test   # print registered tools and exit
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any

from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

import tools as T

load_dotenv()

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("fluxguardian-mcp")

# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

server = Server("fluxguardian-openmetadata")

# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[types.Tool] = [
    types.Tool(
        name="search_assets",
        description=(
            "Search for data assets (tables, dashboards, ML models, pipelines) "
            "in OpenMetadata by name or keyword. Optionally filter by asset type. "
            "Use this to discover what assets exist before diving into lineage or ownership."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search keyword — e.g. 'users', 'revenue', 'email', 'priya'",
                },
                "type": {
                    "type": "string",
                    "enum": ["table", "dashboard", "mlmodel", "pipeline"],
                    "description": "Optional: filter results to a specific asset type",
                },
            },
            "required": ["query"],
        },
    ),
    types.Tool(
        name="get_column_lineage",
        description=(
            "Get the full data lineage for a specific column — both upstream sources "
            "and downstream consumers (dashboards, ML models, pipelines). "
            "Also returns PII tags on the column."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "column_fqn": {
                    "type": "string",
                    "description": (
                        "Fully-qualified column name. Examples: "
                        "'users.email', 'foodieexpress.public.users.email', "
                        "'FoodieExpressPostgres.foodieexpress.public.users.email'"
                    ),
                },
            },
            "required": ["column_fqn"],
        },
    ),
    types.Tool(
        name="get_blast_radius",
        description=(
            "Compute the blast radius of a schema change — which downstream assets "
            "would break, who owns them, and the overall severity. "
            "Use this before merging any database migration PR."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "table": {
                    "type": "string",
                    "description": "Table name, e.g. 'users' or 'public.users'",
                },
                "column": {
                    "type": "string",
                    "description": "Column name being changed, e.g. 'email'",
                },
                "change_type": {
                    "type": "string",
                    "enum": ["drop_column", "add_column", "rename_column", "alter_column_type", "drop_table"],
                    "description": "The type of schema change",
                },
            },
            "required": ["table", "column", "change_type"],
        },
    ),
    types.Tool(
        name="find_owner",
        description=(
            "Find who owns a data asset — table, dashboard, ML model, or pipeline. "
            "Returns the owner's email and Slack handle so you know who to ping."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "asset_fqn": {
                    "type": "string",
                    "description": (
                        "Asset name or fully-qualified name. Examples: "
                        "'users', 'Looker.cfo_weekly_revenue', 'InternalML.churn_predictor_v2'"
                    ),
                },
            },
            "required": ["asset_fqn"],
        },
    ),
    types.Tool(
        name="list_pii_columns",
        description=(
            "List every column across all tables that has a PII (Personally Identifiable "
            "Information) classification tag — Email, Phone, Financial, etc. "
            "Use this for compliance audits or before sharing data access."
        ),
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
    types.Tool(
        name="get_table_schema",
        description=(
            "Get the full column schema for a table — column names, data types, "
            "nullable flags, and PII tags. Use this to understand table structure "
            "before writing migrations or queries."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "table_fqn": {
                    "type": "string",
                    "description": (
                        "Table name or fully-qualified name. Examples: "
                        "'users', 'foodieexpress.public.users', "
                        "'FoodieExpressPostgres.foodieexpress.public.users'"
                    ),
                },
            },
            "required": ["table_fqn"],
        },
    ),
]

# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return TOOL_DEFINITIONS


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    log.info("call_tool: %s args=%s", name, arguments)

    try:
        result = _dispatch(name, arguments)
    except ValueError as exc:
        # Pydantic validation error — tell Claude what was wrong
        result = json.dumps({"error": f"Invalid input: {exc}"})
    except Exception as exc:
        log.exception("Unexpected error in tool %s", name)
        result = json.dumps({"error": f"Internal error: {exc}"})

    return [types.TextContent(type="text", text=result)]


def _dispatch(name: str, args: dict) -> str:
    if name == "search_assets":
        return T.search_assets(T.SearchAssetsInput(**args))
    if name == "get_column_lineage":
        return T.get_column_lineage(T.GetColumnLineageInput(**args))
    if name == "get_blast_radius":
        return T.get_blast_radius(T.GetBlastRadiusInput(**args))
    if name == "find_owner":
        return T.find_owner(T.FindOwnerInput(**args))
    if name == "list_pii_columns":
        return T.list_pii_columns()
    if name == "get_table_schema":
        return T.get_table_schema(T.GetTableSchemaInput(**args))
    return json.dumps({"error": f"Unknown tool: {name}"})


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

async def _run_server() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    # --test flag: print tool list and exit (useful for CI / smoke test)
    if "--test" in sys.argv:
        print("Registered tools:")
        for tool in TOOL_DEFINITIONS:
            print(f"  • {tool.name}: {tool.description[:60]}...")
        print(f"\nTotal: {len(TOOL_DEFINITIONS)} tools")
        print("Backend:", __import__("os").getenv("FLUXGUARDIAN_BACKEND", "http://localhost:8000"))
        return

    asyncio.run(_run_server())


if __name__ == "__main__":
    main()
