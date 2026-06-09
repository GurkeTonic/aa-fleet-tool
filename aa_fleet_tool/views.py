import logging

import requests
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from esi.decorators import token_required

from django.apps import apps
from django.utils import timezone

from .models import (
    ActiveFleet,
    Doctrine,
    DoctrineShip,
    FleetCommander,
    FleetLayout,
    FleetLayoutSquad,
    FleetLayoutWing,
    FleetMember,
    FleetToolConfiguration,
    MOTDTemplate,
)
from .tasks import ESI_BASE, _base_headers, _get_token, sync_fc

logger = logging.getLogger(__name__)

WRITE_SCOPE = "esi-fleets.write_fleet.v1"


def _write_headers(character_id: int) -> dict | None:
    token = _get_token(character_id, WRITE_SCOPE)
    if not token:
        return None
    try:
        at = token.valid_access_token()
    except Exception as exc:
        logger.warning("Could not get write access token for char %s: %s", character_id, exc)
        return None
    return {**_base_headers(), "Authorization": f"Bearer {at}", "Content-Type": "application/json"}


# ── Character management ──────────────────────────────────────────────────────

@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@token_required(scopes=["esi-fleets.read_fleet.v1", "esi-fleets.write_fleet.v1"])
def add_fc(request, token):
    from allianceauth.eveonline.models import EveCharacter

    try:
        char = EveCharacter.objects.get(character_id=token.character_id)
    except EveCharacter.DoesNotExist:
        messages.error(request, "Charakter nicht in Auth gefunden.")
        return redirect("aa_fleet_tool:index")

    fc, created = FleetCommander.objects.get_or_create(
        character=char, defaults={"user": request.user}
    )
    if created:
        sync_fc.delay(fc.pk)
        messages.success(request, f"{char.character_name} als FC registriert. Sync läuft…")
    else:
        messages.info(request, f"{char.character_name} ist bereits registriert.")
    return redirect("aa_fleet_tool:index")


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@require_POST
def remove_fc(request):
    fc_pk = request.POST.get("fc_pk")
    FleetCommander.objects.filter(pk=fc_pk, user=request.user).delete()
    return JsonResponse({"ok": True})


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@require_POST
def trigger_sync(request):
    for fc in FleetCommander.objects.filter(user=request.user):
        sync_fc.delay(fc.pk)
    return JsonResponse({"ok": True})


def _resolve_doctrine(doctrine_pk):
    """Return (ship_type_id_set, ship_role_map) for a given doctrine_pk string.

    Supports local doctrines (plain integer) and fittings doctrines ("fittings-<pk>").
    Returns (None, None) if not found.
    """
    if not doctrine_pk:
        return None, None

    if str(doctrine_pk).startswith("fittings-"):
        if not apps.is_installed("fittings"):
            return None, None
        try:
            from fittings.models import Doctrine as FittingsDoctrine
            pk = int(str(doctrine_pk).split("-", 1)[1])
            doc = FittingsDoctrine.objects.prefetch_related("fittings__ship_type").get(pk=pk)
            ship_ids = {f.ship_type_type_id for f in doc.fittings.all()}
            # Fittings has no role_hint → all ships map to "any" (will go to "other" bucket)
            ship_role_map = {sid: "any" for sid in ship_ids}
            return ship_ids, ship_role_map
        except Exception:
            return None, None
    else:
        try:
            doc = Doctrine.objects.prefetch_related("ships").get(pk=int(doctrine_pk))
            ships = list(doc.ships.all())
            ship_ids = {ds.ship_type_id for ds in ships}
            ship_role_map = {ds.ship_type_id: ds.role_hint for ds in ships}
            return ship_ids, ship_role_map
        except (Doctrine.DoesNotExist, ValueError):
            return None, None


# ── Main view ─────────────────────────────────────────────────────────────────

@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
def index(request):
    all_fcs = FleetCommander.objects.select_related("character", "user")
    my_fcs = all_fcs.filter(user=request.user)

    active_fleets = (
        ActiveFleet.objects.select_related("fc__character", "fc__user")
        .prefetch_related("members", "wings__squads")
        .all()
    )

    selected_fleet = None
    selected_fleet_members = []
    wings_data = []
    on_doctrine_chars = set()  # set of character_ids that are on-doctrine
    on_doctrine_count = 0
    comp = {"dps": {"count": 0, "pct": 0}, "logi": {"count": 0, "pct": 0},
            "booster": {"count": 0, "pct": 0}, "ewar": {"count": 0, "pct": 0},
            "other": {"count": 0, "pct": 0}}

    fleet_pk = request.GET.get("fleet")
    doctrine_pk = request.GET.get("doctrine")
    selected_fleet_type = request.GET.get("fleet_type", "")

    # Maps role_hint values to the 5 display buckets
    _COMP_BUCKET = {"dps": "dps", "logi": "logi", "booster": "booster", "ewar": "ewar"}

    if fleet_pk:
        try:
            selected_fleet = active_fleets.get(pk=fleet_pk)
            selected_fleet_members = list(
                selected_fleet.members.order_by("role", "wing_id", "squad_id", "character_name")
            )

            if doctrine_pk:
                doctrine_ship_ids, ship_role_map = _resolve_doctrine(doctrine_pk)
                if doctrine_ship_ids is not None:
                    on_doctrine_chars = {
                        m.character_id
                        for m in selected_fleet_members
                        if m.ship_type_id in doctrine_ship_ids
                    }
                    on_doctrine_count = len(on_doctrine_chars)
                    total = len(selected_fleet_members)
                    counts = {"dps": 0, "logi": 0, "booster": 0, "ewar": 0, "other": 0}
                    for m in selected_fleet_members:
                        bucket = _COMP_BUCKET.get(ship_role_map.get(m.ship_type_id, ""), "other")
                        counts[bucket] += 1
                    comp = {
                        role: {"count": c, "pct": round(c * 100 / total) if total else 0}
                        for role, c in counts.items()
                    }

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
    motd_templates = MOTDTemplate.objects.all()
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
        except Exception:
            pass

    # afat fleet types and doctrines for FAT modal
    afat_fleet_types = []
    afat_doctrines = []
    afat_default_duration = 60
    if config.enable_fat_link and apps.is_installed("afat"):
        try:
            from afat.models import FleetType as AfatFleetType, Doctrine as AfatDoctrine, Setting as AfatSetting
            afat_fleet_types = list(AfatFleetType.objects.filter(is_enabled=True).values("pk", "name"))
            afat_doctrines = list(AfatDoctrine.objects.filter(is_enabled=True).values("pk", "name"))
            setting = AfatSetting.objects.first()
            if setting:
                afat_default_duration = setting.default_fatlink_expiry_time
        except Exception:
            pass

    # aasrp fleet types for SRP modal
    aasrp_fleet_types = []
    if config.enable_srp_link and apps.is_installed("aasrp"):
        try:
            from aasrp.models import FleetType as AasrpFleetType
            aasrp_fleet_types = list(AasrpFleetType.objects.filter(is_enabled=True).values("pk", "name"))
        except Exception:
            pass

    # Combined fleet type name list (deduplicated) for the global selector
    seen = set()
    fleet_types_combined = []
    for ft in list(afat_fleet_types) + list(aasrp_fleet_types):
        if ft["name"] not in seen:
            seen.add(ft["name"])
            fleet_types_combined.append(ft["name"])

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
        "my_fcs": my_fcs,
        "all_fcs": all_fcs,
        "fleet_summary": fleet_summary,
        "selected_fleet": selected_fleet,
        "selected_fleet_members": selected_fleet_members,
        "wings_data": wings_data,
        "on_doctrine_chars": on_doctrine_chars,
        "on_doctrine_count": on_doctrine_count,
        "role_counts": role_counts,
        "comp": comp,
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
        "fleet_types_combined": fleet_types_combined,
        "afat_fleet_types": afat_fleet_types,
        "afat_doctrines": afat_doctrines,
        "afat_default_duration": afat_default_duration,
        "aasrp_fleet_types": aasrp_fleet_types,
    }
    return render(request, "aa_fleet_tool/index.html", context)


# ── Fleet management (direct ESI write calls) ─────────────────────────────────

def _fleet_write(request, fleet_pk):
    """Return (fleet, headers) or (None, None) if not authorized or no write token."""
    fleet = get_object_or_404(ActiveFleet, pk=fleet_pk)
    if fleet.fc.user != request.user:
        return None, None
    headers = _write_headers(fleet.fc.character.character_id)
    if headers is None:
        return None, None
    return fleet, headers


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@require_POST
def set_fleet_name(request, fleet_pk):
    fleet = get_object_or_404(ActiveFleet, pk=fleet_pk)
    if fleet.fc.user != request.user:
        return JsonResponse({"ok": False, "error": "Not authorized"}, status=403)
    fleet.name = request.POST.get("name", "").strip()
    fleet.save(update_fields=["name"])
    return JsonResponse({"ok": True, "name": fleet.name})


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@require_POST
def set_motd(request, fleet_pk):
    fleet, headers = _fleet_write(request, fleet_pk)
    if not fleet:
        return JsonResponse({"ok": False, "error": "Nicht autorisiert"}, status=403)
    motd = request.POST.get("motd", "")
    resp = requests.put(
        f"{ESI_BASE}/v1/fleets/{fleet.fleet_id}",
        json={"motd": motd},
        headers=headers,
        timeout=30,
    )
    if resp.status_code == 204:
        fleet.motd = motd
        fleet.save(update_fields=["motd"])
        return JsonResponse({"ok": True})
    return JsonResponse({"ok": False, "error": resp.text}, status=resp.status_code)


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@require_POST
def set_free_move(request, fleet_pk):
    fleet, headers = _fleet_write(request, fleet_pk)
    if not fleet:
        return JsonResponse({"ok": False, "error": "Nicht autorisiert"}, status=403)
    value = request.POST.get("value", "false").lower() == "true"
    resp = requests.put(
        f"{ESI_BASE}/v1/fleets/{fleet.fleet_id}",
        json={"is_free_move": value},
        headers=headers,
        timeout=30,
    )
    if resp.status_code == 204:
        fleet.is_free_move = value
        fleet.save(update_fields=["is_free_move"])
        return JsonResponse({"ok": True, "value": value})
    return JsonResponse({"ok": False, "error": resp.text}, status=resp.status_code)


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@require_POST
def kick_member(request, fleet_pk):
    fleet, headers = _fleet_write(request, fleet_pk)
    if not fleet:
        return JsonResponse({"ok": False, "error": "Nicht autorisiert"}, status=403)
    char_id = request.POST.get("character_id")
    resp = requests.delete(
        f"{ESI_BASE}/v1/fleets/{fleet.fleet_id}/members/{char_id}",
        headers=headers,
        timeout=30,
    )
    if resp.status_code == 204:
        fleet.members.filter(character_id=char_id).delete()
        return JsonResponse({"ok": True})
    return JsonResponse({"ok": False, "error": resp.text}, status=resp.status_code)


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@require_POST
def move_member(request, fleet_pk):
    fleet, headers = _fleet_write(request, fleet_pk)
    if not fleet:
        return JsonResponse({"ok": False, "error": "Nicht autorisiert"}, status=403)
    char_id = request.POST.get("character_id")
    role = request.POST.get("role", "squad_member")
    wing_id = request.POST.get("wing_id")
    squad_id = request.POST.get("squad_id")
    body = {"role": role}
    if wing_id:
        body["wing_id"] = int(wing_id)
    if squad_id:
        body["squad_id"] = int(squad_id)
    resp = requests.put(
        f"{ESI_BASE}/v1/fleets/{fleet.fleet_id}/members/{char_id}",
        json=body,
        headers=headers,
        timeout=30,
    )
    if resp.status_code == 204:
        return JsonResponse({"ok": True})
    return JsonResponse({"ok": False, "error": resp.text}, status=resp.status_code)


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@require_POST
def invite_member(request, fleet_pk):
    fleet, headers = _fleet_write(request, fleet_pk)
    if not fleet:
        return JsonResponse({"ok": False, "error": "Nicht autorisiert"}, status=403)
    char_id = int(request.POST.get("character_id", 0))
    role = request.POST.get("role", "squad_member")
    wing_id = request.POST.get("wing_id")
    squad_id = request.POST.get("squad_id")
    body = {"character_id": char_id, "role": role}
    if wing_id:
        body["wing_id"] = int(wing_id)
    if squad_id:
        body["squad_id"] = int(squad_id)
    resp = requests.post(
        f"{ESI_BASE}/v1/fleets/{fleet.fleet_id}/members",
        json=body,
        headers=headers,
        timeout=30,
    )
    if resp.status_code == 204:
        return JsonResponse({"ok": True})
    return JsonResponse({"ok": False, "error": resp.text}, status=resp.status_code)


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@require_POST
def create_wing(request, fleet_pk):
    fleet, headers = _fleet_write(request, fleet_pk)
    if not fleet:
        return JsonResponse({"ok": False, "error": "Nicht autorisiert"}, status=403)
    resp = requests.post(
        f"{ESI_BASE}/v1/fleets/{fleet.fleet_id}/wings",
        headers=headers,
        timeout=30,
    )
    if resp.status_code == 201:
        wing_id = resp.json()["wing_id"]
        return JsonResponse({"ok": True, "wing_id": wing_id})
    return JsonResponse({"ok": False, "error": resp.text}, status=resp.status_code)


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@require_POST
def rename_wing(request, fleet_pk, wing_id):
    fleet, headers = _fleet_write(request, fleet_pk)
    if not fleet:
        return JsonResponse({"ok": False, "error": "Nicht autorisiert"}, status=403)
    name = request.POST.get("name", "")
    resp = requests.put(
        f"{ESI_BASE}/v1/fleets/{fleet.fleet_id}/wings/{wing_id}",
        json={"name": name},
        headers=headers,
        timeout=30,
    )
    if resp.status_code == 204:
        fleet.wings.filter(wing_id=wing_id).update(name=name)
        return JsonResponse({"ok": True})
    return JsonResponse({"ok": False, "error": resp.text}, status=resp.status_code)


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@require_POST
def delete_wing(request, fleet_pk, wing_id):
    fleet, headers = _fleet_write(request, fleet_pk)
    if not fleet:
        return JsonResponse({"ok": False, "error": "Nicht autorisiert"}, status=403)
    resp = requests.delete(
        f"{ESI_BASE}/v1/fleets/{fleet.fleet_id}/wings/{wing_id}",
        headers=headers,
        timeout=30,
    )
    if resp.status_code == 204:
        fleet.wings.filter(wing_id=wing_id).delete()
        return JsonResponse({"ok": True})
    return JsonResponse({"ok": False, "error": resp.text}, status=resp.status_code)


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@require_POST
def create_squad(request, fleet_pk, wing_id):
    fleet, headers = _fleet_write(request, fleet_pk)
    if not fleet:
        return JsonResponse({"ok": False, "error": "Nicht autorisiert"}, status=403)
    resp = requests.post(
        f"{ESI_BASE}/v1/fleets/{fleet.fleet_id}/wings/{wing_id}/squads",
        headers=headers,
        timeout=30,
    )
    if resp.status_code == 201:
        squad_id = resp.json()["squad_id"]
        return JsonResponse({"ok": True, "squad_id": squad_id})
    return JsonResponse({"ok": False, "error": resp.text}, status=resp.status_code)


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@require_POST
def rename_squad(request, fleet_pk, squad_id):
    fleet, headers = _fleet_write(request, fleet_pk)
    if not fleet:
        return JsonResponse({"ok": False, "error": "Nicht autorisiert"}, status=403)
    wing_id = request.POST.get("wing_id")
    name = request.POST.get("name", "")
    resp = requests.put(
        f"{ESI_BASE}/v1/fleets/{fleet.fleet_id}/squads/{squad_id}",
        json={"name": name},
        headers=headers,
        timeout=30,
    )
    if resp.status_code == 204:
        from .models import FleetSquad
        FleetSquad.objects.filter(wing__fleet=fleet, squad_id=squad_id).update(name=name)
        return JsonResponse({"ok": True})
    return JsonResponse({"ok": False, "error": resp.text}, status=resp.status_code)


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@require_POST
def delete_squad(request, fleet_pk, squad_id):
    fleet, headers = _fleet_write(request, fleet_pk)
    if not fleet:
        return JsonResponse({"ok": False, "error": "Nicht autorisiert"}, status=403)
    resp = requests.delete(
        f"{ESI_BASE}/v1/fleets/{fleet.fleet_id}/squads/{squad_id}",
        headers=headers,
        timeout=30,
    )
    if resp.status_code == 204:
        from .models import FleetSquad
        FleetSquad.objects.filter(wing__fleet=fleet, squad_id=squad_id).delete()
        return JsonResponse({"ok": True})
    return JsonResponse({"ok": False, "error": resp.text}, status=resp.status_code)


# ── Doctrine management ───────────────────────────────────────────────────────

@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
def ship_search(request):
    from django.http import JsonResponse
    q = request.GET.get("q", "").strip()
    if len(q) < 2:
        return JsonResponse({"results": []})
    from eve_sde.models import ItemType
    ships = (
        ItemType.objects
        .filter(name__icontains=q, group__category__pk=6, published=True)
        .order_by("name")[:12]
    )
    return JsonResponse({"results": [{"type_id": s.pk, "name": s.name} for s in ships]})


@login_required
@permission_required("aa_fleet_tool.manage_doctrine")
@require_POST
def create_doctrine(request):
    name = request.POST.get("name", "").strip()
    if not name:
        return JsonResponse({"ok": False, "error": "Name erforderlich"}, status=400)
    doc = Doctrine.objects.create(name=name, description=request.POST.get("description", ""), created_by=request.user)
    return JsonResponse({"ok": True, "pk": doc.pk, "name": doc.name})


@login_required
@permission_required("aa_fleet_tool.manage_doctrine")
@require_POST
def delete_doctrine(request, pk):
    get_object_or_404(Doctrine, pk=pk).delete()
    return JsonResponse({"ok": True})


@login_required
@permission_required("aa_fleet_tool.manage_doctrine")
@require_POST
def add_doctrine_ship(request, pk):
    doctrine = get_object_or_404(Doctrine, pk=pk)
    try:
        ship_type_id = int(request.POST.get("ship_type_id", 0))
    except (ValueError, TypeError):
        ship_type_id = 0
    ship_name = request.POST.get("ship_name", "").strip()
    role_hint = request.POST.get("role_hint", "any")
    if not ship_type_id or not ship_name:
        return JsonResponse({"ok": False, "error": "Ship Type ID und Ship Name sind Pflichtfelder."}, status=400)
    ship, created = DoctrineShip.objects.get_or_create(
        doctrine=doctrine,
        ship_type_id=ship_type_id,
        defaults={"ship_name": ship_name, "role_hint": role_hint},
    )
    return JsonResponse({"ok": True, "pk": ship.pk, "ship_name": ship.ship_name, "created": created})


@login_required
@permission_required("aa_fleet_tool.manage_doctrine")
@require_POST
def remove_doctrine_ship(request, pk):
    get_object_or_404(DoctrineShip, pk=pk).delete()
    return JsonResponse({"ok": True})


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
def fleet_members_json(request, fleet_pk):
    """AJAX refresh endpoint for member table."""
    fleet = get_object_or_404(ActiveFleet, pk=fleet_pk)
    members = list(
        fleet.members.order_by("role", "wing_id", "squad_id", "character_name").values(
            "character_id", "character_name", "ship_type_id", "ship_name",
            "system_name", "role", "wing_id", "squad_id", "takes_fleet_warp", "join_time",
            "station_id",
        )
    )

    # Build wing/squad label map for the table
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
        # join_time not JSON-serializable as datetime
        m["join_time"] = m["join_time"].isoformat() if m["join_time"] else None

    fleet_role_counts = {"fleet_commander": 0, "wing_commander": 0, "squad_commander": 0, "squad_member": 0}
    for m in members:
        if m["role"] in fleet_role_counts:
            fleet_role_counts[m["role"]] += 1

    _COMP_BUCKET = {"dps": "dps", "logi": "logi", "booster": "booster", "ewar": "ewar"}

    doctrine_pk = request.GET.get("doctrine")
    doctrine_match = {}
    role_breakdown = {"dps": {"count": 0, "pct": 0}, "logi": {"count": 0, "pct": 0},
                      "booster": {"count": 0, "pct": 0}, "ewar": {"count": 0, "pct": 0},
                      "other": {"count": 0, "pct": 0}}
    if doctrine_pk:
        doctrine_ship_ids, ship_role_map = _resolve_doctrine(doctrine_pk)
        if doctrine_ship_ids is not None:
            for m in members:
                doctrine_match[str(m["character_id"])] = m["ship_type_id"] in doctrine_ship_ids
            total = len(members)
            counts = {"dps": 0, "logi": 0, "booster": 0, "ewar": 0, "other": 0}
            for m in members:
                bucket = _COMP_BUCKET.get(ship_role_map.get(m["ship_type_id"], ""), "other")
                counts[bucket] += 1
            role_breakdown = {
                role: {"count": c, "pct": round(c * 100 / total) if total else 0}
                for role, c in counts.items()
            }

    return JsonResponse({
        "ok": True,
        "member_count": len(members),
        "last_updated": fleet.last_updated.isoformat() if fleet.last_updated else None,
        "members": members,
        "doctrine_match": doctrine_match,
        "role_breakdown": role_breakdown,
        "fleet_role_counts": fleet_role_counts,
    })


# ── Fleet Layout management ───────────────────────────────────────────────────

@login_required
@permission_required("aa_fleet_tool.manage_doctrine")
@require_POST
def create_layout(request):
    name = request.POST.get("name", "").strip()
    if not name:
        return JsonResponse({"ok": False, "error": "Name erforderlich"}, status=400)
    layout = FleetLayout.objects.create(
        name=name,
        description=request.POST.get("description", "").strip(),
        created_by=request.user,
    )
    return JsonResponse({"ok": True, "pk": layout.pk, "name": layout.name})


@login_required
@permission_required("aa_fleet_tool.manage_doctrine")
@require_POST
def delete_layout(request, pk):
    get_object_or_404(FleetLayout, pk=pk).delete()
    return JsonResponse({"ok": True})


@login_required
@permission_required("aa_fleet_tool.manage_doctrine")
@require_POST
def add_layout_wing(request, pk):
    layout = get_object_or_404(FleetLayout, pk=pk)
    name = request.POST.get("name", "").strip() or "Wing"
    from django.db.models import Max
    next_pos = (layout.wings.aggregate(m=Max("position"))["m"] or 0) + 1
    wing = FleetLayoutWing.objects.create(layout=layout, position=next_pos, name=name)
    return JsonResponse({"ok": True, "pk": wing.pk, "name": wing.name, "position": wing.position})


@login_required
@permission_required("aa_fleet_tool.manage_doctrine")
@require_POST
def rename_layout_wing(request, pk):
    wing = get_object_or_404(FleetLayoutWing, pk=pk)
    wing.name = request.POST.get("name", wing.name).strip()
    wing.save(update_fields=["name"])
    return JsonResponse({"ok": True})


@login_required
@permission_required("aa_fleet_tool.manage_doctrine")
@require_POST
def delete_layout_wing(request, pk):
    get_object_or_404(FleetLayoutWing, pk=pk).delete()
    return JsonResponse({"ok": True})


@login_required
@permission_required("aa_fleet_tool.manage_doctrine")
@require_POST
def add_layout_squad(request, pk):
    wing = get_object_or_404(FleetLayoutWing, pk=pk)
    name = request.POST.get("name", "").strip() or "Squad"
    from django.db.models import Max
    next_pos = (wing.squads.aggregate(m=Max("position"))["m"] or 0) + 1
    squad = FleetLayoutSquad.objects.create(wing=wing, position=next_pos, name=name)
    return JsonResponse({"ok": True, "pk": squad.pk, "name": squad.name})


@login_required
@permission_required("aa_fleet_tool.manage_doctrine")
@require_POST
def rename_layout_squad(request, pk):
    squad = get_object_or_404(FleetLayoutSquad, pk=pk)
    squad.name = request.POST.get("name", squad.name).strip()
    squad.save(update_fields=["name"])
    return JsonResponse({"ok": True})


@login_required
@permission_required("aa_fleet_tool.manage_doctrine")
@require_POST
def delete_layout_squad(request, pk):
    get_object_or_404(FleetLayoutSquad, pk=pk).delete()
    return JsonResponse({"ok": True})


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@require_POST
def apply_layout(request, fleet_pk, layout_pk):
    fleet, headers = _fleet_write(request, fleet_pk)
    if not fleet:
        return JsonResponse({"ok": False, "error": "Nicht autorisiert oder kein Write-Token"}, status=403)

    layout = get_object_or_404(FleetLayout, pk=layout_pk)
    layout_wings = list(layout.wings.prefetch_related("squads").order_by("position"))
    if not layout_wings:
        return JsonResponse({"ok": False, "error": "Layout hat keine Wings definiert"}, status=400)

    # Fetch current wings fresh from ESI
    resp = requests.get(
        f"{ESI_BASE}/v1/fleets/{fleet.fleet_id}/wings",
        headers=headers,
        timeout=30,
    )
    if resp.status_code != 200:
        return JsonResponse({"ok": False, "error": f"ESI wings fetch failed: {resp.status_code}"}, status=502)

    existing_wings = sorted(resp.json(), key=lambda w: w["id"])

    errors = []

    for i, layout_wing in enumerate(layout_wings):
        if i < len(existing_wings):
            ew = existing_wings[i]
            wing_id = ew["id"]
            existing_squads = sorted(ew.get("squads", []), key=lambda s: s["id"])
        else:
            cr = requests.post(
                f"{ESI_BASE}/v1/fleets/{fleet.fleet_id}/wings",
                headers=headers,
                timeout=30,
            )
            if cr.status_code != 201:
                errors.append(f"Wing '{layout_wing.name}' konnte nicht erstellt werden")
                continue
            wing_id = cr.json()["wing_id"]
            existing_squads = []

        # Rename the wing
        requests.put(
            f"{ESI_BASE}/v1/fleets/{fleet.fleet_id}/wings/{wing_id}",
            json={"name": layout_wing.name},
            headers=headers,
            timeout=30,
        )

        layout_squads = list(layout_wing.squads.order_by("position"))
        for j, layout_squad in enumerate(layout_squads):
            if j < len(existing_squads):
                squad_id = existing_squads[j]["id"]
            else:
                cr = requests.post(
                    f"{ESI_BASE}/v1/fleets/{fleet.fleet_id}/wings/{wing_id}/squads",
                    headers=headers,
                    timeout=30,
                )
                if cr.status_code != 201:
                    errors.append(f"Squad '{layout_squad.name}' konnte nicht erstellt werden")
                    continue
                squad_id = cr.json()["squad_id"]

            requests.put(
                f"{ESI_BASE}/v1/fleets/{fleet.fleet_id}/squads/{squad_id}",
                json={"name": layout_squad.name},
                headers=headers,
                timeout=30,
            )

    if errors:
        return JsonResponse({"ok": True, "warnings": errors})
    return JsonResponse({"ok": True})


# ── MOTD Templates ────────────────────────────────────────────────────────────

@login_required
@permission_required("aa_fleet_tool.manage_doctrine")
@require_POST
def create_motd_template(request):
    name = request.POST.get("name", "").strip()
    text = request.POST.get("text", "").strip()
    if not name:
        return JsonResponse({"ok": False, "error": "Name erforderlich"}, status=400)
    tpl = MOTDTemplate.objects.create(name=name, text=text, created_by=request.user)
    return JsonResponse({"ok": True, "pk": tpl.pk, "name": tpl.name})


@login_required
@permission_required("aa_fleet_tool.manage_doctrine")
@require_POST
def update_motd_template(request, pk):
    tpl = get_object_or_404(MOTDTemplate, pk=pk)
    name = request.POST.get("name", "").strip()
    if not name:
        return JsonResponse({"ok": False, "error": "Name erforderlich"}, status=400)
    tpl.name = name
    tpl.text = request.POST.get("text", "")
    tpl.save(update_fields=["name", "text"])
    return JsonResponse({"ok": True})


@login_required
@permission_required("aa_fleet_tool.manage_doctrine")
@require_POST
def delete_motd_template(request, pk):
    get_object_or_404(MOTDTemplate, pk=pk).delete()
    return JsonResponse({"ok": True})


# ── FAT Link integration ──────────────────────────────────────────────────────

@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@require_POST
def create_fat_link(request, fleet_pk):
    if not apps.is_installed("afat"):
        return JsonResponse({"ok": False, "error": "afat is not installed"}, status=400)

    fleet = get_object_or_404(ActiveFleet, pk=fleet_pk)
    if fleet.fc.user != request.user:
        return JsonResponse({"ok": False, "error": "Not authorized"}, status=403)

    name = request.POST.get("name", "").strip()
    if not name:
        return JsonResponse({"ok": False, "error": "Fleet name required"}, status=400)

    try:
        import secrets
        from afat.models import FatLink, Duration, FleetType as AfatFleetType
        from allianceauth.eveonline.models import EveCharacter

        hash_val = secrets.token_urlsafe(30)[:30]

        fleet_type_pk = request.POST.get("fleet_type_pk")
        fleet_type_name = ""
        if fleet_type_pk:
            try:
                fleet_type_name = AfatFleetType.objects.get(pk=fleet_type_pk).name
            except AfatFleetType.DoesNotExist:
                pass

        doctrine_name = request.POST.get("doctrine_name", "").strip()
        duration_minutes = int(request.POST.get("duration", 60))

        character = None
        try:
            character = request.user.profile.main_character
        except Exception:
            character = EveCharacter.objects.filter(
                fleet_commander__user=request.user
            ).first()

        link_type = request.POST.get("link_type", "clickable")

        if link_type == "esi":
            # ESI FAT link — auto-registers current fleet members immediately,
            # periodic afat task keeps adding new members
            fat_link = FatLink.objects.create(
                fleet=name,
                hash=hash_val,
                creator=request.user,
                character=character,
                fleet_type=fleet_type_name,
                doctrine=doctrine_name,
                is_esilink=True,
                is_registered_on_esi=True,
                esi_fleet_id=fleet.fleet_id,
            )
            # Feed current members directly to afat's processing task
            from afat.tasks import process_fats
            member_data = list(
                fleet.members.values("character_id", "solar_system_id", "ship_type_id")
            )
            if member_data:
                process_fats.delay(
                    data_list=member_data,
                    data_source="esi",
                    fatlink_hash=hash_val,
                )
            details_url = f"/afat/fatlinks/{hash_val}/details/"
            return JsonResponse({"ok": True, "hash": hash_val, "link_type": "esi", "details_url": details_url})
        else:
            fat_link = FatLink.objects.create(
                fleet=name,
                hash=hash_val,
                creator=request.user,
                character=character,
                fleet_type=fleet_type_name,
                doctrine=doctrine_name,
                is_esilink=False,
                is_registered_on_esi=False,
            )
            Duration.objects.create(fleet=fat_link, duration=duration_minutes)
            register_url = f"/afat/fatlinks/{hash_val}/register/"
            return JsonResponse({"ok": True, "hash": hash_val, "link_type": "clickable", "register_url": register_url})

    except Exception as exc:
        logger.exception("FAT link creation failed: %s", exc)
        return JsonResponse({"ok": False, "error": str(exc)}, status=500)


# ── SRP Link integration ──────────────────────────────────────────────────────

@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@require_POST
def create_srp_link(request, fleet_pk):
    if not apps.is_installed("aasrp"):
        return JsonResponse({"ok": False, "error": "aasrp is not installed"}, status=400)

    fleet = get_object_or_404(ActiveFleet, pk=fleet_pk)
    if fleet.fc.user != request.user:
        return JsonResponse({"ok": False, "error": "Not authorized"}, status=403)

    srp_name = request.POST.get("srp_name", "").strip()
    fleet_doctrine = request.POST.get("fleet_doctrine", "").strip()
    if not srp_name:
        return JsonResponse({"ok": False, "error": "SRP name required"}, status=400)
    if not fleet_doctrine:
        return JsonResponse({"ok": False, "error": "Doctrine required"}, status=400)

    try:
        from aasrp.models import SrpLink, FleetType as AasrpFleetType

        fleet_type_name = request.POST.get("fleet_type_name", "").strip()
        fleet_type = None
        if fleet_type_name:
            fleet_type = AasrpFleetType.objects.filter(name__iexact=fleet_type_name).first()
            if fleet_type is None:
                fleet_type = AasrpFleetType.objects.create(name=fleet_type_name)

        character = None
        try:
            character = request.user.profile.main_character
        except Exception:
            from allianceauth.eveonline.models import EveCharacter
            character = EveCharacter.objects.filter(
                fleet_commander__user=request.user
            ).first()

        aar_link = request.POST.get("aar_link", "").strip()

        srp_link = SrpLink.objects.create(
            srp_name=srp_name,
            fleet_time=timezone.now(),
            fleet_commander=character,
            fleet_type=fleet_type,
            fleet_doctrine=fleet_doctrine,
            aar_link=aar_link,
            creator=request.user,
        )

        request_url = f"/srp/srp-link/{srp_link.srp_code}/request-srp/"
        return JsonResponse({"ok": True, "srp_code": srp_link.srp_code, "request_url": request_url})

    except Exception as exc:
        logger.exception("SRP link creation failed: %s", exc)
        return JsonResponse({"ok": False, "error": str(exc)}, status=500)
