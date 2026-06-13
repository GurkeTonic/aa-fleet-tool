"""Doctrines page, ship search and doctrine/ship CRUD."""

from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from ..models import Doctrine, DoctrineShip
from .common import nav_context


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
def doctrines(request):
    """Doctrines management page."""
    context = {
        "doctrines": Doctrine.objects.prefetch_related("ships"),
        **nav_context("doctrines"),
    }
    return render(request, "aa_fleet_tool/doctrines.html", context)


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
def ship_search(request):
    q = request.GET.get("q", "").strip()
    if len(q) < 2:
        return JsonResponse({"results": []})
    from eve_sde.models import ItemType

    ships = ItemType.objects.filter(
        name__icontains=q, group__category__pk=6, published=True
    ).order_by("name")[:12]
    return JsonResponse({"results": [{"type_id": s.pk, "name": s.name} for s in ships]})


@login_required
@permission_required("aa_fleet_tool.manage_doctrine")
@require_POST
def create_doctrine(request):
    name = request.POST.get("name", "").strip()
    if not name:
        return JsonResponse({"ok": False, "error": _("Name required")}, status=400)
    doc = Doctrine.objects.create(
        name=name,
        description=request.POST.get("description", ""),
        created_by=request.user,
    )
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
        return JsonResponse(
            {"ok": False, "error": _("Ship Type ID and Ship Name are required.")},
            status=400,
        )
    ship, created = DoctrineShip.objects.get_or_create(
        doctrine=doctrine,
        ship_type_id=ship_type_id,
        defaults={"ship_name": ship_name, "role_hint": role_hint},
    )
    return JsonResponse(
        {"ok": True, "pk": ship.pk, "ship_name": ship.ship_name, "created": created}
    )


@login_required
@permission_required("aa_fleet_tool.manage_doctrine")
@require_POST
def remove_doctrine_ship(request, pk):
    get_object_or_404(DoctrineShip, pk=pk).delete()
    return JsonResponse({"ok": True})
