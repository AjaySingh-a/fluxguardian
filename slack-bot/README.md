# FluxGuardian Slack Bot

Natural-language queries over your OpenMetadata data assets, powered by Claude.

---

## How it works

```
User: /fluxguardian what breaks if I drop users.email?
         │
         ▼
  Slack (Socket Mode)
         │
         ▼
  handlers.py  →  claude_client.py  →  Claude (tool use)
                                              │
                              ┌───────────────┼───────────────┐
                              ▼               ▼               ▼
                       search_assets  get_column_impact  list_pii_columns
                              │               │               │
                              └───────────────┴───────────────┘
                                              │
                                    Backend / OM stubs
                                              │
                                    Final Slack answer
```

---

## Step 1 — Create a Slack App

1. Go to **https://api.slack.com/apps** → **Create New App** → **From scratch**
2. Name it `FluxGuardian`, pick your workspace, click **Create App**

---

## Step 2 — Enable Socket Mode

1. In the left sidebar → **Socket Mode** → toggle **Enable Socket Mode** ON
2. It will ask you to generate an App-Level Token:
   - Token name: `socket-mode`
   - Scope: `connections:write`
   - Click **Generate**
   - Copy the token (starts with `xapp-`) → this is your `SLACK_APP_TOKEN`

---

## Step 3 — Add Bot Scopes

1. Left sidebar → **OAuth & Permissions** → scroll to **Scopes** → **Bot Token Scopes**
2. Add these scopes:

| Scope | Why |
|-------|-----|
| `commands` | Handle `/fluxguardian` slash command |
| `chat:write` | Post messages |
| `app_mentions:read` | Respond to @mentions |
| `im:history` | Read DMs sent to the bot |
| `im:read` | Know which conversations are DMs |
| `im:write` | Reply in DMs |

---

## Step 4 — Add the Slash Command

1. Left sidebar → **Slash Commands** → **Create New Command**
2. Fill in:
   - Command: `/fluxguardian`
   - Request URL: `https://placeholder.example.com` (Socket Mode ignores this)
   - Short Description: `Query your data assets with FluxGuardian`
   - Usage hint: `[question]`
3. Click **Save**

---

## Step 5 — Enable Event Subscriptions (for DMs + mentions)

1. Left sidebar → **Event Subscriptions** → toggle **Enable Events** ON
2. Request URL: `https://placeholder.example.com` (ignored in Socket Mode)
3. Under **Subscribe to bot events**, add:
   - `message.im` (DMs to the bot)
   - `app_mention` (@mentions in channels)
4. Click **Save Changes**

---

## Step 6 — Install to Workspace

1. Left sidebar → **Install App** → **Install to Workspace** → **Allow**
2. Copy the **Bot User OAuth Token** (starts with `xoxb-`) → this is your `SLACK_BOT_TOKEN`

---

## Step 7 — Configure .env

```bash
cd slack-bot/
cp .env.example .env
```

Edit `.env`:
```
SLACK_BOT_TOKEN=xoxb-...      # from Step 6
SLACK_APP_TOKEN=xapp-...      # from Step 2
ANTHROPIC_API_KEY=sk-ant-...  # from your Anthropic console
FLUXGUARDIAN_BACKEND=http://localhost:8000
```

---

## Step 8 — Install Dependencies & Run

```bash
cd slack-bot/

# Create venv
python3 -m venv .venv
source .venv/bin/activate

# Install
pip install -e .

# Run (make sure your FastAPI backend is also running)
python app.py
```

You should see:
```
⚡️ Bolt app is running! (^C to quit)
```

---

## Step 9 — Test It

In Slack, find your bot or invite it to a channel:

```
/fluxguardian what breaks if I drop users.email?
/fluxguardian who owns the CFO dashboard?
/fluxguardian show me all PII columns
```

Or DM the bot directly with any question.

---

## Running with Docker

Make sure your `.env` file is populated, then:

```bash
# From project root
docker build -t fluxguardian-slack-bot ./slack-bot

docker run --env-file slack-bot/.env \
  --network host \
  fluxguardian-slack-bot
```

> `--network host` lets the container reach the FastAPI backend on localhost:8000.

---

## Debugging

Set `LOG_LEVEL=DEBUG` in `.env` to see every tool call and Claude response:

```
DEBUG    claude_client — Calling tool: get_column_impact({'column_fqn': 'users.email'})
DEBUG    claude_client — Tool result: {"column": "users.email", "affected_assets": [...]}
```

---

## Architecture Notes

- **Socket Mode** — no public URL needed; the bot connects outbound to Slack's WebSocket API
- **Tool stubs** — `claude_client.py` returns FoodieExpress demo data until Day 3 wires real backend endpoints
- **Model** — defaults to `claude-haiku-4-5-20251001` (cheap); set `CLAUDE_MODEL=claude-sonnet-4-6` for production quality
- **Thread safety** — Slack Bolt runs each handler in a thread from its internal pool; Claude calls are blocking but safe
