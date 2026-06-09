from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("aa_fleet_tool", "0005_fleettoolconfiguration"),
    ]

    operations = [
        migrations.AddField(
            model_name="activefleet",
            name="name",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
    ]
