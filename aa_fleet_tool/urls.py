from django.urls import path

from . import views

app_name = "aa_fleet_tool"

urlpatterns = [
    # Pages
    path("", views.index, name="index"),
    path("commanders/", views.commanders, name="commanders"),
    path("doctrines/", views.doctrines, name="doctrines"),
    path("layouts/", views.layouts, name="layouts"),
    path("motd/", views.motd, name="motd"),

    # Fleet Commander management
    path("add-fc/", views.add_fc, name="add_fc"),
    path("remove-fc/", views.remove_fc, name="remove_fc"),
    path("fleet-start/", views.start_fleet, name="start_fleet"),
    path("fleet-stop/", views.stop_fleet, name="stop_fleet"),
    path("sync/", views.trigger_sync, name="trigger_sync"),

    # Live fleet management
    path("fleet/<int:fleet_pk>/name/", views.set_fleet_name, name="set_fleet_name"),
    path("fleet/<int:fleet_pk>/motd/", views.set_motd, name="set_motd"),
    path("fleet/<int:fleet_pk>/free-move/", views.set_free_move, name="set_free_move"),
    path("fleet/<int:fleet_pk>/kick/", views.kick_member, name="kick_member"),
    path("fleet/<int:fleet_pk>/move/", views.move_member, name="move_member"),
    path("fleet/<int:fleet_pk>/invite/", views.invite_member, name="invite_member"),
    path("fleet/<int:fleet_pk>/wing/create/", views.create_wing, name="create_wing"),
    path("fleet/<int:fleet_pk>/wing/<int:wing_id>/rename/", views.rename_wing, name="rename_wing"),
    path("fleet/<int:fleet_pk>/wing/<int:wing_id>/delete/", views.delete_wing, name="delete_wing"),
    path("fleet/<int:fleet_pk>/wing/<int:wing_id>/squad/create/", views.create_squad, name="create_squad"),
    path("fleet/<int:fleet_pk>/squad/<int:squad_id>/rename/", views.rename_squad, name="rename_squad"),
    path("fleet/<int:fleet_pk>/squad/<int:squad_id>/delete/", views.delete_squad, name="delete_squad"),
    path("fleet/<int:fleet_pk>/members.json", views.fleet_members_json, name="fleet_members_json"),

    path("ship-search/", views.ship_search, name="ship_search"),

    # Fleet Layouts
    path("layout/create/", views.create_layout, name="create_layout"),
    path("layout/<int:pk>/delete/", views.delete_layout, name="delete_layout"),
    path("layout/<int:pk>/wing/add/", views.add_layout_wing, name="add_layout_wing"),
    path("layout/wing/<int:pk>/rename/", views.rename_layout_wing, name="rename_layout_wing"),
    path("layout/wing/<int:pk>/delete/", views.delete_layout_wing, name="delete_layout_wing"),
    path("layout/wing/<int:pk>/squad/add/", views.add_layout_squad, name="add_layout_squad"),
    path("layout/squad/<int:pk>/rename/", views.rename_layout_squad, name="rename_layout_squad"),
    path("layout/squad/<int:pk>/delete/", views.delete_layout_squad, name="delete_layout_squad"),
    path("fleet/<int:fleet_pk>/apply-layout/<int:layout_pk>/", views.apply_layout, name="apply_layout"),

    # MOTD Templates
    path("motd-template/create/", views.create_motd_template, name="create_motd_template"),
    path("motd-template/<int:pk>/update/", views.update_motd_template, name="update_motd_template"),
    path("motd-template/<int:pk>/delete/", views.delete_motd_template, name="delete_motd_template"),

    # Integrations
    path("fleet/<int:fleet_pk>/fat-link/create/", views.create_fat_link, name="create_fat_link"),
    path("fleet/<int:fleet_pk>/srp-link/create/", views.create_srp_link, name="create_srp_link"),
    path("fleet/<int:fleet_pk>/ping/", views.send_fleet_ping, name="send_fleet_ping"),

    # Doctrine
    path("doctrine/create/", views.create_doctrine, name="create_doctrine"),
    path("doctrine/<int:pk>/delete/", views.delete_doctrine, name="delete_doctrine"),
    path("doctrine/<int:pk>/ship/add/", views.add_doctrine_ship, name="add_doctrine_ship"),
    path("doctrine/ship/<int:pk>/remove/", views.remove_doctrine_ship, name="remove_doctrine_ship"),
]
