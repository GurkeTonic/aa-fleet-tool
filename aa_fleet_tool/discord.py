"""Minimal Discord webhook posting for the Fleet Ping.

The AA Discord service client only manages users/roles, not channel messages, so
fleet pings are sent via a Discord webhook (configured per FleetType in admin).
"""

import time

import requests

from allianceauth.services.hooks import get_extension_logger

logger = get_extension_logger(__name__)

TIMEOUT = 10
# Discord rate-limits webhooks and answers 429 with a Retry-After. Retry a few
# times, honouring that delay, before giving up.
MAX_RETRIES = 3
MAX_RETRY_AFTER = 30  # cap so a hostile Retry-After can't block the worker forever


def post_webhook(
    webhook_url: str, content: str = "", embed: dict | None = None
) -> tuple[bool, str]:
    """Post a message (optional embed) to a Discord webhook.

    ``allowed_mentions`` is set so role/@here mentions in ``content`` actually
    trigger. Honours Discord's 429 ``Retry-After``. Returns ``(ok, error_message)``.
    Always called from a Celery task, so the short Retry-After sleep is fine.
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

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(webhook_url, json=payload, timeout=TIMEOUT)
        except requests.RequestException as exc:
            logger.warning("Fleet ping webhook POST failed: %s", exc)
            return False, "Could not reach Discord."

        if resp.status_code in (200, 204):
            return True, ""

        if resp.status_code == 429 and attempt < MAX_RETRIES - 1:
            retry_after = _retry_after_seconds(resp)
            logger.warning(
                "Fleet ping webhook rate limited (429), retrying in %.1fs", retry_after
            )
            time.sleep(retry_after)
            continue

        logger.warning(
            "Fleet ping webhook returned %s: %s", resp.status_code, resp.text[:200]
        )
        return False, f"Discord returned {resp.status_code}."

    return False, "Discord rate limited the webhook."


def _retry_after_seconds(resp) -> float:
    """Seconds to wait from a 429 response, capped at ``MAX_RETRY_AFTER``."""
    try:
        # Discord sends Retry-After both as a header and in the JSON body.
        retry_after = float(resp.headers.get("Retry-After", 1))
    except (TypeError, ValueError):
        retry_after = 1.0
    return min(max(retry_after, 0.5), MAX_RETRY_AFTER)
