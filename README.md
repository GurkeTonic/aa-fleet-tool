# AA Fleet Tool

Fleet Commander tool for Alliance Auth — live member overview, MOTD library, doctrine tracking, FAT & SRP link integration.

## Features

- Live fleet member overview (updated every 30 seconds via ESI)
- MOTD template library with doctrine support
- Fleet composition overview (DPS / Logi / Support)
- FAT link integration (afat)
- SRP link integration (aasrp)
- Fleet type selection with URL persistence
- Docked status display for fleet members

## Installation

```bash
pip install aa-fleet-tool
```

Add `aa_fleet_tool` to `INSTALLED_APPS` in your Alliance Auth settings and run migrations:

```bash
python manage.py migrate aa_fleet_tool
python manage.py collectstatic --noinput
```

## Permissions

| Permission        | Description                       |
|-------------------|-----------------------------------|
| `view_fleet_tool` | Access to the Fleet Tool          |

## Credits

Built on [Alliance Auth](https://gitlab.com/allianceauth/allianceauth).
