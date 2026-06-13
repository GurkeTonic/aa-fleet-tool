"""MOTD Library page and MOTD template CRUD (public shared + private per-user)."""

from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from ..models import MOTDTemplate
from .common import nav_context

MANAGE_PERM = "aa_fleet_tool.manage_doctrine"


def _can_edit(user, tpl) -> bool:
    """Public templates require manage_doctrine; private ones belong to their owner."""
    if tpl.is_public:
        return user.has_perm(MANAGE_PERM)
    return tpl.created_by_id == user.id


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
def motd(request):
    """MOTD library: shared (public) templates and the user's own private ones."""
    public = MOTDTemplate.objects.filter(is_public=True)
    mine = MOTDTemplate.objects.filter(is_public=False, created_by=request.user)
    context = {
        "public_templates": public,
        "my_templates": mine,
        # Data for the edit modal (only templates the user may see/edit).
        "motd_tpl_data": list((public | mine).values("pk", "name", "text")),
        "can_manage_public": request.user.has_perm(MANAGE_PERM),
        **nav_context("motd"),
    }
    return render(request, "aa_fleet_tool/motd.html", context)


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@require_POST
def create_motd_template(request):
    name = request.POST.get("name", "").strip()
    text = request.POST.get("text", "").strip()
    if not name:
        return JsonResponse({"ok": False, "error": _("Name required")}, status=400)
    is_public = request.POST.get("is_public") == "true"
    if is_public and not request.user.has_perm(MANAGE_PERM):
        return JsonResponse({"ok": False, "error": _("Not authorized")}, status=403)
    tpl = MOTDTemplate.objects.create(
        name=name, text=text, created_by=request.user, is_public=is_public
    )
    return JsonResponse({"ok": True, "pk": tpl.pk, "name": tpl.name})


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@require_POST
def update_motd_template(request, pk):
    tpl = get_object_or_404(MOTDTemplate, pk=pk)
    if not _can_edit(request.user, tpl):
        return JsonResponse({"ok": False, "error": _("Not authorized")}, status=403)
    name = request.POST.get("name", "").strip()
    if not name:
        return JsonResponse({"ok": False, "error": _("Name required")}, status=400)
    tpl.name = name
    tpl.text = request.POST.get("text", "")
    tpl.save(update_fields=["name", "text"])
    return JsonResponse({"ok": True})


@login_required
@permission_required("aa_fleet_tool.view_fleet_tool")
@require_POST
def delete_motd_template(request, pk):
    tpl = get_object_or_404(MOTDTemplate, pk=pk)
    if not _can_edit(request.user, tpl):
        return JsonResponse({"ok": False, "error": _("Not authorized")}, status=403)
    tpl.delete()
    return JsonResponse({"ok": True})
