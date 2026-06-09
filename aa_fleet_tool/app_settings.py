"""
App Settings
"""

# Django
from django.conf import settings

# Menu name displayed in the Alliance Auth navigation
FLEET_TOOL_APP_NAME = getattr(settings, "FLEET_TOOL_APP_NAME", "Fleet Tool")

# Global timeout for Celery tasks in seconds to reduce accumulation during outages
FLEET_TOOL_TASKS_TIME_LIMIT = getattr(settings, "FLEET_TOOL_TASKS_TIME_LIMIT", 300)

# Interval in seconds for the fleet member sync task
FLEET_TOOL_MEMBER_SYNC_INTERVAL = getattr(
    settings, "FLEET_TOOL_MEMBER_SYNC_INTERVAL", 30
)

# Interval in seconds for the FC status check task
FLEET_TOOL_FC_CHECK_INTERVAL = getattr(settings, "FLEET_TOOL_FC_CHECK_INTERVAL", 60)
