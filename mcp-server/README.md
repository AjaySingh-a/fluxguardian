# FluxGuardian MCP Server

Exposes OpenMetadata capabilities as tools for Claude Desktop, Claude Code, and any MCP-compatible client. Ask Claude questions about your data assets in natural language — no Slack needed.

---

## Tools exposed

| Tool | Description |
|------|-------------|
| `search_assets` | Find tables, dashboards, ML models, pipelines by keyword |
| `get_column_lineage` | Upstream + downstream lineage for a column |
| `get_blast_radius` | Impact of a schema change (drop/rename/alter) |
| `find_owner` | Who owns an asset (email + Slack handle) |
| `list_pii_columns` | All PII-tagged columns across all tables |
| `get_table_schema` | Full column list with types and PII tags |

---

## Prerequisites

1. Python 3.11+
2. FluxGuardian backend running at `http://localhost:8000` (see `backend/README.md`)
3. `mcp` and `httpx` packages installed

---

## Install dependencies

```bash
cd mcp-server/
pip install mcp httpx pydantic-settings python-dotenv
```

---

## Step 1 — Add to Claude Desktop

Claude Desktop config lives at:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

Open (or create) that file and add the `mcpServers` block:

```json
{
  "mcpServers": {
    "fluxguardian": {
      "command": "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3",
      "args": [
        "/Users/devgrover/Desktop/fluxgaurdain/fluxguardian/mcp-server/server.py"
      ],
      "env": {
        "FLUXGUARDIAN_BACKEND": "http://localhost:8000"
      }
    }
  }
}
```

> If you have other MCP servers already configured, add `"fluxguardian": { ... }` inside the existing `"mcpServers"` object — don't replace the whole file.

---

## Step 2 — Restart Claude Desktop

Fully quit Claude Desktop (⌘Q on Mac, not just close the window) and reopen it.

Verify the server loaded: in a new Claude conversation, click the **🔧 Tools** icon or type a question — you should see FluxGuardian tools listed.

---

## Step 3 — Test it works

Run the smoke tests (no Claude Desktop needed):

```bash
cd mcp-server/
python test_mcp.py
```

Expected output:
```
✅ search_assets — by name (users)
✅ search_assets — by owner (priya)
✅ get_column_lineage — users.email (known PII column)
✅ get_blast_radius — drop_column users.email
✅ find_owner — CFO dashboard by short name
✅ list_pii_columns — returns all PII columns
✅ get_table_schema — users (by short name)
...
20/20 tests passed
```

---

## Step 4 — Try it in Claude Desktop

Ask Claude (with the MCP server connected):

```
What would break if I dropped the email column from the users table?
```

```
List all PII columns and tell me who owns each table.
```

```
Show me the schema for the users table and flag any sensitive columns.
```

```
Who should I ping before changing orders.amount_cents?
```

---

## Adding to Claude Code (CLI)

If you use Claude Code instead of Claude Desktop, add to your project's `.mcp.json`:

```json
{
  "mcpServers": {
    "fluxguardian": {
      "command": "python3",
      "args": ["/Users/devgrover/Desktop/fluxgaurdain/fluxguardian/mcp-server/server.py"],
      "env": {
        "FLUXGUARDIAN_BACKEND": "http://localhost:8000"
      }
    }
  }
}
```

Or add globally via Claude Code settings.

---

## Running the server manually (debug)

```bash
cd mcp-server/

# Print registered tools and exit (quick sanity check)
python server.py --test

# Run as stdio server (this is what Claude Desktop does automatically)
FLUXGUARDIAN_BACKEND=http://localhost:8000 python server.py
```

The server communicates over stdin/stdout (MCP stdio transport). Claude Desktop manages the process lifecycle — you don't need to keep a terminal open.

---

## Architecture

```
Claude Desktop
     │  MCP stdio transport
     ▼
server.py  ──── list_tools() → returns TOOL_DEFINITIONS
               call_tool()  → dispatches to tools.py
                                    │
                         ┌──────────┴──────────┐
                         ▼                     ▼
                  Real backend            Stub fallback
                  (localhost:8000)        (FoodieExpress
                                           demo data)
```

Tools try the backend first. If the endpoint returns 404 or the backend is unreachable, they fall back to FoodieExpress stub data. Wire full backend on Day 3.

---

## Troubleshooting

**Claude Desktop doesn't show FluxGuardian tools**
- Confirm the config file path is exact (copy-paste from above)
- Make sure you fully quit and relaunched Claude Desktop
- Run `python server.py --test` to confirm the server starts correctly
- Check Claude Desktop logs: `~/Library/Logs/Claude/mcp*.log`

**Tool returns stub data instead of real OM data**
- Confirm backend is running: `curl http://localhost:8000/health`
- Confirm backend has the `/api/search` endpoint: `curl "http://localhost:8000/api/search?q=users"`

**SSL errors on macOS**
```bash
/Applications/Python\ 3.13/Install\ Certificates.command
```
