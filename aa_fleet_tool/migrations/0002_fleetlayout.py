import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("aa_fleet_tool", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FleetLayout",
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
                        related_name="fleet_layouts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="FleetLayoutWing",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False
                    ),
                ),
                ("position", models.PositiveSmallIntegerField()),
                ("name", models.CharField(max_length=100)),
                (
                    "layout",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="wings",
                        to="aa_fleet_tool.fleetlayout",
                    ),
                ),
            ],
            options={
                "ordering": ["position"],
                "unique_together": {("layout", "position")},
            },
        ),
        migrations.CreateModel(
            name="FleetLayoutSquad",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False
                    ),
                ),
                ("position", models.PositiveSmallIntegerField()),
                ("name", models.CharField(max_length=100)),
                (
                    "wing",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="squads",
                        to="aa_fleet_tool.fleetlayoutwing",
                    ),
                ),
            ],
            options={
                "ordering": ["position"],
                "unique_together": {("wing", "position")},
            },
        ),
    ]
