"""Fleet Commanders page + FC registration and Fleet Start/Stop control."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from esi.decorators import token_required

from ..constants import FLEET_SCOPES
from ..models import ActiveFleet, FleetCommander
from ..tasks import check_fc_in_fleet, sync_fc
from .common import nav_context


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
def commanders(request):
    """Fleet Commanders overview page."""
    all_fcs = FleetCommander.objects.select_related("character", "user")
    context = {"all_fcs": all_fcs, **nav_context("commanders")}
    return render(request, "aa_fleet_tool/commanders.html", context)


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@token_required(scopes=FLEET_SCOPES)
def add_fc(request, token):
    from allianceauth.authentication.models import CharacterOwnership
    from allianceauth.eveonline.models import EveCharacter

    try:
        char = EveCharacter.objects.get(character_id=token.character_id)
    except EveCharacter.DoesNotExist:
        messages.error(request, _("Character not found in Auth."))
        return redirect("aa_fleet_tool:commanders")

    # AA convention: a user may only register their own characters.
    if not CharacterOwnership.objects.filter(
        user=request.user, character=char
    ).exists():
        messages.error(request, _("That character is not registered to your account."))
        return redirect("aa_fleet_tool:commanders")

    created = FleetCommander.objects.get_or_create(
        character=char, defaults={"user": request.user}
    )[1]
    if created:
        # No automatic polling on registration — the FC starts tracking on demand.
        messages.success(
            request,
            _("%s registered as FC. Press “Fleet Start” when you form a fleet.")
            % char.character_name,
        )
    else:
        messages.info(request, _("%s is already registered.") % char.character_name)
    return redirect("aa_fleet_tool:commanders")


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
def start_fleet(request):
    """Activate tracking for one of the user's own FCs and check it immediately."""
    fc = get_object_or_404(
        FleetCommander, pk=request.POST.get("fc_pk"), user=request.user
    )
    fc.start()
    # force=True bypasses the ESI ETag so a fleet the FC never left is picked up
    # again immediately (otherwise a 304 would leave Active Fleets empty).
    check_fc_in_fleet.delay(fc.pk, force=True)
    return JsonResponse({"ok": True})


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@require_POST
def stop_fleet(request):
    """Deactivate tracking for one of the user's own FCs and drop its fleet."""
    fc = get_object_or_404(
        FleetCommander, pk=request.POST.get("fc_pk"), user=request.user
    )
    fc.stop()
    ActiveFleet.objects.filter(fc=fc).delete()
    return JsonResponse({"ok": True})


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@require_POST
def trigger_sync(request):
    """Force an immediate re-check of the user's active FCs."""
    for fc in FleetCommander.objects.filter(user=request.user, is_active=True):
        sync_fc.delay(fc.pk)
    return JsonResponse({"ok": True})
