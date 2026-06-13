"""
App Settings
"""

# Django
from django.conf import settings

# Menu name displayed in the Alliance Auth navigation
FLEET_TOOL_APP_NAME = getattr(settings, "FLEET_TOOL_APP_NAME", "Fleet Tool")

# Global timeout for Celery tasks in seconds to reduce accumulation during outages
FLEET_TOOL_TASKS_TIME_LIMIT = getattr(settings, "FLEET_TOOL_TASKS_TIME_LIMIT", 300)

# Interval in seconds for the fleet member sync task. ESI caches the member
# list for 5 s, and the rate limit is per FC token, so 5 s gives near-live data
# without exhausting a single FC's budget.
FLEET_TOOL_MEMBER_SYNC_INTERVAL = getattr(
    settings, "FLEET_TOOL_MEMBER_SYNC_INTERVAL", 5
)

# Interval in seconds for the FC status check task
FLEET_TOOL_FC_CHECK_INTERVAL = getattr(settings, "FLEET_TOOL_FC_CHECK_INTERVAL", 60)

# Grace period (seconds) after "Fleet Start" before an FC that never formed a
# fleet is automatically deactivated again. Prevents stale active FCs from
# polling forever when someone clicks Start but never opens a fleet in game.
FLEET_TOOL_ACTIVATION_GRACE = getattr(settings, "FLEET_TOOL_ACTIVATION_GRACE", 600)

# Rolling window (seconds) of composition snapshots kept per fleet for the live
# graph. Older snapshots are pruned on each write. Default 5 minutes.
FLEET_TOOL_SNAPSHOT_WINDOW = getattr(settings, "FLEET_TOOL_SNAPSHOT_WINDOW", 300)
