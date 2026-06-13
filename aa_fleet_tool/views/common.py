"""Shared view helpers."""

from django.apps import apps
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from allianceauth.services.hooks import get_extension_logger
from esi.exceptions import HTTPClientError, HTTPNotModified, HTTPServerError

from ..constants import WRITE_SCOPE
from ..models import ActiveFleet, Doctrine, FleetCommander, FleetLayout, MOTDTemplate
from ..providers import get_token

logger = get_extension_logger(__name__)


def nav_context(active: str) -> dict:
    """Counts + active flag for the shared navigation bar.

    Every page renders the same nav, so each page view merges this in.
    """
    return {
        "active_page": active,
        "nav_fleet_count": ActiveFleet.objects.count(),
        "nav_fc_count": FleetCommander.objects.count(),
        "nav_layout_count": FleetLayout.objects.count(),
        "nav_motd_count": MOTDTemplate.objects.count(),
    }


def esi_call(call):
    """Run an ESI operation callable and normalise the outcome.

    ``call`` is a zero-arg callable returning the (unexecuted) ESI operation, so
    we can run ``.result()`` inside the try/except. Returns ``(data, None)`` on
    success or ``(None, JsonResponse)`` with an error payload to return as-is.
    A 304 (not modified) is treated as success with ``data=None``.
    """
    try:
        return call().result(), None
    except HTTPNotModified:
        return None, None
    except (HTTPClientError, HTTPServerError) as exc:
        status = getattr(exc, "status_code", 502)
        logger.warning("ESI write failed (%s): %s", status, exc)
        return None, JsonResponse({"ok": False, "error": str(exc)}, status=status)


def fleet_write(request, fleet_pk):
    """Return (fleet, token) or (None, None) if not authorized or no write token."""
    fleet = get_object_or_404(ActiveFleet, pk=fleet_pk)
    if fleet.fc.user != request.user:
        return None, None
    token = get_token(fleet.fc.character.character_id, WRITE_SCOPE)
    if token is None:
        return None, None
    return fleet, token


def resolve_doctrine(doctrine_pk):
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
            doc = FittingsDoctrine.objects.prefetch_related("fittings__ship_type").get(
                pk=pk
            )
            ship_ids = {f.ship_type_type_id for f in doc.fittings.all()}
            # Fittings has no role_hint → all ships map to "any" (→ "other")
            ship_role_map = {sid: "any" for sid in ship_ids}
            return ship_ids, ship_role_map
        except Exception as exc:
            logger.warning("Fittings doctrine resolve failed: %s", exc)
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
