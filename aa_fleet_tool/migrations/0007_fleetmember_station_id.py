from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("aa_fleet_tool", "0006_activefleet_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="fleetmember",
            name="station_id",
            field=models.BigIntegerField(blank=True, null=True),
        ),
    ]
