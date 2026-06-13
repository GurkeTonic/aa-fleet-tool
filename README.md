# AA Fleet Tool<a name="aa-fleet-tool"></a>

A Fleet Commander tool for [Alliance Auth](https://gitlab.com/allianceauth/allianceauth) —
live member overview, fleet composition with a live graph, doctrine tracking, a MOTD
library, wing/squad management, FAT/SRP integration and a Discord fleet ping.

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
    - [Step 2 — Install the EVE SDE](#step-2--install-the-eve-sde)
    - [Step 3 — Configure Alliance Auth](#step-3--configure-alliance-auth)
    - [Step 4 — Migrate and load the SDE](#step-4--migrate-and-load-the-sde)
    - [Step 5 — Enable ESI scopes](#step-5--enable-esi-scopes)
    - [Step 6 — Register Fleet Commanders](#step-6--register-fleet-commanders)
    - [Step 7 — Discord Fleet Ping (optional)](#step-7--discord-fleet-ping-optional)
  - [Usage](#usage)
  - [Permissions](#permissions)
  - [ESI Scopes](#esi-scopes)
  - [Settings](#settings)
  - [Optional integrations](#optional-integrations)
  - [Contribute](#contribute)

<!-- mdformat-toc end -->

______________________________________________________________________

## Features<a name="features"></a>

- **On-demand tracking** — an FC presses *Fleet Start* to track their fleet and
  *Fleet Stop* (or it auto-stops when the fleet ends). Only active FCs hit ESI, so
  registering an FC does not cause permanent polling.
- **Live member table** with ESI sync every 30 seconds (docked status, fleet warp,
  wing/squad, join time).
- **Always-on fleet composition** — DPS / Logi / Booster / EWAR / Other, classified by
  EVE ship group (or by the selected doctrine), with a live **DPS/Logi graph**.
- **Doctrine tracking** — define doctrines (or use the `fittings` module) and highlight
  members flying off-doctrine ships.
- **MOTD library** — shared templates plus each FC's own private templates; one-click
  "Load MOTD" injection via ESI.
- **Wing & squad management** — create, rename, delete, and invite/kick/move members
  via ESI write.
- **Fleet layout templates** — save wing/squad structures and apply them in one click.
- **Discord Fleet Ping** — post a forming-up message (staging, doctrine, note, FAT/SRP
  links) to a Discord channel via webhook, with an optional `@here`/`@everyone` mention.
- **FAT link** ([aFAT](https://github.com/ppfeufer/allianceauth-afat)) and **SRP link**
  ([AA-SRP](https://github.com/ppfeufer/allianceauth-srp)) integration (optional).

## Installation<a name="installation"></a>

### Step 1 — Install the package<a name="step-1--install-the-package"></a>

```bash
pip install git+https://github.com/GurkeTonic/aa-fleet-tool
```

### Step 2 — Install the EVE SDE<a name="step-2--install-the-eve-sde"></a>

The plugin uses the local EVE Static Data Export for ship/system names and the
composition classification:

```bash
pip install django-eveonline-sde
```

### Step 3 — Configure Alliance Auth<a name="step-3--configure-alliance-auth"></a>

Add both apps to `INSTALLED_APPS` in your `myauth/settings/local.py`:

```python
INSTALLED_APPS += [
    "aa_fleet_tool",
    "eve_sde",
]
```

### Step 4 — Migrate and load the SDE<a name="step-4--migrate-and-load-the-sde"></a>

```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py esde_load_sde     # one-off, takes a few minutes
```

Restart your `allianceserver` (web + Celery worker + beat).

### Step 5 — Enable ESI scopes<a name="step-5--enable-esi-scopes"></a>

Enable these scopes in your Alliance Auth ESI application
(Developer Portal → your app → permissions):

| Scope | Purpose |
| --- | --- |
| `esi-fleets.read_fleet.v1` | Read fleet members, wings, squads, MOTD |
| `esi-fleets.write_fleet.v1` | MOTD updates, invite/kick/move, wing/squad management |

### Step 6 — Register Fleet Commanders<a name="step-6--register-fleet-commanders"></a>

Each FC registers their character with the **+ Add FC** button (the character must be
on their own Auth account and authenticate with both scopes above). Registering does
**not** start any polling — the FC presses **Fleet Start** when forming a fleet and
**Fleet Stop** afterwards (it also auto-stops when the fleet ends).

### Step 7 — Discord Fleet Ping (optional)<a name="step-7--discord-fleet-ping-optional"></a>

To enable the Fleet Ping button, configure these in the Django admin under *Fleet Tool*:

1. **Webhooks** — create a webhook entry (name + Discord webhook URL of the target
   channel).
2. **Fleet types** — create a fleet type, link one or more webhooks (dual-list) and
   pick the mention (`@here`, `@everyone` or none).
3. **Stagings** (optional) — a name + solar system the FC can attach to the ping.

## Usage<a name="usage"></a>

1. Open **Fleet Tool** in the menu → register your FC (**+ Add FC**) once.
2. Form a fleet in game, then press **Fleet Start**. Your fleet appears under
   *Active Fleets* with the live member table, composition and graph.
3. Manage wings/squads, load a MOTD, create FAT/SRP links, or send a **Fleet Ping**.
4. Press **Fleet Stop** when done (or it stops automatically).

## Permissions<a name="permissions"></a>

| Permission | Description |
| --- | --- |
| `aa_fleet_tool.view_fleet_tool` | Access the Fleet Tool, run fleet actions on your own fleet, manage your own private MOTD templates |
| `aa_fleet_tool.manage_doctrine` | Create/edit/delete doctrines, fleet layouts and **shared** MOTD templates |

## ESI Scopes<a name="esi-scopes"></a>

| Scope | Used for |
| --- | --- |
| `esi-fleets.read_fleet.v1` | Reading fleet state (members, wings, squads, MOTD) |
| `esi-fleets.write_fleet.v1` | Writing fleet state (MOTD, invite/kick/move, wing/squad CRUD) |

## Settings<a name="settings"></a>

Optional overrides for `myauth/settings/local.py` (defaults shown):

| Setting | Default | Purpose |
| --- | --- | --- |
| `FLEET_TOOL_APP_NAME` | `"Fleet Tool"` | Menu name |
| `FLEET_TOOL_MEMBER_SYNC_INTERVAL` | `30` | Member sync interval (seconds) |
| `FLEET_TOOL_FC_CHECK_INTERVAL` | `60` | FC fleet-status check interval (seconds) |
| `FLEET_TOOL_ACTIVATION_GRACE` | `600` | Auto-stop a started FC who never forms a fleet (seconds) |
| `FLEET_TOOL_SNAPSHOT_WINDOW` | `600` | Rolling window of composition snapshots for the graph (seconds) |

## Optional integrations<a name="optional-integrations"></a>

Detected automatically when installed and enabled in *Fleet Tool Configuration*:

- [`afat`](https://github.com/ppfeufer/allianceauth-afat) — FAT link button.
- [`aasrp`](https://github.com/ppfeufer/allianceauth-srp) — SRP link button.
- [`fittings`](https://gitlab.com/colcrunch/fittings) — use fittings doctrines in the
  doctrine dropdown.

## Contribute<a name="contribute"></a>

Issues and pull requests are welcome on
[GitHub](https://github.com/GurkeTonic/aa-fleet-tool).
