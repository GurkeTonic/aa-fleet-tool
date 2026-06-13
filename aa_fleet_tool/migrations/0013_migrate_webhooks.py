from django.db import migrations


def forwards(apps, schema_editor):
    """Move each FleetType's old webhook_url/role_mention into the new structure."""
    FleetType = apps.get_model("aa_fleet_tool", "FleetType")
    Webhook = apps.get_model("aa_fleet_tool", "Webhook")
    for ft in FleetType.objects.all():
        if ft.webhook_url:
            wh = Webhook.objects.create(name=ft.name, url=ft.webhook_url)
            ft.webhooks.add(wh)
        rm = (ft.role_mention or "").strip().lower()
        if "everyone" in rm:
            ft.mention = "everyone"
        elif "here" in rm:
            ft.mention = "here"
        ft.save(update_fields=["mention"])


class Migration(migrations.Migration):

    dependencies = [
        ('aa_fleet_tool', '0012_webhook_fleettype_mention_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
