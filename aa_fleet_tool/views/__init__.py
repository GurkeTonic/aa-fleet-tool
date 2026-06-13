"""View package — pages and AJAX action endpoints, grouped by concern."""

from .commanders import (
    add_fc,
    commanders,
    remove_fc,
    start_fleet,
    stop_fleet,
    trigger_sync,
)
from .doctrines import (
    add_doctrine_ship,
    create_doctrine,
    delete_doctrine,
    doctrines,
    remove_doctrine_ship,
    ship_search,
)
from .fleets import (
    create_squad,
    create_wing,
    delete_squad,
    delete_wing,
    fleet_members_json,
    index,
    invite_member,
    kick_member,
    move_member,
    rename_squad,
    rename_wing,
    set_fleet_name,
    set_free_move,
    set_motd,
)
from .integrations import create_fat_link, create_srp_link
from .ping import send_fleet_ping
from .layouts import (
    add_layout_squad,
    add_layout_wing,
    apply_layout,
    create_layout,
    delete_layout,
    delete_layout_squad,
    delete_layout_wing,
    layouts,
    rename_layout_squad,
    rename_layout_wing,
)
from .motd import create_motd_template, delete_motd_template, motd, update_motd_template

__all__ = [
    "add_doctrine_ship", "add_fc", "add_layout_squad", "add_layout_wing",
    "apply_layout", "commanders", "create_doctrine", "create_fat_link",
    "create_layout", "create_motd_template", "create_squad", "create_srp_link",
    "create_wing", "delete_doctrine", "delete_layout", "delete_layout_squad",
    "delete_layout_wing", "delete_motd_template", "delete_squad", "delete_wing",
    "doctrines", "fleet_members_json", "index", "invite_member", "kick_member",
    "layouts", "motd", "move_member", "remove_doctrine_ship", "remove_fc",
    "rename_layout_squad", "rename_layout_wing", "rename_squad", "rename_wing",
    "send_fleet_ping", "set_fleet_name", "set_free_move", "set_motd", "ship_search",
    "start_fleet", "stop_fleet", "trigger_sync", "update_motd_template",
]
