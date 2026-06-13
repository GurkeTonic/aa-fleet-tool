"""Doctrine-independent fleet composition (DPS / Logi / Booster / EWAR / Other).

Ships are classified by their static EVE ship group from the local SDE, so the
composition works even without a doctrine selected and stays consistent over the
fleet's lifetime (used both live and for the snapshot graph). No ESI calls.
"""

from allianceauth.services.hooks import get_extension_logger

from .constants import COMP_ROLES, SHIP_GROUP_ROLE

logger = get_extension_logger(__name__)


def ship_roles(ship_type_ids) -> dict[int, str]:
    """Map ship type ids to a composition role via their SDE group (default 'dps')."""
    ids = {int(i) for i in ship_type_ids if i}
    if not ids:
        return {}
    try:
        from eve_sde.models import ItemType

        groups = dict(ItemType.objects.filter(id__in=ids).values_list("id", "group_id"))
    except Exception as exc:  # SDE missing/not loaded → everything falls back to 'dps'
        logger.warning("Composition SDE lookup failed: %s", exc)
        groups = {}
    return {tid: SHIP_GROUP_ROLE.get(groups.get(tid), "dps") for tid in ids}


# Doctrine role_hint values that map onto a composition bucket. Other hints
# ("any", "fc", "hauler", "scout") are left to the SDE group classification.
_ROLE_HINT_BUCKET = {"dps": "dps", "logi": "logi", "booster": "booster", "ewar": "ewar"}


def doctrine_overrides(ship_role_map) -> dict[int, str]:
    """Turn a doctrine's {ship_type_id: role_hint} into composition overrides.

    Only the four explicit buckets override the SDE classification; ambiguous
    hints fall back to the ship group.
    """
    return {
        int(tid): _ROLE_HINT_BUCKET[hint]
        for tid, hint in (ship_role_map or {}).items()
        if hint in _ROLE_HINT_BUCKET
    }


def composition_counts(ship_type_ids: list, doctrine_roles: dict | None = None) -> dict:
    """Return {role: {'count': n, 'pct': p}} for the 5 buckets over the given ships.

    Two modes:
    - ``doctrine_roles is None`` → classify by the SDE ship group; unknown → dps.
    - ``doctrine_roles`` given (a {ship_type_id: role} map from the selected
      doctrine) → classify **only** by the doctrine; the SDE is ignored entirely
      and anything not in the doctrine (or without a tracked role) falls into
      "other" — so off-doctrine ships don't inflate the DPS/Logi numbers.
    """
    if doctrine_roles is not None:
        roles = doctrine_roles
        default = "other"
    else:
        roles = ship_roles(set(ship_type_ids))
        default = "dps"

    counts = {role: 0 for role in COMP_ROLES}
    for tid in ship_type_ids:
        role = roles.get(int(tid), default)
        counts[role if role in counts else default] += 1
    total = len(ship_type_ids)
    return {
        role: {"count": c, "pct": round(c * 100 / total) if total else 0}
        for role, c in counts.items()
    }


def in_system_ship_ids(members) -> list:
    """Ship type ids of members undocked in the fleet boss's solar system.

    ``members`` is an iterable of FleetMember instances. The boss is the
    ``fleet_commander`` member; only members in his system and not docked
    (``station_id`` unset) count. Returns ``[]`` when there is no boss or his
    system is unknown.
    """
    members = list(members)
    boss_system = next(
        (
            m.solar_system_id
            for m in members
            if m.role == "fleet_commander" and m.solar_system_id
        ),
        None,
    )
    if not boss_system:
        return []
    return [
        m.ship_type_id
        for m in members
        if m.solar_system_id == boss_system and not m.station_id
    ]
