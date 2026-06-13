"""Fleet Ping — post a forming-up message to Discord via the FleetType webhook."""

from django.apps import apps
from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from allianceauth.services.hooks import get_extension_logger

from ..discord import post_webhook
from ..models import ActiveFleet, FleetType, Staging

logger = get_extension_logger(__name__)


def _site_url() -> str:
    return getattr(settings, "SITE_URL", "").rstrip("/")


def _clickable_fat_url(fleet_hash: str, site: str) -> str:
    """Register URL for a *clickable* FAT link, else "" (ESI FATs auto-register).

    Reads afat's FatLink read-only via its public ORM (intended integration).
    """
    if not fleet_hash or not site or not apps.is_installed("afat"):
        return ""
    try:
        from afat.models import FatLink
        fl = FatLink.objects.filter(hash=fleet_hash).first()
        if fl and not fl.is_esilink:
            return f"{site}/afat/fatlinks/{fleet_hash}/register/"
    except Exception as exc:
        logger.warning("FAT link lookup for ping failed: %s", exc)
    return ""


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@require_POST
def send_fleet_ping(request, fleet_pk):
    fleet = get_object_or_404(ActiveFleet, pk=fleet_pk)
    if fleet.fc.user != request.user:
        return JsonResponse({"ok": False, "error": _("Not authorized")}, status=403)

    fleet_type = FleetType.objects.filter(
        pk=request.POST.get("fleet_type_pk"), is_enabled=True
    ).first()
    if not fleet_type:
        return JsonResponse({"ok": False, "error": _("Please select a fleet type.")}, status=400)
    webhooks = list(fleet_type.webhooks.filter(is_enabled=True))
    if not webhooks:
        return JsonResponse(
            {"ok": False, "error": _("This fleet type has no Discord webhook configured.")},
            status=400,
        )

    staging = Staging.objects.filter(pk=request.POST.get("staging_pk"), is_enabled=True).first()
    note = request.POST.get("note", "").strip()

    fc_name = fleet.fc.character.character_name
    site = _site_url()

    fields = [
        {"name": _("FC"), "value": fc_name, "inline": True},
        {"name": _("Staging"), "value": staging.system if staging else "—", "inline": True},
        {"name": _("Fleet Type"), "value": fleet_type.name, "inline": True},
        {"name": _("Doctrine"), "value": "Read MOTD", "inline": True},
    ]
    # FAT link only for clickable FATs — ESI FATs auto-register, nothing to share.
    fat_url = _clickable_fat_url(fleet.fat_link_hash, site)
    if fat_url:
        fields.append({"name": _("FAT Link"), "value": fat_url, "inline": False})
    if fleet.srp_link_code and site:
        fields.append({
            "name": _("SRP Link"),
            "value": f"{site}/srp/srp-link/{fleet.srp_link_code}/request-srp/",
            "inline": False,
        })
    if note:
        fields.append({"name": _("Note"), "value": note, "inline": False})

    embed = {
        "title": fleet.name or fleet_type.name,
        "description": _("Fleet forming up — join now!"),
        "color": 0x3FA9F5,
        "fields": fields,
    }
    headline = _("%(type)s forming up!") % {"type": fleet_type.name}
    mention = {"here": "@here", "everyone": "@everyone"}.get(fleet_type.mention, "")
    content = f"{mention} {headline}".strip()

    # Post to every linked webhook; succeed if at least one goes through.
    any_ok, last_err = False, ""
    for wh in webhooks:
        ok, err = post_webhook(wh.url, content=content, embed=embed)
        any_ok = any_ok or ok
        if not ok:
            last_err = err
    if any_ok:
        return JsonResponse({"ok": True})
    return JsonResponse({"ok": False, "error": last_err}, status=502)
