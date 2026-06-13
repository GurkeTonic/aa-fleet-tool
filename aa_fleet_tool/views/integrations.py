"""Optional integrations: aFAT and AA-SRP link creation."""

from django.apps import apps
from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from allianceauth.services.hooks import get_extension_logger

from ..models import ActiveFleet

logger = get_extension_logger(__name__)


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

        from afat.models import Duration, FatLink

        from allianceauth.eveonline.models import EveCharacter

        hash_val = secrets.token_urlsafe(30)[:30]

        # afat stores fleet_type as a plain string — pass our FleetType name directly.
        fleet_type_name = request.POST.get("fleet_type_name", "").strip()

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
            fleet.fat_link_hash = hash_val
            fleet.save(update_fields=["fat_link_hash"])
            details_url = f"/afat/fatlinks/{hash_val}/details/"
            return JsonResponse(
                {
                    "ok": True,
                    "hash": hash_val,
                    "link_type": "esi",
                    "details_url": details_url,
                }
            )
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
            fleet.fat_link_hash = hash_val
            fleet.save(update_fields=["fat_link_hash"])
            register_url = f"/afat/fatlinks/{hash_val}/register/"
            return JsonResponse(
                {
                    "ok": True,
                    "hash": hash_val,
                    "link_type": "clickable",
                    "register_url": register_url,
                }
            )

    except Exception as exc:
        logger.exception("FAT link creation failed: %s", exc)
        return JsonResponse({"ok": False, "error": str(exc)}, status=500)


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@require_POST
def create_srp_link(request, fleet_pk):
    if not apps.is_installed("aasrp"):
        return JsonResponse(
            {"ok": False, "error": "aasrp is not installed"}, status=400
        )

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
        from aasrp.models import FleetType as AasrpFleetType
        from aasrp.models import SrpLink

        fleet_type_name = request.POST.get("fleet_type_name", "").strip()
        fleet_type = None
        if fleet_type_name:
            fleet_type = AasrpFleetType.objects.filter(
                name__iexact=fleet_type_name
            ).first()
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

        fleet.srp_link_code = srp_link.srp_code
        fleet.save(update_fields=["srp_link_code"])

        request_url = f"/srp/srp-link/{srp_link.srp_code}/request-srp/"
        return JsonResponse(
            {"ok": True, "srp_code": srp_link.srp_code, "request_url": request_url}
        )

    except Exception as exc:
        logger.exception("SRP link creation failed: %s", exc)
        return JsonResponse({"ok": False, "error": str(exc)}, status=500)
