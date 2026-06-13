"""App Configuration"""

# Django
from django.apps import AppConfig

# AA Fleet Tool
from aa_fleet_tool import __version__


class AaFleetToolConfig(AppConfig):
    """App Config"""

    default_auto_field = "django.db.models.AutoField"
    name = "aa_fleet_tool"
    label = "aa_fleet_tool"
    verbose_name = f"Fleet Tool v{__version__}"

    def ready(self):
        from datetime import timedelta

        from celery import current_app

        from .app_settings import (
            FLEET_TOOL_FC_CHECK_INTERVAL,
            FLEET_TOOL_MEMBER_SYNC_INTERVAL,
        )

        current_app.conf.beat_schedule.update(
            {
                "aa_fleet_tool_check_fc_status": {
                    "task": "aa_fleet_tool.tasks.check_all_fc_status",
                    "schedule": timedelta(seconds=FLEET_TOOL_FC_CHECK_INTERVAL),
                    "options": {"expires": max(5, FLEET_TOOL_FC_CHECK_INTERVAL - 5)},
                },
                "aa_fleet_tool_update_active_fleets": {
                    "task": "aa_fleet_tool.tasks.update_all_active_fleets",
                    "schedule": timedelta(seconds=FLEET_TOOL_MEMBER_SYNC_INTERVAL),
                    "options": {"expires": max(2, FLEET_TOOL_MEMBER_SYNC_INTERVAL - 1)},
                },
            }
        )
