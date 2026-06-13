"""Hook into Alliance Auth"""

# Alliance Auth
from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook, UrlHook

# AA Fleet Tool
from aa_fleet_tool import app_settings, urls


class FleetToolMenuItem(MenuItemHook):
    """This class ensures only authorized users will see the menu entry"""

    def __init__(self):
        super().__init__(
            f"{app_settings.FLEET_TOOL_APP_NAME}",
            "fas fa-fighter-jet fa-fw",
            "aa_fleet_tool:index",
            # Community apps must use an order above 1000 (below is reserved for AA)
            order=9999,
            navactive=["aa_fleet_tool:"],
        )

    def render(self, request):
        if request.user.has_perm("aa_fleet_tool.view_fleet_tool"):
            return MenuItemHook.render(self, request)
        return ""


@hooks.register("menu_item_hook")
def register_menu():
    """Register the menu item"""

    return FleetToolMenuItem()


@hooks.register("url_hook")
def register_urls():
    """Register app urls"""

    return UrlHook(urls, "aa_fleet_tool", r"^fleet-tool/")
