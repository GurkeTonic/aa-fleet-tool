from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("aa_fleet_tool", "0004_motdtemplate"),
    ]

    operations = [
        migrations.CreateModel(
            name="FleetToolConfiguration",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("enable_fat_link", models.BooleanField(default=False, help_text="Show 'Create FAT Link' button in fleet detail (requires afat).")),
                ("enable_srp_link", models.BooleanField(default=False, help_text="Show 'Create SRP Link' button in fleet detail (requires aasrp).")),
                ("use_fittings_doctrines", models.BooleanField(default=False, help_text="Include doctrines from the fittings module in the doctrine dropdown (requires fittings).")),
            ],
            options={
                "verbose_name": "Fleet Tool Configuration",
                "verbose_name_plural": "Fleet Tool Configuration",
            },
        ),
    ]
