import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("eveonline", "0025_remove_evecharacter_last_updated_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="General",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False
                    ),
                ),
            ],
            options={
                "managed": False,
                "default_permissions": (),
                "permissions": [
                    ("view_fleet_tool", "Can access Fleet Tool"),
                    ("manage_doctrine", "Can manage fleet doctrines"),
                ],
            },
        ),
        migrations.CreateModel(
            name="FleetCommander",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False
                    ),
                ),
                (
                    "character",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="fleet_commander",
                        to="eveonline.evecharacter",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="fleet_commanders",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["character__character_name"]},
        ),
        migrations.CreateModel(
            name="ActiveFleet",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False
                    ),
                ),
                ("fleet_id", models.BigIntegerField()),
                ("motd", models.TextField(blank=True, default="")),
                ("is_free_move", models.BooleanField(default=False)),
                ("is_registered", models.BooleanField(default=False)),
                ("is_voice_enabled", models.BooleanField(default=False)),
                ("last_updated", models.DateTimeField(blank=True, null=True)),
                (
                    "fc",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="active_fleet",
                        to="aa_fleet_tool.fleetcommander",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="FleetWing",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False
                    ),
                ),
                ("wing_id", models.BigIntegerField()),
                ("name", models.CharField(default="", max_length=100)),
                (
                    "fleet",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="wings",
                        to="aa_fleet_tool.activefleet",
                    ),
                ),
            ],
            options={
                "ordering": ["wing_id"],
                "unique_together": {("fleet", "wing_id")},
            },
        ),
        migrations.CreateModel(
            name="FleetSquad",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False
                    ),
                ),
                ("squad_id", models.BigIntegerField()),
                ("name", models.CharField(default="", max_length=100)),
                (
                    "wing",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="squads",
                        to="aa_fleet_tool.fleetwing",
                    ),
                ),
            ],
            options={
                "ordering": ["squad_id"],
                "unique_together": {("wing", "squad_id")},
            },
        ),
        migrations.CreateModel(
            name="FleetMember",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False
                    ),
                ),
                ("character_id", models.IntegerField()),
                ("character_name", models.CharField(default="", max_length=100)),
                ("ship_type_id", models.IntegerField(default=0)),
                ("ship_name", models.CharField(default="", max_length=100)),
                ("solar_system_id", models.IntegerField(default=0)),
                ("system_name", models.CharField(default="", max_length=100)),
                ("role", models.CharField(default="squad_member", max_length=30)),
                ("role_name", models.CharField(default="", max_length=100)),
                ("wing_id", models.BigIntegerField(blank=True, null=True)),
                ("squad_id", models.BigIntegerField(blank=True, null=True)),
                ("join_time", models.DateTimeField(blank=True, null=True)),
                ("takes_fleet_warp", models.BooleanField(default=True)),
                (
                    "fleet",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="members",
                        to="aa_fleet_tool.activefleet",
                    ),
                ),
            ],
            options={
                "ordering": ["role", "character_name"],
                "unique_together": {("fleet", "character_id")},
            },
        ),
        migrations.CreateModel(
            name="Doctrine",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                ("description", models.TextField(blank=True, default="")),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="doctrines",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="DoctrineShip",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False
                    ),
                ),
                ("ship_type_id", models.IntegerField()),
                ("ship_name", models.CharField(max_length=100)),
                ("role_hint", models.CharField(default="any", max_length=20)),
                (
                    "doctrine",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ships",
                        to="aa_fleet_tool.doctrine",
                    ),
                ),
            ],
            options={
                "ordering": ["role_hint", "ship_name"],
                "unique_together": {("doctrine", "ship_type_id")},
            },
        ),
    ]
