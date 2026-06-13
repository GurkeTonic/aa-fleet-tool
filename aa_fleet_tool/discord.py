"""Minimal Discord webhook posting for the Fleet Ping.

The AA Discord service client only manages users/roles, not channel messages, so
fleet pings are sent via a Discord webhook (configured per FleetType in admin).
"""

import requests

from allianceauth.services.hooks import get_extension_logger

logger = get_extension_logger(__name__)

TIMEOUT = 10


def post_webhook(
    webhook_url: str, content: str = "", embed: dict | None = None
) -> tuple[bool, str]:
    """Post a message (optional embed) to a Discord webhook.

    ``allowed_mentions`` is set so role/@here mentions in ``content`` actually
    trigger. Returns ``(ok, error_message)``.
    """
    if not webhook_url:
        return False, "No webhook configured for this fleet type."

    payload = {
        "content": content or "",
        # Let @here / @everyone mentions in the content ping for real.
        "allowed_mentions": {"parse": ["everyone"]},
    }
    if embed:
        payload["embeds"] = [embed]

    try:
        resp = requests.post(webhook_url, json=payload, timeout=TIMEOUT)
    except requests.RequestException as exc:
        logger.warning("Fleet ping webhook POST failed: %s", exc)
        return False, "Could not reach Discord."

    if resp.status_code in (200, 204):
        return True, ""
    logger.warning(
        "Fleet ping webhook returned %s: %s", resp.status_code, resp.text[:200]
    )
    return False, f"Discord returned {resp.status_code}."
