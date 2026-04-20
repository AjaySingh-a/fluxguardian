"""
handlers.py — Slack event/command handlers.

Imported by app.py and registered on the Bolt App instance.
"""

from __future__ import annotations

import logging

from slack_bolt import App

from claude_client import ask_with_tools

log = logging.getLogger(__name__)


def register_handlers(app: App) -> None:
    """Register all Slack handlers on the given Bolt App."""
    app.command("/fluxguardian")(handle_slash_command)
    app.event("message")(handle_dm)
    app.event("app_mention")(handle_mention)


# ---------------------------------------------------------------------------
# /fluxguardian <question>
# ---------------------------------------------------------------------------

def handle_slash_command(ack, respond, command, logger) -> None:
    """
    Handle the /fluxguardian slash command.

    Flow:
      1. ack() immediately (Slack requires < 3 s)
      2. Post "Thinking..." via respond()
      3. Call Claude (blocking — Bolt runs this in a thread)
      4. Post the final answer via respond()
    """
    ack()

    question = (command.get("text") or "").strip()
    if not question:
        respond(
            "👋 *FluxGuardian* here! Ask me anything about your data assets.\n"
            "Example: `/fluxguardian what breaks if I drop users.email?`"
        )
        return

    user = command.get("user_name", "there")
    logger.info("/fluxguardian from @%s: %s", user, question)

    # Post immediate feedback so the user sees activity
    respond(f"🤔 Thinking about: _{question}_")

    try:
        answer = ask_with_tools(question)
    except Exception as exc:
        logger.exception("Claude call failed for question: %s", question)
        respond(f"⚠️ Something went wrong: `{exc}`")
        return

    respond(answer)


# ---------------------------------------------------------------------------
# DM messages
# ---------------------------------------------------------------------------

def handle_dm(event, say, logger) -> None:
    """
    Handle direct messages to the bot.
    Only responds to human messages in IM channels (not bot echoes).
    """
    # Ignore bot messages and message_changed/deleted subtypes
    if event.get("bot_id") or event.get("subtype"):
        return
    if event.get("channel_type") not in ("im", "mpim"):
        return

    question = (event.get("text") or "").strip()
    if not question:
        return

    logger.info("DM received: %s", question)
    say("🤔 On it...")

    try:
        answer = ask_with_tools(question)
    except Exception as exc:
        logger.exception("Claude call failed for DM: %s", question)
        say(f"⚠️ Something went wrong: `{exc}`")
        return

    say(answer)


# ---------------------------------------------------------------------------
# @FluxGuardian mentions in channels
# ---------------------------------------------------------------------------

def handle_mention(event, say, logger) -> None:
    """Handle @FluxGuardian mentions in channels."""
    if event.get("bot_id"):
        return

    # Strip the bot mention token from the text
    raw_text = event.get("text", "")
    # Remove <@BOTID> tokens
    import re
    question = re.sub(r"<@[A-Z0-9]+>", "", raw_text).strip()

    if not question:
        say("👋 Mention me with a question, e.g. `@FluxGuardian who owns the CFO dashboard?`")
        return

    logger.info("Mention: %s", question)
    say("🤔 Looking that up...")

    try:
        answer = ask_with_tools(question)
    except Exception as exc:
        logger.exception("Claude call failed for mention: %s", question)
        say(f"⚠️ Something went wrong: `{exc}`")
        return

    say(answer)
