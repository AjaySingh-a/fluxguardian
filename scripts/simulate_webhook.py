#!/usr/bin/env python3
"""
simulate_webhook.py — Simulate a GitHub PR webhook locally.

Sends a realistic pull_request.opened payload to the local backend,
signed with the configured webhook secret (or no signature if unset).

Usage:
    # From the repo root
    python3 scripts/simulate_webhook.py

    # Override defaults
    python3 scripts/simulate_webhook.py \
        --url http://localhost:8000/api/github/webhook \
        --secret my-secret \
        --action synchronize \
        --sql "ALTER TABLE orders DROP COLUMN amount_cents;"
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sys
import time
import httpx


# ---------------------------------------------------------------------------
# Payload builder
# ---------------------------------------------------------------------------

def build_payload(action: str, sql_statement: str) -> dict:
    """Build a realistic pull_request webhook payload."""
    pr_number = 42
    owner     = "Devgr72"
    repo      = "fluxguardian-demo"

    return {
        "action": action,
        "number": pr_number,
        "pull_request": {
            "number":    pr_number,
            "title":     f"[test] schema change: {sql_statement[:50]}",
            "state":     "open",
            "html_url":  f"https://github.com/{owner}/{repo}/pull/{pr_number}",
            "head": {"sha": "abc123def456", "ref": "feat/rename-email"},
            "base": {"sha": "000000000000", "ref": "main"},
            "user":  {"login": "devgrover"},
        },
        "repository": {
            "id":        999888777,
            "name":      repo,
            "full_name": f"{owner}/{repo}",
            "private":   False,
            "owner":     {"login": owner},
            "html_url":  f"https://github.com/{owner}/{repo}",
        },
        "installation": {
            "id": 12345678,   # replace with real installation ID after App setup
        },
        "sender": {"login": "devgrover"},
    }


def build_file_patch(sql_statement: str, filename: str) -> list[dict]:
    """Build a fake PR files response for patching the webhook handler tests."""
    return [
        {
            "filename": filename,
            "status": "modified",
            "additions": 1,
            "deletions": 0,
            "patch": f"@@ -0,0 +1,1 @@\n+{sql_statement}",
        }
    ]


def sign_payload(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate a GitHub PR webhook")
    parser.add_argument("--url",    default="http://localhost:8000/api/github/webhook")
    parser.add_argument("--secret", default=None, help="Webhook secret (leave empty to skip HMAC)")
    parser.add_argument("--action", default="opened", choices=["opened", "synchronize"])
    parser.add_argument(
        "--sql",
        default="ALTER TABLE users RENAME COLUMN email TO contact_email;",
        help="SQL statement to include in the diff",
    )
    parser.add_argument(
        "--file",
        default="migrations/005_rename_email.sql",
        help="Filename for the SQL migration",
    )
    args = parser.parse_args()

    payload = build_payload(args.action, args.sql)
    body    = json.dumps(payload).encode()

    headers: dict[str, str] = {
        "Content-Type":  "application/json",
        "X-GitHub-Event": "pull_request",
        "X-GitHub-Delivery": f"simulate-{int(time.time())}",
        "User-Agent": "GitHub-Hookshot/simulate",
    }

    if args.secret:
        sig = "sha256=" + hmac.new(args.secret.encode(), body, hashlib.sha256).hexdigest()
        headers["X-Hub-Signature-256"] = sig
        print(f"[simulate] Signed with secret: {args.secret[:4]}****")
    else:
        print("[simulate] No secret — skipping signature")

    print(f"[simulate] POST {args.url}")
    print(f"[simulate] Event: pull_request.{args.action}")
    print(f"[simulate] SQL:   {args.sql}")
    print()

    try:
        resp = httpx.post(args.url, content=body, headers=headers, timeout=15.0)
    except httpx.ConnectError:
        print(f"[simulate] ERROR — cannot connect to {args.url}")
        print("           Is the backend running?  cd backend && uvicorn app.main:app --reload")
        sys.exit(1)

    print(f"[simulate] Response: HTTP {resp.status_code}")
    try:
        print(json.dumps(resp.json(), indent=2))
    except Exception:
        print(resp.text)

    if resp.status_code == 200:
        data = resp.json()
        if data.get("status") == "accepted":
            print()
            print("[simulate] ✓ Webhook accepted. Background pipeline started.")
            print("           Check backend logs for analysis + comment output.")
            print()
            print("NOTE: Because the pipeline runs in a background task, the bot")
            print("needs GitHub App credentials to actually post a PR comment.")
            print("For a fully offline test, see tests/test_github_webhook.py.")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
