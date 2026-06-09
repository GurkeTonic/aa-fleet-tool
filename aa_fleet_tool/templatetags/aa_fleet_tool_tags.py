"""Template tags for AA Fleet Tool"""

# Django
from django.template.defaulttags import register

# AA Fleet Tool
from aa_fleet_tool import __title__, __version__


@register.simple_tag
def fleet_tool_version() -> str:
    """Return the current Fleet Tool version."""
    return __version__
