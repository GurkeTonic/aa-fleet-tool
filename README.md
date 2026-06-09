# AA Fleet Tool<a name="aa-fleet-tool"></a>

A Fleet Commander tool for [Alliance Auth](https://gitlab.com/allianceauth/allianceauth) —
live member overview, MOTD library, doctrine tracking, wing/squad management,
and FAT/SRP link integration.

![License](https://img.shields.io/badge/license-GPLv3-green)
![python](https://img.shields.io/badge/python-3.10+-informational)
![django](https://img.shields.io/badge/django-4.2+-informational)

> [!IMPORTANT]
>
> **This app requires Alliance Auth v5!**
>
> Please make sure to update your Alliance Auth instance **before** installing
> this module, otherwise an update to Alliance Auth will be pulled in unsupervised.

______________________________________________________________________

<!-- mdformat-toc start --slug=github --maxlevel=6 --minlevel=1 -->

- [AA Fleet Tool](#aa-fleet-tool)
  - [Features](#features)
  - [Installation](#installation)
    - [Step 1 — Install the package](#step-1--install-the-package)
    - [Step 2 — Install EVE SDE (if not already present)](#step-2--install-eve-sde-if-not-already-present)
    - [Step 3 — Configure Alliance Auth](#step-3--configure-alliance-auth)
    - [Step 4 — Load SDE data](#step-4--load-sde-data)
    - [Step 5 — Enable ESI scopes](#step-5--enable-esi-scopes)
    - [Step 6 — Register Fleet Commanders](#step-6--register-fleet-commanders)
  - [Permissions](#permissions)
  - [ESI Scopes](#esi-scopes)
  - [Contribute](#contribute)

<!-- mdformat-toc end -->

______________________________________________________________________

## Features<a name="features"></a>

- Live fleet member table (ESI sync every 30 seconds)
- Fleet composition counters: FC / WC / SC / Members
- Doctrine compliance tracking — highlights members flying off-doctrine ships
- MOTD template library with one-click "Load MOTD" injection via ESI
- Wing and squad management (create, rename, delete) directly via ESI write
- Member actions: invite, kick, move to wing/squad
- Fleet layout templates — save wing/squad structures and apply them in one click
- Fleet type selection with URL persistence across page loads
- Free-move toggle
- Station / docked status column for each member
- FAT link integration ([aFAT](https://github.com/ppfeufer/allianceauth-afat))
- SRP link integration ([AA-SRP](https://github.com/ppfeufer/allianceauth-srp))

## Installation<a name="installation"></a>

### Step 1 — Install the package<a name="step-1--install-the-package"></a>

```bash
pip install git+https://github.com/GurkeTonic/aa-fleet-tool
```

### Step 2 — Install EVE SDE (if not already present)<a name="step-2--install-eve-sde-if-not-already-present"></a>

```bash
pip install django-eveonline-sde
```

### Step 3 — Configure Alliance Auth<a name="step-3--configure-alliance-auth"></a>

Add both apps to `INSTALLED_APPS` in `settings/local.py`:

```python
INSTALLED_APPS += [
    "aa_fleet_tool",
    "eve_sde",
]
```

Run migrations and collect static files:

```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

### Step 4 — Load SDE data<a name="step-4--load-sde-data"></a>

```bash
python manage.py import_sde
```

Restart your allianceserver.

### Step 5 — Enable ESI scopes<a name="step-5--enable-esi-scopes"></a>

The following ESI scopes must be enabled in your Alliance Auth ESI application
(Developer Portal → your app → permissions):

| Scope | Purpose |
| --- | --- |
| `esi-fleets.read_fleet.v1` | Read fleet members, wings, squads, MOTD |
| `esi-fleets.write_fleet.v1` | MOTD updates, invite/kick/move, wing/squad management |

### Step 6 — Register Fleet Commanders<a name="step-6--register-fleet-commanders"></a>

Fleet Commanders must be registered via the **+ Add FC** button in the module
(or through the Django admin panel). Each FC character must have authenticated
with both ESI scopes above so a valid token is stored.

The module will then check every 60 seconds whether each registered FC is in a
fleet and update the member list every 30 seconds.

## Permissions<a name="permissions"></a>

| Permission | Description |
| --- | --- |
| `aa_fleet_tool.view_fleet_tool` | Access to the Fleet Tool |
| `aa_fleet_tool.manage_doctrine` | Create, edit, and delete doctrines |

## ESI Scopes<a name="esi-scopes"></a>

| Scope | Used for |
| --- | --- |
| `esi-fleets.read_fleet.v1` | Reading fleet state (members, wings, squads, MOTD) |
| `esi-fleets.write_fleet.v1` | Writing fleet state (MOTD, invite/kick/move, wing/squad CRUD) |

## Contribute<a name="contribute"></a>

Issues and pull requests are welcome on
[GitHub](https://github.com/GurkeTonic/aa-fleet-tool).
