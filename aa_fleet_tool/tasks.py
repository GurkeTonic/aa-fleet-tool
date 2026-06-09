"""App Tasks"""

# Standard Library
from email.utils import parsedate_to_datetime

# Third Party
import requests
from celery import shared_task

# Django
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

# Alliance Auth
from allianceauth.services.hooks import get_extension_logger

# AA Fleet Tool
from aa_fleet_tool import (
    __app_name_useragent__,
    __esi_compatibility_date__,
    __github_url__,
    __version__,
)

logger = get_extension_logger(__name__)

ESI_BASE = "https://esi.evetech.net"
_ESI_COMPAT_DATE = __esi_compatibility_date__

READ_SCOPE = "esi-fleets.read_fleet.v1"


def _get_user_agent() -> str:
    email = getattr(settings, "ESI_USER_CONTACT_EMAIL", "unknown@example.com")
    return f"{__app_name_useragent__}/{__version__} ({email}; +{__github_url__})"


def _base_headers() -> dict:
    return {
        "User-Agent": _get_user_agent(),
        "X-Compatibility-Date": _ESI_COMPAT_DATE,
        "Accept": "application/json",
    }


def _auth_headers(access_token: str) -> dict:
    return {**_base_headers(), "Authorization": f"Bearer {access_token}"}


def _handle_esi_response(resp: requests.Response) -> None:
    """Check ESI error-limit headers and raise on exhaustion or HTTP errors."""
    remain = int(resp.headers.get("X-ESI-Error-Limit-Remain", 100))
    if remain <= 0:
        reset = resp.headers.get("X-ESI-Error-Limit-Reset", "?")
        logger.error("ESI error limit exhausted, resets in %ss — aborting task", reset)
        resp.raise_for_status()
    if remain < 10:
        logger.warning(
            "ESI error limit critical: %d remaining, resets in %ss",
            remain,
            resp.headers.get("X-ESI-Error-Limit-Reset", "?"),
        )
    if resp.status_code == 429:
        logger.warning(
            "ESI rate limited (429), retry after %ss",
            resp.headers.get("Retry-After", "?"),
        )
    resp.raise_for_status()


def _cache_ttl_from_expires(headers: dict) -> int:
    expires = headers.get("Expires")
    if expires:
        try:
            exp_dt = parsedate_to_datetime(expires)
            ttl = int(exp_dt.timestamp() - timezone.now().timestamp())
            return max(30, ttl)
        except Exception:
            pass
    return 60


def _get_token(character_id: int, scope: str):
    from esi.models import Token

    return (
        Token.objects.filter(character_id=character_id)
        .require_valid()
        .filter(scopes__name=scope)
        .first()
    )


def _esi_get(url: str, access_token: str, cache_key: str = "", timeout: int = 30):
    """Authenticated ESI GET with caching and error-limit handling."""
    if cache_key:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    try:
        resp = requests.get(url, headers=_auth_headers(access_token), timeout=timeout)
    except requests.RequestException as exc:
        logger.warning("ESI GET %s failed: %s", url, exc)
        return None

    try:
        _handle_esi_response(resp)
    except requests.HTTPError:
        return None

    if resp.status_code == 200 and cache_key:
        ttl = _cache_ttl_from_expires(resp.headers)
        cache.set(cache_key, resp, ttl)

    return resp


def _resolve_names_bulk(ids: list[int]) -> dict[int, str]:
    if not ids:
        return {}

    unknown = []
    result = {}
    for uid in ids:
        cached = cache.get(f"fleet_tool_name_{uid}")
        if cached:
            result[uid] = cached
        else:
            unknown.append(uid)

    if not unknown:
        return result

    chunks = [unknown[i:i + 1000] for i in range(0, len(unknown), 1000)]
    for chunk in chunks:
        try:
            resp = requests.post(
                f"{ESI_BASE}/v3/universe/names/",
                json=chunk,
                headers=_base_headers(),
                timeout=30,
            )
            if resp.status_code != 200:
                logger.warning("Name resolution returned %s", resp.status_code)
                continue
            for item in resp.json():
                name = item["name"]
                uid = item["id"]
                result[uid] = name
                cache.set(f"fleet_tool_name_{uid}", name, 3600)
        except requests.RequestException as exc:
            logger.warning("Name resolution failed: %s", exc)

    return result


@shared_task
def check_all_fc_status():
    """Runs every 60s — checks if each FC is in a fleet; updates or clears ActiveFleet."""
    from .models import FleetCommander

    for fc in FleetCommander.objects.select_related("character"):
        _check_fc_in_fleet.delay(fc.pk)


@shared_task
def update_all_active_fleets():
    """Runs every 30s — updates members/wings for all known active fleets."""
    from .models import ActiveFleet

    for af in ActiveFleet.objects.select_related("fc__character"):
        _update_fleet_members.delay(af.fc.pk)


@shared_task
def _check_fc_in_fleet(fc_pk: int):
    from .models import ActiveFleet, FleetCommander

    try:
        fc = FleetCommander.objects.select_related("character").get(pk=fc_pk)
    except FleetCommander.DoesNotExist:
        return

    char_id = fc.character.character_id
    token = _get_token(char_id, READ_SCOPE)
    if not token:
        logger.debug("No valid token for FC %s", fc)
        return

    access_token = token.valid_access_token()
    cache_key = f"fleet_tool_fc_status_{char_id}"
    resp = _esi_get(
        f"{ESI_BASE}/v1/characters/{char_id}/fleet",
        access_token,
        cache_key=cache_key,
    )
    if resp is None:
        return

    if resp.status_code == 404:
        cache.delete(cache_key)
        ActiveFleet.objects.filter(fc=fc).delete()
        return

    if resp.status_code != 200:
        logger.warning("Fleet status check failed for %s: %s", fc, resp.status_code)
        return

    data = resp.json()
    fleet_id = data["fleet_id"]

    fleet_resp = _esi_get(
        f"{ESI_BASE}/v1/fleets/{fleet_id}",
        access_token,
        cache_key=f"fleet_tool_fleet_{fleet_id}",
    )
    if fleet_resp is None or fleet_resp.status_code != 200:
        return

    fleet_data = fleet_resp.json()
    ActiveFleet.objects.update_or_create(
        fc=fc,
        defaults={
            "fleet_id": fleet_id,
            "motd": fleet_data.get("motd", ""),
            "is_free_move": fleet_data.get("is_free_move", False),
            "is_registered": fleet_data.get("is_registered", False),
            "is_voice_enabled": fleet_data.get("is_voice_enabled", False),
            "last_updated": timezone.now(),
        },
    )

    _update_fleet_members.delay(fc_pk)


@shared_task
def _update_fleet_members(fc_pk: int):
    from .models import ActiveFleet, FleetCommander, FleetMember, FleetSquad, FleetWing

    try:
        fc = FleetCommander.objects.select_related("character").get(pk=fc_pk)
        fleet = fc.active_fleet
    except (FleetCommander.DoesNotExist, ActiveFleet.DoesNotExist):
        return

    char_id = fc.character.character_id
    token = _get_token(char_id, READ_SCOPE)
    if not token:
        return

    access_token = token.valid_access_token()
    fleet_id = fleet.fleet_id

    # Members
    resp = _esi_get(
        f"{ESI_BASE}/v1/fleets/{fleet_id}/members",
        access_token,
        cache_key=f"fleet_tool_members_{char_id}_{fleet_id}",
    )
    if resp is not None and resp.status_code == 200:
        members_raw = resp.json()

        all_ids = set()
        for m in members_raw:
            all_ids.add(m["character_id"])
            all_ids.add(m["ship_type_id"])
            all_ids.add(m["solar_system_id"])

        names = _resolve_names_bulk(list(all_ids))

        fleet.members.all().delete()
        new_members = [
            FleetMember(
                fleet=fleet,
                character_id=m["character_id"],
                character_name=names.get(m["character_id"], f"Unknown #{m['character_id']}"),
                ship_type_id=m["ship_type_id"],
                ship_name=names.get(m["ship_type_id"], f"Unknown Ship #{m['ship_type_id']}"),
                solar_system_id=m["solar_system_id"],
                system_name=names.get(m["solar_system_id"], f"Unknown System #{m['solar_system_id']}"),
                role=m["role"],
                role_name=m.get("role_name", ""),
                wing_id=m.get("wing_id"),
                squad_id=m.get("squad_id"),
                join_time=m.get("join_time"),
                takes_fleet_warp=m.get("takes_fleet_warp", True),
                station_id=m.get("station_id"),
            )
            for m in members_raw
        ]
        FleetMember.objects.bulk_create(new_members, ignore_conflicts=True)

    # Wings + Squads
    resp_w = _esi_get(
        f"{ESI_BASE}/v1/fleets/{fleet_id}/wings",
        access_token,
        cache_key=f"fleet_tool_wings_{char_id}_{fleet_id}",
    )
    if resp_w is not None and resp_w.status_code == 200:
        wings_raw = resp_w.json()
        fleet.wings.all().delete()
        for w in wings_raw:
            wing = FleetWing.objects.create(
                fleet=fleet,
                wing_id=w["id"],
                name=w.get("name", ""),
            )
            for s in w.get("squads", []):
                FleetSquad.objects.create(
                    wing=wing,
                    squad_id=s["id"],
                    name=s.get("name", ""),
                )

    fleet.last_updated = timezone.now()
    fleet.save(update_fields=["last_updated"])


@shared_task
def sync_fc(fc_pk: int):
    """Manual trigger: full refresh for one FC."""
    _check_fc_in_fleet(fc_pk)
