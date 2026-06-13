"""Fleet Layouts page, layout CRUD and applying a layout to a live fleet."""

from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Max
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from esi.exceptions import HTTPClientError, HTTPServerError

from ..models import FleetLayout, FleetLayoutSquad, FleetLayoutWing
from ..providers import esi
from .common import esi_call, fleet_write, nav_context


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
def layouts(request):
    """Fleet Layouts management page."""
    context = {
        "layouts": FleetLayout.objects.prefetch_related("wings__squads"),
        **nav_context("layouts"),
    }
    return render(request, "aa_fleet_tool/layouts.html", context)


@login_required
@permission_required("aa_fleet_tool.manage_doctrine")
@require_POST
def create_layout(request):
    name = request.POST.get("name", "").strip()
    if not name:
        return JsonResponse({"ok": False, "error": _("Name required")}, status=400)
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
    """Apply a saved layout to the live fleet.

    Wings/squads are paired **positionally** with what already exists in the
    fleet: existing wings/squads are *renamed* in order, and any that the layout
    needs beyond the current count are created. Nothing is deleted — surplus
    wings/squads already in the fleet are left untouched. The user is warned of
    this in the Apply-Layout modal. ESI write errors per wing/squad are collected
    and returned as ``warnings`` rather than aborting the whole apply.
    """
    fleet, token = fleet_write(request, fleet_pk)
    if not fleet:
        return JsonResponse({"ok": False, "error": _("Not authorized or no write token")}, status=403)

    layout = get_object_or_404(FleetLayout, pk=layout_pk)
    layout_wings = list(layout.wings.prefetch_related("squads").order_by("position"))
    if not layout_wings:
        return JsonResponse({"ok": False, "error": _("Layout has no wings defined")}, status=400)

    fleet_id = fleet.fleet_id

    # Fetch current wings fresh from ESI
    try:
        existing_wings = sorted(
            esi.client.Fleets.GetFleetsFleetIdWings(fleet_id=fleet_id, token=token).result(),
            key=lambda w: w.id,
        )
    except (HTTPClientError, HTTPServerError) as exc:
        status = getattr(exc, "status_code", 502)
        return JsonResponse({"ok": False, "error": f"ESI wings fetch failed: {status}"}, status=502)

    errors = []

    for i, layout_wing in enumerate(layout_wings):
        if i < len(existing_wings):
            ew = existing_wings[i]
            wing_id = ew.id
            existing_squads = sorted(getattr(ew, "squads", None) or [], key=lambda s: s.id)
        else:
            data, err = esi_call(
                lambda: esi.client.Fleets.PostFleetsFleetIdWings(fleet_id=fleet_id, token=token)
            )
            if err:
                errors.append(_("Wing '%s' could not be created") % layout_wing.name)
                continue
            wing_id = data.wing_id
            existing_squads = []

        # Rename the wing (best effort)
        esi_call(
            lambda wid=wing_id, name=layout_wing.name: esi.client.Fleets.PutFleetsFleetIdWingsWingId(
                fleet_id=fleet_id, wing_id=wid, body={"name": name}, token=token
            )
        )

        layout_squads = list(layout_wing.squads.order_by("position"))
        for j, layout_squad in enumerate(layout_squads):
            if j < len(existing_squads):
                squad_id = existing_squads[j].id
            else:
                data, err = esi_call(
                    lambda wid=wing_id: esi.client.Fleets.PostFleetsFleetIdWingsWingIdSquads(
                        fleet_id=fleet_id, wing_id=wid, token=token
                    )
                )
                if err:
                    errors.append(_("Squad '%s' could not be created") % layout_squad.name)
                    continue
                squad_id = data.squad_id

            esi_call(
                lambda sid=squad_id, name=layout_squad.name: esi.client.Fleets.PutFleetsFleetIdSquadsSquadId(
                    fleet_id=fleet_id, squad_id=sid, body={"name": name}, token=token
                )
            )

    if errors:
        return JsonResponse({"ok": True, "warnings": errors})
    return JsonResponse({"ok": True})
