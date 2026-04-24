# FluxGuardian — Complete Setup Guide

Get from zero to live demo in **15–30 minutes**.

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Docker Desktop | 24.0+ | [docker.com](https://docker.com) |
| Python | 3.11+ | `brew install python@3.11` (Mac) |
| Node.js | 20+ | `brew install node@20` (Mac) |
| ngrok | Latest | `brew install ngrok` |
| git | Any | pre-installed on most systems |

Also needed:
- [Anthropic API key](https://console.anthropic.com)
- [ngrok account](https://ngrok.com) (free tier OK)
- GitHub account

---

## Phase 1: Clone Repository

```bash
git clone https://github.com/AjaySingh-a/fluxguardian.git
cd fluxguardian
```

---

## Phase 2: Start OpenMetadata (5 min)

```bash
cd infra/openmetadata
docker compose up -d
```

Wait 2–3 minutes for all services to become healthy:

```bash
watch -n 5 'docker compose ps'
```

All 4 services should show `(healthy)`:
- `openmetadata_mysql`
- `openmetadata_elasticsearch`
- `openmetadata_server`
- `openmetadata_ingestion`

**Verify:**
```bash
curl http://127.0.0.1:8585/api/v1/system/version
# → {"version":"1.10.3",...}
```

**Access UI:** http://127.0.0.1:8585  
**Login:** `admin@open-metadata.org` / `admin`

> **Tip:** Always use `127.0.0.1` rather than `localhost`. Python 3.13 resolves
> `localhost` to `::1` (IPv6) first, which fails when OpenMetadata only binds on
> IPv4.

---

## Phase 3: Get OpenMetadata JWT Token (2 min)

1. Log in to the OM UI
2. Click the gear icon (top-right) → **Settings**
3. Navigate: **Bots** → click **ingestion-bot**
4. Scroll to the **Token** section
5. Click **Revoke Token** → **Generate New Token**
6. Set expiry to **Unlimited**
7. Copy the full JWT string (starts with `eyJ…`)

---

## Phase 4: Seed Demo Data (3 min)

```bash
cd ../../scripts
pip install -r requirements.txt
python3 seed_openmetadata.py
```

This seeds the FoodieExpress demo dataset:
- 5 tables (users, orders, restaurants, deliveries, payments)
- 4 dashboards (CFO Weekly Revenue, Support Agent, Marketing, Fraud)
- 2 ML models (Churn Predictor v2, Fraud Detection v4)
- 2 pipelines (daily_revenue_etl, customer_enrichment_etl)
- 4 users (priya, arjun, kavya, raj) with emails
- PII tags (Email, Phone, Financial) on sensitive columns
- Column-level lineage edges

---

## Phase 5: Backend Setup (5 min)

```bash
cd ../backend
cp .env.example .env
```

Edit `.env` with your values:

```env
# OpenMetadata
OPENMETADATA_HOST=http://127.0.0.1:8585
OPENMETADATA_JWT_TOKEN=eyJ...     # from Phase 3

# GitHub App (fill in after Phase 7)
GITHUB_APP_ID=
GITHUB_APP_PRIVATE_KEY_PATH=/Users/you/.ssh/fluxguardian.pem
GITHUB_WEBHOOK_SECRET=

# Claude
ANTHROPIC_API_KEY=sk-ant-api03-...
FLUXGUARDIAN_ENV=prod             # uses claude-sonnet-4-5

# Optional
LOG_LEVEL=INFO
APP_VERSION=1.0.0
```

Install and start:

```bash
pip install -r requirements.txt
uvicorn app.main:app --port 8000 --reload
```

Verify:
```bash
curl http://127.0.0.1:8000/health
# → {"status":"ok"}
```

---

## Phase 6: Frontend Setup (3 min)

```bash
cd ../frontend
npm install
npm run dev
```

**Access:** http://localhost:3000

Pages:
- `/` — Dashboard home (recent analyses feed + governance pulse)
- `/analyze` — Paste a SQL diff → get a blast radius report
- `/lineage` — Interactive ReactFlow lineage graph
- `/governance` — Governance health snapshot

---

## Phase 7: Create GitHub App (10 min)

### 7.1 Generate Webhook Secret

```bash
openssl rand -hex 32
```

Save this value — you'll use it twice.

### 7.2 Create the App

Visit: https://github.com/settings/apps/new

| Field | Value |
|---|---|
| **GitHub App name** | `fluxguardian-bot-<yourhandle>` (globally unique) |
| **Homepage URL** | your repo URL |
| **Webhook URL** | leave blank for now |
| **Webhook secret** | paste from 7.1 |

**Repository permissions:**
- Contents: Read-only
- Metadata: Read-only (auto-set)
- Pull requests: Read and write

**Subscribe to events:** ☑ Pull request

**Where can this app be installed?** → Only on this account

Click **Create GitHub App**.

### 7.3 Download Private Key

1. Note your **App ID** (e.g. `3451129`)
2. Scroll to **Private keys** → **Generate a private key**
3. Move the downloaded file:

```bash
mv ~/Downloads/fluxguardian-bot*.private-key.pem ~/.ssh/fluxguardian.pem
chmod 600 ~/.ssh/fluxguardian.pem
```

### 7.4 Update `.env`

```env
GITHUB_APP_ID=3451129
GITHUB_APP_PRIVATE_KEY_PATH=/Users/you/.ssh/fluxguardian.pem
GITHUB_WEBHOOK_SECRET=<secret from 7.1>
```

Restart the backend (`Ctrl+C`, then `uvicorn app.main:app --port 8000 --reload`).

### 7.5 Start ngrok Tunnel

```bash
ngrok http 8000
```

Copy the HTTPS forwarding URL (e.g. `https://abc123.ngrok-free.app`).

### 7.6 Set Webhook URL in the GitHub App

1. Go to `https://github.com/settings/apps/YOUR-APP-NAME`
2. Scroll to **Webhook** → paste: `https://abc123.ngrok-free.app/api/github/webhook`
3. Tick **Active**
4. **Save changes**

### 7.7 Install App on a Test Repo

1. Click **Install App** in the left sidebar
2. **Install** → Only select repositories → choose your demo/test repo
3. Click **Install**

---

## Phase 8: End-to-End Test (3 min)

### 8.1 Clone Your Test Repo

```bash
git clone https://github.com/YOU/your-demo-repo.git
cd your-demo-repo
```

### 8.2 Create a Schema-Changing PR

```bash
git checkout -b test/rename-email
mkdir -p migrations
cat > migrations/001_rename.sql << 'SQL'
ALTER TABLE users RENAME COLUMN email TO contact_email;
SQL
git add . && git commit -m "test: rename email column"
git push -u origin test/rename-email
gh pr create --title "test: rename users.email" --body "Testing FluxGuardian"
```

### 8.3 Watch the Backend Log

```
INFO: POST /api/github/webhook 200 OK
INFO: Parsing SQL diff...
INFO: 1 schema change detected: [rename_column]
INFO: Running blast radius analysis...
INFO: 7 affected assets found
INFO: Calling Claude Sonnet 4.5...
INFO: Comment posted successfully
```

### 8.4 Check the PR

Refresh the PR in your browser — the FluxGuardian bot comment should appear within 10–15 seconds. ✨

---

## Phase 9: (Optional) Slack Bot

<details>
<summary>Expand Slack setup</summary>

### 9.1 Create a Slack App

Visit https://api.slack.com/apps → **Create New App** → From scratch.

### 9.2 Enable Socket Mode

Settings → **Socket Mode** → Enable → generate an app-level token with `connections:write`.

Copy the token (`xapp-…`) → add to `.env` as `SLACK_APP_TOKEN`.

### 9.3 Add Bot Scopes

OAuth & Permissions → Bot Token Scopes:
- `chat:write`
- `commands`
- `app_mentions:read`

### 9.4 Create Slash Command

Slash Commands → **Create New Command**:
- Command: `/fluxguardian`
- Description: Query metadata blast radius

### 9.5 Install and Start

Install App → copy Bot User OAuth Token (`xoxb-…`) → add to `.env` as `SLACK_BOT_TOKEN`.

```bash
cd slack-bot
pip install -r requirements.txt
python3 app.py
```

Test in Slack:
```
/fluxguardian what breaks if I drop users.email
```
</details>

---

## Phase 10: (Optional) Claude Desktop MCP

<details>
<summary>Expand MCP setup</summary>

Edit the Claude Desktop config:

**Mac:** `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "fluxguardian": {
      "command": "python3",
      "args": ["/absolute/path/to/fluxguardian/mcp-server/server.py"],
      "env": {
        "OPENMETADATA_HOST": "http://127.0.0.1:8585",
        "OPENMETADATA_JWT_TOKEN": "your-jwt-token"
      }
    }
  }
}
```

Restart Claude Desktop completely (Cmd+Q on Mac).

Test:
> Using fluxguardian MCP tools, what assets depend on users.email?

</details>

---

## Troubleshooting

### `404` on `/api/github/webhook`

```bash
find . -name "__pycache__" -exec rm -rf {} + 2>/dev/null
pkill -9 -f uvicorn
uvicorn app.main:app --port 8000
```

### `ConnectError: All connection attempts failed`

Use `127.0.0.1` instead of `localhost` in `.env`:

```env
OPENMETADATA_HOST=http://127.0.0.1:8585
```

Python 3.13 prefers IPv6 when resolving `localhost`, which fails when OM only listens on IPv4.

### OM containers not healthy

```bash
docker compose down
docker system prune -f
docker compose up -d
# Wait 5 min, then check: docker compose ps
```

### Webhook signature invalid

Make sure the exact same secret (no trailing spaces or quotes) is in:
- GitHub App webhook secret field
- Backend `.env` `GITHUB_WEBHOOK_SECRET`

### ngrok URL changes on every restart

Free ngrok assigns a new URL each time. Options:
1. Update the GitHub App webhook URL after each restart
2. Upgrade to ngrok Pro for a static domain
3. Use Cloudflare Tunnel (free, stable URL)

---

## Support

- Bug report: [Open an issue](https://github.com/AjaySingh-a/fluxguardian/issues)
- Docs: See [README.md](./README.md)

---

**Built with ❤️ for OpenMetadata OUTATIME 2026**
