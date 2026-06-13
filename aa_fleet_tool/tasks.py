"""App Tasks"""

# Third Party
from celery import shared_task

# Django
from django.core.cache import cache
from django.utils import timezone

# Alliance Auth
from allianceauth.services.hooks import get_extension_logger
from allianceauth.services.tasks import QueueOnce

# Alliance Auth (External Libs)
from esi.exceptions import (
    ESIBucketLimitException,
    ESIErrorLimitException,
    HTTPClientError,
    HTTPNotModified,
    HTTPServerError,
)

# AA Fleet Tool
from aa_fleet_tool.app_settings import FLEET_TOOL_ACTIVATION_GRACE
from aa_fleet_tool.constants import READ_SCOPE
from aa_fleet_tool.providers import esi, get_token

logger = get_extension_logger(__name__)

# Exceptions worth a retry — the error/bucket limits and transient ESI 5xx.
ESI_RETRY_EXCEPTIONS = (
    ESIErrorLimitException,
    ESIBucketLimitException,
    HTTPServerError,
)

NAME_CACHE_TTL = 3600


def _auto_stop(fc, had_fleet: bool) -> None:
    """Deactivate an FC that is no longer fleeting.

    ``had_fleet`` True means a fleet was just running and ended → stop now.
    Otherwise only stop once the activation grace period has elapsed (the FC
    clicked "Fleet Start" but never actually opened a fleet in game).
    """
    if had_fleet:
        fc.stop()
    elif (
        fc.activated_at
        and (timezone.now() - fc.activated_at).total_seconds()
        > FLEET_TOOL_ACTIVATION_GRACE
    ):
        fc.stop()


def _resolve_sde_names(model_name: str, ids: set[int]) -> dict[int, str]:
    """Resolve static IDs (ship types, solar systems) to names from the local SDE.

    Static data never changes, so this avoids hitting ESI /universe/names for it
    entirely — only dynamic entities (characters) still need an ESI call.
    """
    if not ids:
        return {}
    try:
        from eve_sde import models as sde

        model = getattr(sde, model_name)
        return dict(model.objects.filter(id__in=ids).values_list("id", "name"))
    except (
        Exception
    ) as exc:  # SDE not installed/loaded → caller falls back to placeholders
        logger.warning("SDE name lookup (%s) failed: %s", model_name, exc)
        return {}


def _resolve_character_names(ids: list[int]) -> dict[int, str]:
    """Resolve character ids to names via ESI /universe/names, cached per id."""
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

    chunks = [unknown[i : i + 1000] for i in range(0, len(unknown), 1000)]
    for chunk in chunks:
        try:
            names = esi.client.Universe.PostUniverseNames(body=chunk).result()
        except (HTTPClientError, HTTPServerError) as exc:
            logger.warning("Character name resolution failed: %s", exc)
            continue
        for item in names:
            result[item.id] = item.name
            cache.set(f"fleet_tool_name_{item.id}", item.name, NAME_CACHE_TTL)

    return result


@shared_task(base=QueueOnce, once={"graceful": True})
def check_all_fc_status():
    """Runs every 60s — checks active FCs for a fleet; updates or clears ActiveFleet.

    Only FCs that pressed "Fleet Start" (``is_active``) are polled, so registering
    an FC does not cause permanent ESI polling.
    """
    from .models import FleetCommander

    for fc_pk in FleetCommander.objects.filter(is_active=True).values_list(
        "pk", flat=True
    ):
        check_fc_in_fleet.delay(fc_pk)


@shared_task(base=QueueOnce, once={"graceful": True})
def update_all_active_fleets():
    """Periodic fan-out — updates members/wings for all known active fleets."""
    from .models import ActiveFleet

    for fc_pk in ActiveFleet.objects.filter(fc__is_active=True).values_list(
        "fc_id", flat=True
    ):
        update_fleet_members.delay(fc_pk)


@shared_task(
    base=QueueOnce,
    once={"graceful": True},
    autoretry_for=ESI_RETRY_EXCEPTIONS,
    retry_backoff=True,
    max_retries=3,
)
def check_fc_in_fleet(fc_pk: int, force: bool = False):
    """Check whether the FC is in a fleet and rebuild the ActiveFleet.

    ``force`` bypasses the ESI cache/ETag — needed when (re)activating, because
    a 304 Not-Modified would otherwise leave us unable to recreate an ActiveFleet
    that was deleted on Stop while the FC never actually left the in-game fleet.
    """
    from .models import ActiveFleet, FleetCommander

    try:
        fc = FleetCommander.objects.select_related("character").get(pk=fc_pk)
    except FleetCommander.DoesNotExist:
        return

    char_id = fc.character.character_id
    token = get_token(char_id, READ_SCOPE)
    if not token:
        logger.debug("No valid token for FC %s", fc)
        return

    try:
        fleet_info = esi.client.Fleets.GetCharactersCharacterIdFleet(
            character_id=char_id, token=token
        ).result(force_refresh=force)
    except HTTPNotModified:
        # Unchanged since last fetch. Normally just refresh members — but if the
        # ActiveFleet is gone (FC stopped, then restarted the *same* fleet), the
        # ETag keeps returning 304, so force a fresh fetch to rebuild it.
        if ActiveFleet.objects.filter(fc=fc).exists():
            update_fleet_members.delay(fc_pk)
        elif not force:
            check_fc_in_fleet(fc_pk, force=True)
        return
    except HTTPClientError as exc:
        if exc.status_code == 404:
            # Character is not in a fleet — drop any stale ActiveFleet and
            # deactivate the FC (fleet ended, or never formed within grace).
            had_fleet = ActiveFleet.objects.filter(fc=fc).exists()
            ActiveFleet.objects.filter(fc=fc).delete()
            _auto_stop(fc, had_fleet)
        else:
            logger.warning("Fleet status check failed for %s: %s", fc, exc)
        return

    fleet_id = fleet_info.fleet_id

    motd = ""
    is_free_move = is_registered = is_voice_enabled = False
    try:
        fleet_data = esi.client.Fleets.GetFleetsFleetId(
            fleet_id=fleet_id, token=token
        ).result(force_refresh=force)
        motd = fleet_data.motd or ""
        is_free_move = fleet_data.is_free_move
        is_registered = fleet_data.is_registered
        is_voice_enabled = fleet_data.is_voice_enabled
    except HTTPNotModified:
        # Fleet settings unchanged — keep whatever we already stored.
        existing = ActiveFleet.objects.filter(fc=fc).first()
        if existing:
            motd = existing.motd
            is_free_move = existing.is_free_move
            is_registered = existing.is_registered
            is_voice_enabled = existing.is_voice_enabled
    except HTTPClientError as exc:
        if exc.status_code == 404:
            ActiveFleet.objects.filter(fc=fc).delete()
            return
        logger.warning("Fleet detail fetch failed for %s: %s", fc, exc)
        return

    ActiveFleet.objects.update_or_create(
        fc=fc,
        defaults={
            "fleet_id": fleet_id,
            "motd": motd,
            "is_free_move": is_free_move,
            "is_registered": is_registered,
            "is_voice_enabled": is_voice_enabled,
            "last_updated": timezone.now(),
        },
    )

    update_fleet_members.delay(fc_pk, force=force)


@shared_task(
    base=QueueOnce,
    once={"graceful": True},
    autoretry_for=ESI_RETRY_EXCEPTIONS,
    retry_backoff=True,
    max_retries=3,
)
def update_fleet_members(fc_pk: int, force: bool = False):
    """Rebuild the member/wing rows from ESI.

    ``force`` bypasses the ESI cache/ETag — required after a stop/start of the
    same fleet, where a 304 Not-Modified would otherwise leave the (cascade-
    deleted) member list empty.
    """
    from .models import ActiveFleet, FleetCommander, FleetMember, FleetSquad, FleetWing

    try:
        fc = FleetCommander.objects.select_related("character").get(pk=fc_pk)
        fleet = fc.active_fleet
    except (FleetCommander.DoesNotExist, ActiveFleet.DoesNotExist):
        return

    char_id = fc.character.character_id
    token = get_token(char_id, READ_SCOPE)
    if not token:
        return

    fleet_id = fleet.fleet_id

    # Members
    try:
        members_raw = esi.client.Fleets.GetFleetsFleetIdMembers(
            fleet_id=fleet_id, token=token
        ).result(force_refresh=force)
    except HTTPNotModified:
        # Unchanged — normally keep the stored rows. But if we have none (the
        # fleet was just recreated after a stop/start), the ETag would keep
        # returning 304, so force a fresh fetch to repopulate.
        if not force and not fleet.members.exists():
            update_fleet_members(fc_pk, force=True)
            return
        members_raw = None
    except HTTPClientError as exc:
        if exc.status_code == 404:
            # Fleet vanished — remove it and deactivate the FC.
            fleet.delete()
            _auto_stop(fc, had_fleet=True)
        return

    if members_raw is not None:
        # Static IDs (ships, systems) come from the local SDE; only character
        # names — which the SDE does not hold — are resolved via ESI.
        char_names = _resolve_character_names(
            list({m.character_id for m in members_raw})
        )
        ship_names = _resolve_sde_names(
            "ItemType", {m.ship_type_id for m in members_raw}
        )
        system_names = _resolve_sde_names(
            "SolarSystem", {m.solar_system_id for m in members_raw}
        )

        fleet.members.all().delete()
        new_members = [
            FleetMember(
                fleet=fleet,
                character_id=m.character_id,
                character_name=char_names.get(
                    m.character_id, f"Unknown #{m.character_id}"
                ),
                ship_type_id=m.ship_type_id,
                ship_name=ship_names.get(
                    m.ship_type_id, f"Unknown Ship #{m.ship_type_id}"
                ),
                solar_system_id=m.solar_system_id,
                system_name=system_names.get(
                    m.solar_system_id, f"Unknown System #{m.solar_system_id}"
                ),
                role=m.role,
                role_name=getattr(m, "role_name", "") or "",
                wing_id=getattr(m, "wing_id", None),
                squad_id=getattr(m, "squad_id", None),
                join_time=getattr(m, "join_time", None),
                takes_fleet_warp=getattr(m, "takes_fleet_warp", True),
                station_id=getattr(m, "station_id", None),
            )
            for m in members_raw
        ]
        FleetMember.objects.bulk_create(new_members, ignore_conflicts=True)

    # Wings + Squads
    try:
        wings_raw = esi.client.Fleets.GetFleetsFleetIdWings(
            fleet_id=fleet_id, token=token
        ).result(force_refresh=force)
    except HTTPNotModified:
        wings_raw = None
    except HTTPClientError:
        wings_raw = None

    if wings_raw is not None:
        fleet.wings.all().delete()
        for w in wings_raw:
            wing = FleetWing.objects.create(
                fleet=fleet,
                wing_id=w.id,
                name=w.name or "",
            )
            for s in getattr(w, "squads", None) or []:
                FleetSquad.objects.create(
                    wing=wing,
                    squad_id=s.id,
                    name=s.name or "",
                )

    fleet.last_updated = timezone.now()
    fleet.save(update_fields=["last_updated"])

    _write_snapshot(fleet)


def _write_snapshot(fleet) -> None:
    """Capture the current composition for the live graph.

    One snapshot per member sync, plus a rolling window: snapshots older than
    ``FLEET_TOOL_SNAPSHOT_WINDOW`` (default 5 min) are pruned so the graph stays
    a short live window and the table doesn't grow unbounded.
    """
    from datetime import timedelta

    from .app_settings import (
        FLEET_TOOL_MEMBER_SYNC_INTERVAL,
        FLEET_TOOL_SNAPSHOT_WINDOW,
    )
    from .composition import composition_counts, in_system_ship_ids
    from .models import FleetSnapshot

    now = timezone.now()
    # Dedup snapshots that land closer than half a sync interval apart (e.g. when
    # the FC status check triggers an extra update right after a member sync).
    min_gap = max(2, FLEET_TOOL_MEMBER_SYNC_INTERVAL // 2)
    last = fleet.snapshots.order_by("-timestamp").first()
    if last and (now - last.timestamp).total_seconds() < min_gap:
        return

    members = list(fleet.members.all())
    ship_ids = [m.ship_type_id for m in members]
    comp = composition_counts(ship_ids)
    sys_ids = in_system_ship_ids(members)
    sys_comp = composition_counts(sys_ids)
    FleetSnapshot.objects.create(
        fleet=fleet,
        timestamp=now,
        total=len(ship_ids),
        dps=comp["dps"]["count"],
        logi=comp["logi"]["count"],
        booster=comp["booster"]["count"],
        ewar=comp["ewar"]["count"],
        other=comp["other"]["count"],
        in_system_total=len(sys_ids),
        in_system_dps=sys_comp["dps"]["count"],
        in_system_logi=sys_comp["logi"]["count"],
        in_system_booster=sys_comp["booster"]["count"],
        in_system_ewar=sys_comp["ewar"]["count"],
        in_system_other=sys_comp["other"]["count"],
    )

    cutoff = now - timedelta(seconds=FLEET_TOOL_SNAPSHOT_WINDOW)
    fleet.snapshots.filter(timestamp__lt=cutoff).delete()


@shared_task
def sync_fc(fc_pk: int):
    """Manual trigger: full (cache-bypassing) refresh for one FC."""
    check_fc_in_fleet(fc_pk, force=True)
