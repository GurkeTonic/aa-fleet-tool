"""Active Fleets page (fleet list + live detail) and all live-fleet ESI actions."""

from django.apps import apps
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from allianceauth.services.hooks import get_extension_logger

from ..models import (
    ActiveFleet,
    Doctrine,
    FleetLayout,
    FleetSquad,
    FleetToolConfiguration,
    FleetType,
    MOTDTemplate,
    Staging,
)
from ..composition import composition_counts, doctrine_overrides
from ..providers import esi
from .common import esi_call, fleet_write, nav_context, resolve_doctrine

logger = get_extension_logger(__name__)


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
def index(request):
    """Active Fleets — fleet list, live member detail and composition."""
    active_fleets = (
        ActiveFleet.objects.select_related("fc__character", "fc__user")
        .prefetch_related("members", "wings__squads")
        .all()
    )

    selected_fleet = None
    selected_fleet_members = []
    wings_data = []
    on_doctrine_chars = set()
    on_doctrine_count = 0
    comp = {"dps": {"count": 0, "pct": 0}, "logi": {"count": 0, "pct": 0},
            "booster": {"count": 0, "pct": 0}, "ewar": {"count": 0, "pct": 0},
            "other": {"count": 0, "pct": 0}}
    snapshot_data = []

    fleet_pk = request.GET.get("fleet")
    doctrine_pk = request.GET.get("doctrine")
    selected_fleet_type = request.GET.get("fleet_type", "")

    if fleet_pk:
        try:
            selected_fleet = active_fleets.get(pk=fleet_pk)
            selected_fleet_members = list(
                selected_fleet.members.order_by("role", "wing_id", "squad_id", "character_name")
            )

            # A selected doctrine drives the compliance overlay AND fully replaces
            # the composition classification (off-doctrine ships → "other").
            doctrine_roles = None
            if doctrine_pk:
                doctrine_ship_ids, ship_role_map = resolve_doctrine(doctrine_pk)
                if doctrine_ship_ids is not None:
                    on_doctrine_chars = {
                        m.character_id
                        for m in selected_fleet_members
                        if m.ship_type_id in doctrine_ship_ids
                    }
                    on_doctrine_count = len(on_doctrine_chars)
                    doctrine_roles = doctrine_overrides(ship_role_map)

            # Composition: SDE ship group by default; a doctrine fully overrides.
            comp = composition_counts(
                [m.ship_type_id for m in selected_fleet_members], doctrine_roles
            )
            snapshot_data = list(
                selected_fleet.snapshots.values("timestamp", "dps", "logi", "total")
            )

            for wing in selected_fleet.wings.prefetch_related("squads"):
                wing_members = [m for m in selected_fleet_members if m.wing_id == wing.wing_id]
                squads = []
                for squad in wing.squads.all():
                    squad_members = [m for m in wing_members if m.squad_id == squad.squad_id]
                    squads.append({"squad": squad, "members": squad_members})
                wings_data.append({"wing": wing, "squads": squads, "members": wing_members})

        except ActiveFleet.DoesNotExist:
            pass

    role_counts = {"fleet_commander": 0, "wing_commander": 0, "squad_commander": 0, "squad_member": 0}
    for m in selected_fleet_members:
        if m.role in role_counts:
            role_counts[m.role] += 1

    doctrines = Doctrine.objects.prefetch_related("ships")
    layouts = FleetLayout.objects.prefetch_related("wings__squads")
    # Public templates plus the user's own private ones.
    motd_templates = MOTDTemplate.objects.filter(
        Q(is_public=True) | Q(created_by=request.user)
    )
    motd_tpl_data = list(motd_templates.values("pk", "name", "text"))

    config = FleetToolConfiguration.get_config()

    # Fittings doctrines (optional integration)
    fittings_doctrines = []
    if config.use_fittings_doctrines and apps.is_installed("fittings"):
        try:
            from fittings.models import Doctrine as FittingsDoctrine
            fittings_doctrines = list(
                FittingsDoctrine.objects
                .prefetch_related("fittings__ship_type")
                .filter()
                .order_by("name")
            )
        except Exception as exc:
            logger.warning("Fittings doctrine lookup failed: %s", exc)

    # Our own central fleet types (drive the selector, FAT/SRP and the Fleet Ping)
    # and stagings the FC can attach to a ping.
    fleet_types = FleetType.objects.filter(is_enabled=True)
    stagings = Staging.objects.filter(is_enabled=True)

    # afat doctrines + default FAT duration are still needed by the FAT modal.
    afat_doctrines = []
    afat_default_duration = 60
    if config.enable_fat_link and apps.is_installed("afat"):
        try:
            from afat.models import Doctrine as AfatDoctrine, Setting as AfatSetting
            afat_doctrines = list(AfatDoctrine.objects.filter(is_enabled=True).values("pk", "name"))
            setting = AfatSetting.objects.first()
            if setting:
                afat_default_duration = setting.default_fatlink_expiry_time
        except Exception as exc:
            logger.warning("afat data lookup failed: %s", exc)

    # Whether the stored FAT link is a clickable one (ESI FATs aren't shared in the ping).
    fleet_clickable_fat = False
    if selected_fleet and selected_fleet.fat_link_hash and apps.is_installed("afat"):
        try:
            from afat.models import FatLink
            fl = FatLink.objects.filter(hash=selected_fleet.fat_link_hash).first()
            fleet_clickable_fat = bool(fl and not fl.is_esilink)
        except Exception as exc:
            logger.warning("FAT link lookup failed: %s", exc)

    fleet_summary = []
    for af in active_fleets:
        total = af.members.count()
        fleet_summary.append({
            "fleet": af,
            "member_count": total,
            "is_my_fc": af.fc.user == request.user,
        })

    # Extract numeric pk for fittings doctrine (template can't do string + int with add filter)
    selected_fittings_doctrine_pk = None
    if doctrine_pk and str(doctrine_pk).startswith("fittings-"):
        try:
            selected_fittings_doctrine_pk = int(str(doctrine_pk).split("-", 1)[1])
        except (ValueError, IndexError):
            pass

    context = {
        "fleet_summary": fleet_summary,
        "selected_fleet": selected_fleet,
        "selected_fleet_members": selected_fleet_members,
        "wings_data": wings_data,
        "on_doctrine_chars": on_doctrine_chars,
        "on_doctrine_count": on_doctrine_count,
        "role_counts": role_counts,
        "comp": comp,
        "snapshot_data": snapshot_data,
        "fleet_clickable_fat": fleet_clickable_fat,
        "doctrines": doctrines,
        "fittings_doctrines": fittings_doctrines,
        "layouts": layouts,
        "motd_templates": motd_templates,
        "motd_tpl_data": motd_tpl_data,
        "selected_doctrine_pk": doctrine_pk,
        "selected_fittings_doctrine_pk": selected_fittings_doctrine_pk,
        "selected_fleet_type": selected_fleet_type,
        "is_my_fleet": selected_fleet and selected_fleet.fc.user == request.user,
        "config": config,
        "fleet_types": fleet_types,
        "stagings": stagings,
        "afat_doctrines": afat_doctrines,
        "afat_default_duration": afat_default_duration,
        **nav_context("fleets"),
    }
    return render(request, "aa_fleet_tool/fleets.html", context)


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
def fleet_members_json(request, fleet_pk):
    """AJAX refresh endpoint for the member table."""
    fleet = get_object_or_404(ActiveFleet, pk=fleet_pk)
    members = list(
        fleet.members.order_by("role", "wing_id", "squad_id", "character_name").values(
            "character_id", "character_name", "ship_type_id", "ship_name",
            "system_name", "role", "wing_id", "squad_id", "takes_fleet_warp", "join_time",
            "station_id",
        )
    )

    wing_map = {w.wing_id: w.name for w in fleet.wings.all()}
    squad_map = {}
    for wing in fleet.wings.prefetch_related("squads"):
        for sq in wing.squads.all():
            squad_map[sq.squad_id] = sq.name
    for m in members:
        parts = []
        if m["wing_id"] and m["wing_id"] in wing_map:
            parts.append(wing_map[m["wing_id"]])
        if m["squad_id"] and m["squad_id"] in squad_map:
            parts.append(squad_map[m["squad_id"]])
        m["wing_squad_label"] = " / ".join(parts)
        m["join_time"] = m["join_time"].isoformat() if m["join_time"] else None

    fleet_role_counts = {"fleet_commander": 0, "wing_commander": 0, "squad_commander": 0, "squad_member": 0}
    for m in members:
        if m["role"] in fleet_role_counts:
            fleet_role_counts[m["role"]] += 1

    # A selected doctrine drives the on/off overlay AND fully replaces composition.
    doctrine_pk = request.GET.get("doctrine")
    doctrine_match = {}
    doctrine_roles = None
    if doctrine_pk:
        doctrine_ship_ids, ship_role_map = resolve_doctrine(doctrine_pk)
        if doctrine_ship_ids is not None:
            for m in members:
                doctrine_match[str(m["character_id"])] = m["ship_type_id"] in doctrine_ship_ids
            doctrine_roles = doctrine_overrides(ship_role_map)

    # Composition: SDE ship group by default; a doctrine fully overrides.
    role_breakdown = composition_counts([m["ship_type_id"] for m in members], doctrine_roles)

    history = [
        {"t": s["timestamp"].isoformat(), "dps": s["dps"], "logi": s["logi"], "total": s["total"]}
        for s in fleet.snapshots.values("timestamp", "dps", "logi", "total")
    ]

    return JsonResponse({
        "ok": True,
        "member_count": len(members),
        "last_updated": fleet.last_updated.isoformat() if fleet.last_updated else None,
        "members": members,
        "doctrine_match": doctrine_match,
        "role_breakdown": role_breakdown,
        "fleet_role_counts": fleet_role_counts,
        "history": history,
    })


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@require_POST
def set_fleet_name(request, fleet_pk):
    fleet = get_object_or_404(ActiveFleet, pk=fleet_pk)
    if fleet.fc.user != request.user:
        return JsonResponse({"ok": False, "error": _("Not authorized")}, status=403)
    fleet.name = request.POST.get("name", "").strip()
    fleet.save(update_fields=["name"])
    return JsonResponse({"ok": True, "name": fleet.name})


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@require_POST
def set_motd(request, fleet_pk):
    fleet, token = fleet_write(request, fleet_pk)
    if not fleet:
        return JsonResponse({"ok": False, "error": _("Not authorized")}, status=403)
    motd = request.POST.get("motd", "")
    _ignored, err = esi_call(
        lambda: esi.client.Fleets.PutFleetsFleetId(
            fleet_id=fleet.fleet_id, body={"motd": motd}, token=token
        )
    )
    if err:
        return err
    fleet.motd = motd
    fleet.save(update_fields=["motd"])
    return JsonResponse({"ok": True})


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@require_POST
def set_free_move(request, fleet_pk):
    fleet, token = fleet_write(request, fleet_pk)
    if not fleet:
        return JsonResponse({"ok": False, "error": _("Not authorized")}, status=403)
    value = request.POST.get("value", "false").lower() == "true"
    _ignored, err = esi_call(
        lambda: esi.client.Fleets.PutFleetsFleetId(
            fleet_id=fleet.fleet_id, body={"is_free_move": value}, token=token
        )
    )
    if err:
        return err
    fleet.is_free_move = value
    fleet.save(update_fields=["is_free_move"])
    return JsonResponse({"ok": True, "value": value})


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@require_POST
def kick_member(request, fleet_pk):
    fleet, token = fleet_write(request, fleet_pk)
    if not fleet:
        return JsonResponse({"ok": False, "error": _("Not authorized")}, status=403)
    char_id = request.POST.get("character_id")
    _ignored, err = esi_call(
        lambda: esi.client.Fleets.DeleteFleetsFleetIdMembersMemberId(
            fleet_id=fleet.fleet_id, member_id=int(char_id), token=token
        )
    )
    if err:
        return err
    fleet.members.filter(character_id=char_id).delete()
    return JsonResponse({"ok": True})


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@require_POST
def move_member(request, fleet_pk):
    fleet, token = fleet_write(request, fleet_pk)
    if not fleet:
        return JsonResponse({"ok": False, "error": _("Not authorized")}, status=403)
    char_id = request.POST.get("character_id")
    role = request.POST.get("role", "squad_member")
    wing_id = request.POST.get("wing_id")
    squad_id = request.POST.get("squad_id")
    body = {"role": role}
    if wing_id:
        body["wing_id"] = int(wing_id)
    if squad_id:
        body["squad_id"] = int(squad_id)
    _ignored, err = esi_call(
        lambda: esi.client.Fleets.PutFleetsFleetIdMembersMemberId(
            fleet_id=fleet.fleet_id, member_id=int(char_id), body=body, token=token
        )
    )
    if err:
        return err
    return JsonResponse({"ok": True})


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@require_POST
def invite_member(request, fleet_pk):
    fleet, token = fleet_write(request, fleet_pk)
    if not fleet:
        return JsonResponse({"ok": False, "error": _("Not authorized")}, status=403)
    char_id = int(request.POST.get("character_id", 0))
    role = request.POST.get("role", "squad_member")
    wing_id = request.POST.get("wing_id")
    squad_id = request.POST.get("squad_id")
    body = {"character_id": char_id, "role": role}
    if wing_id:
        body["wing_id"] = int(wing_id)
    if squad_id:
        body["squad_id"] = int(squad_id)
    _ignored, err = esi_call(
        lambda: esi.client.Fleets.PostFleetsFleetIdMembers(
            fleet_id=fleet.fleet_id, body=body, token=token
        )
    )
    if err:
        return err
    return JsonResponse({"ok": True})


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@require_POST
def create_wing(request, fleet_pk):
    fleet, token = fleet_write(request, fleet_pk)
    if not fleet:
        return JsonResponse({"ok": False, "error": _("Not authorized")}, status=403)
    data, err = esi_call(
        lambda: esi.client.Fleets.PostFleetsFleetIdWings(
            fleet_id=fleet.fleet_id, token=token
        )
    )
    if err:
        return err
    return JsonResponse({"ok": True, "wing_id": data.wing_id})


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@require_POST
def rename_wing(request, fleet_pk, wing_id):
    fleet, token = fleet_write(request, fleet_pk)
    if not fleet:
        return JsonResponse({"ok": False, "error": _("Not authorized")}, status=403)
    name = request.POST.get("name", "")
    _ignored, err = esi_call(
        lambda: esi.client.Fleets.PutFleetsFleetIdWingsWingId(
            fleet_id=fleet.fleet_id, wing_id=int(wing_id), body={"name": name}, token=token
        )
    )
    if err:
        return err
    fleet.wings.filter(wing_id=wing_id).update(name=name)
    return JsonResponse({"ok": True})


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@require_POST
def delete_wing(request, fleet_pk, wing_id):
    fleet, token = fleet_write(request, fleet_pk)
    if not fleet:
        return JsonResponse({"ok": False, "error": _("Not authorized")}, status=403)
    _ignored, err = esi_call(
        lambda: esi.client.Fleets.DeleteFleetsFleetIdWingsWingId(
            fleet_id=fleet.fleet_id, wing_id=int(wing_id), token=token
        )
    )
    if err:
        return err
    fleet.wings.filter(wing_id=wing_id).delete()
    return JsonResponse({"ok": True})


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@require_POST
def create_squad(request, fleet_pk, wing_id):
    fleet, token = fleet_write(request, fleet_pk)
    if not fleet:
        return JsonResponse({"ok": False, "error": _("Not authorized")}, status=403)
    data, err = esi_call(
        lambda: esi.client.Fleets.PostFleetsFleetIdWingsWingIdSquads(
            fleet_id=fleet.fleet_id, wing_id=int(wing_id), token=token
        )
    )
    if err:
        return err
    return JsonResponse({"ok": True, "squad_id": data.squad_id})


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@require_POST
def rename_squad(request, fleet_pk, squad_id):
    fleet, token = fleet_write(request, fleet_pk)
    if not fleet:
        return JsonResponse({"ok": False, "error": _("Not authorized")}, status=403)
    name = request.POST.get("name", "")
    _ignored, err = esi_call(
        lambda: esi.client.Fleets.PutFleetsFleetIdSquadsSquadId(
            fleet_id=fleet.fleet_id, squad_id=int(squad_id), body={"name": name}, token=token
        )
    )
    if err:
        return err
    FleetSquad.objects.filter(wing__fleet=fleet, squad_id=squad_id).update(name=name)
    return JsonResponse({"ok": True})


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@require_POST
def delete_squad(request, fleet_pk, squad_id):
    fleet, token = fleet_write(request, fleet_pk)
    if not fleet:
        return JsonResponse({"ok": False, "error": _("Not authorized")}, status=403)
    _ignored, err = esi_call(
        lambda: esi.client.Fleets.DeleteFleetsFleetIdSquadsSquadId(
            fleet_id=fleet.fleet_id, squad_id=int(squad_id), token=token
        )
    )
    if err:
        return err
    FleetSquad.objects.filter(wing__fleet=fleet, squad_id=squad_id).delete()
    return JsonResponse({"ok": True})
