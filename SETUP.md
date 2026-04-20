# FluxGuardian — GitHub App Setup

Complete guide to wire the GitHub webhook so FluxGuardian automatically
comments on every PR that touches a `.sql` migration file.

---

## Step 1 — Create the GitHub App

1. Go to **github.com/settings/apps** → **New GitHub App**

2. Fill in:
   | Field | Value |
   |-------|-------|
   | App name | `fluxguardian` |
   | Homepage URL | `https://github.com/AjaySingh-a/fluxguardian` |
   | Webhook URL | *(leave blank for now — fill in after ngrok starts)* |
   | Webhook secret | Generate a strong random string, e.g. `openssl rand -hex 32` |

3. **Permissions → Repository permissions:**
   | Permission | Level |
   |------------|-------|
   | Contents | Read |
   | Metadata | Read |
   | Pull requests | Read & Write |

4. **Subscribe to events:** check **Pull request**

5. Click **Create GitHub App**

6. On the App settings page:
   - Note the **App ID** (a number like `1234567`)
   - Scroll to **Private keys** → **Generate a private key**
   - Download the `.pem` file, save it somewhere safe (e.g. `~/.ssh/fluxguardian.pem`)

---

## Step 2 — Set environment variables

Add to `backend/.env`:

```bash
# GitHub App
GITHUB_APP_ID=1234567
GITHUB_APP_PRIVATE_KEY_PATH=/Users/yourname/.ssh/fluxguardian.pem
GITHUB_WEBHOOK_SECRET=your-32-char-random-secret

# Set prod model for real deployments
FLUXGUARDIAN_ENV=prod
```

---

## Step 3 — Start the backend

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

Verify it's up:
```bash
curl http://localhost:8000/health
# {"status":"ok"}

curl http://localhost:8000/api/github/webhook \
  -X POST -d '{}' -H "Content-Type: application/json"
# {"status":"ignored",...}
```

---

## Step 4 — Start ngrok tunnel (macOS)

```bash
# Install once
brew install ngrok

# Authenticate (one-time, free account)
ngrok config add-authtoken YOUR_NGROK_TOKEN

# Start tunnel
ngrok http 8000
```

You'll see output like:
```
Forwarding  https://abc123.ngrok-free.app -> http://localhost:8000
```

Copy the `https://...ngrok-free.app` URL.

**macOS alternative — Homebrew:**
```bash
brew install --cask ngrok
```

---

## Step 5 — Wire the webhook URL

1. Go back to your GitHub App settings
2. Set **Webhook URL** to: `https://abc123.ngrok-free.app/api/github/webhook`
3. Click **Save changes**

---

## Step 6 — Create the demo repo

```bash
# Create repo on GitHub (requires gh CLI)
gh repo create fluxguardian-demo --public --add-readme
cd /tmp && git clone https://github.com/Devgr72/fluxguardian-demo && cd fluxguardian-demo

# Create initial migration
mkdir migrations
cat > migrations/001_initial.sql << 'SQL'
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(320) NOT NULL,
    phone VARCHAR(20),
    full_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    city VARCHAR(100)
);
SQL

git add migrations/001_initial.sql
git commit -m "chore: initial schema"
git push
```

---

## Step 7 — Install the GitHub App on the demo repo

1. Go to your GitHub App settings
2. Click **Install App** (left sidebar)
3. Install on **Devgr72/fluxguardian-demo**
4. Select **Only select repositories** → choose `fluxguardian-demo`
5. Click **Install**

---

## Step 8 — Open a test PR

```bash
cd /tmp/fluxguardian-demo

git checkout -b feat/rename-email
cat > migrations/005_rename_email.sql << 'SQL'
ALTER TABLE users RENAME COLUMN email TO contact_email;
SQL

git add migrations/005_rename_email.sql
git commit -m "feat: rename email to contact_email"
git push -u origin feat/rename-email

# Open the PR
gh pr create \
  --title "feat: rename users.email → contact_email" \
  --body "Renames the PII email column for GDPR compliance."
```

Within **5-10 seconds** FluxGuardian should post a comment like:

> ## 🔴 FluxGuardian — HIGH severity schema change detected
> **`RENAME COLUMN users.email → contact_email`**
> ...

---

## Step 9 — Simulate locally (no GitHub App needed)

```bash
# Start backend
cd backend && uvicorn app.main:app --reload --port 8000

# Fire a signed webhook payload
python3 scripts/simulate_webhook.py \
  --secret your-webhook-secret \
  --sql "ALTER TABLE users RENAME COLUMN email TO contact_email;" \
  --action opened
```

Expected output:
```
[simulate] ✓ Webhook accepted. Background pipeline started.
           Check backend logs for analysis + comment output.
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `401 Invalid webhook signature` | Double-check `GITHUB_WEBHOOK_SECRET` matches the App setting |
| No comment posted | Check backend logs; ensure `GITHUB_APP_ID` and `GITHUB_APP_PRIVATE_KEY_PATH` are correct |
| `JWT` error | Confirm the `.pem` file path is correct and readable |
| Comment posted but no analysis | Ensure the PR file ends in `.sql` and contains a valid `ALTER TABLE` statement |
| ngrok session expired | Restart ngrok and update the webhook URL in the App settings |

---

## Architecture

```
GitHub PR opened / synchronize
       │
       │  POST /api/github/webhook
       ▼
github_webhook.py
  ├─ verify HMAC-SHA256
  ├─ extract owner/repo/PR#/installation_id
  ├─ return 200 immediately
  └─ BackgroundTask:
       ├─ GitHubAppClient.get_pr_files()
       ├─ extract_sql_diffs()
       ├─ parse_schema_diff()
       ├─ BlastRadiusEngine.analyze() [→ OpenMetadata]
       ├─ ClaudeReporter.agenerate()  [→ Claude API]
       └─ GitHubAppClient.post_pr_comment()
```
