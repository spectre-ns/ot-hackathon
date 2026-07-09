"""Post kudos announcements to Slack via an Incoming Webhook.

This is an OUTBOUND-only integration: when someone gives kudos, we fire a
single message to a pre-configured Slack channel. It intentionally does the
simplest thing that works — an Incoming Webhook (one URL, one channel, no
OAuth scopes) — rather than a full bot. See ``config.SLACK_WEBHOOK_URL``.

Design rules:
  * If Slack isn't configured, every function is a silent no-op. The app must
    run identically in "demo mode" with no webhook set.
  * Posting must NEVER break the request that triggered it. Network errors,
    timeouts, and non-2xx responses are swallowed and reported in the return
    value instead of raised. Giving kudos succeeds even if Slack is down.
"""
from __future__ import annotations

import logging

import httpx

from . import config
from .values import value_or_default

log = logging.getLogger("kudos.slack")


def _post(text: str, blocks: list | None = None) -> bool:
    """POST a message to the configured Incoming Webhook.

    Returns True on success, False if disabled or the request failed. Never
    raises — Slack being unreachable must not fail the caller.
    """
    if not config.slack_enabled():
        return False
    payload: dict = {"text": text}
    if blocks:
        payload["blocks"] = blocks
    try:
        resp = httpx.post(config.SLACK_WEBHOOK_URL, json=payload, timeout=5.0)
    except httpx.HTTPError as e:
        log.warning("Slack post failed: %s", e)
        return False
    if resp.status_code != 200:
        # Incoming Webhooks return 200 + "ok" on success; anything else is an
        # error (e.g. "invalid_payload", "no_service" for a revoked hook).
        log.warning("Slack post rejected (%s): %s", resp.status_code, resp.text[:200])
        return False
    return True


def notify_kudos(giver: dict, receiver: dict, points: int, value_key: str,
                 message: str) -> bool:
    """Announce a kudos to Slack. No-op (returns False) when Slack is disabled."""
    if not config.slack_enabled():
        return False

    value = value_or_default(value_key)
    emoji = value.get("emoji", "🎉")
    label = value.get("label", "Kudos")

    summary = (f"{emoji} {giver['name']} gave {receiver['name']} "
               f"{points} pts for {label}")

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (f"{emoji} *{giver['name']}* gave *{receiver['name']}* "
                         f"*{points} pts* for *{label}*"),
            },
        },
    ]
    if message:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"> {message}"},
        })

    return _post(summary, blocks)
