from django.apps import apps
from django.contrib import admin

from .models import ActiveFleet, Doctrine, DoctrineShip, FleetCommander, FleetMember, FleetWing, FleetSquad, FleetToolConfiguration


@admin.register(FleetCommander)
class FleetCommanderAdmin(admin.ModelAdmin):
    list_display = ("character", "user")
    search_fields = ("character__character_name", "user__username")


class FleetMemberInline(admin.TabularInline):
    model = FleetMember
    extra = 0
    readonly_fields = ("character_name", "ship_name", "system_name", "role", "join_time")


@admin.register(ActiveFleet)
class ActiveFleetAdmin(admin.ModelAdmin):
    list_display = ("fc", "fleet_id", "member_count", "is_free_move", "last_updated")
    readonly_fields = ("fleet_id", "last_updated")
    inlines = [FleetMemberInline]


class DoctrineShipInline(admin.TabularInline):
    model = DoctrineShip
    extra = 1


@admin.register(Doctrine)
class DoctrineAdmin(admin.ModelAdmin):
    list_display = ("name", "created_by")
    search_fields = ("name",)
    inlines = [DoctrineShipInline]


@admin.register(FleetToolConfiguration)
class FleetToolConfigurationAdmin(admin.ModelAdmin):
    def get_fields(self, request, obj=None):
        fields = []
        if apps.is_installed("afat"):
            fields.append("enable_fat_link")
        if apps.is_installed("aasrp"):
            fields.append("enable_srp_link")
        if apps.is_installed("fittings"):
            fields.append("use_fittings_doctrines")
        return fields or ["enable_fat_link"]

    def has_add_permission(self, request):
        return not FleetToolConfiguration.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
