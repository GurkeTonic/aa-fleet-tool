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

        current_app.conf.beat_schedule.update(
            {
                "aa_fleet_tool_check_fc_status": {
                    "task": "aa_fleet_tool.tasks.check_all_fc_status",
                    "schedule": timedelta(seconds=60),
                    "options": {"expires": 55},
                },
                "aa_fleet_tool_update_active_fleets": {
                    "task": "aa_fleet_tool.tasks.update_all_active_fleets",
                    "schedule": timedelta(seconds=30),
                    "options": {"expires": 25},
                },
            }
        )
