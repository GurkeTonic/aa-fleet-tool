# Changelog

All notable changes to this project are documented here
([Keep a Changelog](https://keepachangelog.com/), [SemVer](https://semver.org/)).

## [Unreleased]

## [0.2.2] - 2026-06-13

### Fixed

- Pin the pre-commit CI job to Python 3.13. Resolving the interpreter from
  `pyproject.toml` pulled in Python 3.14, where `pyupgrade` crashes
  (`tokenize.cookie_re` is now a bytes pattern).

## [0.2.1] - 2026-06-13

### Fixed

- CI is green again: align flake8 to black's line length, give isort the
  `black` profile (no more isort/black conflict), and stop pylint failing on
  `import-error` in the dependency-less CI environment. Applied the formatters
  across the code base and removed unused imports/variables.

## [0.2.0] - 2026-06-13

### Added

- **On-demand fleet tracking** — FCs press **Fleet Start** / **Fleet Stop** instead
  of being polled around the clock; tracking auto-stops when the fleet ends or after
  a grace period. Only active FCs hit ESI. Setting `FLEET_TOOL_ACTIVATION_GRACE`.
- **Always-on fleet composition** (DPS / Logi / Booster / EWAR / Other), enlarged and
  readable, with a live **DPS/Logi graph** (Chart.js) fed by per-tick snapshots
  (rolling window, `FLEET_TOOL_SNAPSHOT_WINDOW`). Ships are classified by their EVE
  ship group from the SDE; a selected doctrine fully overrides the classification.
- **Fleet Ping to Discord** — post a forming-up message via webhook(s) with an
  optional `@here`/`@everyone` mention, staging and free-text note; FAT/SRP links are
  included automatically. Preview-and-confirm flow. New admin models `Webhook`,
  `FleetType` and `Staging`.
- **Private MOTD templates** — each FC can keep their own private MOTD templates
  alongside the shared library (two-column MOTD page).

### Changed

- ESI now goes through the **`django-esi`** client (caching, ETags, rate/error limits,
  User-Agent, compatibility date) instead of raw `requests`.
- Ship and solar-system names are resolved from the local **SDE**; only character
  names still hit ESI — fewer ESI calls per sync.
- Periodic tasks use `QueueOnce` and `autoretry`; 304 Not-Modified is handled.
- Restructured the single-page tabs into **real sub-pages** (`/`, `/commanders/`,
  `/doctrines/`, `/layouts/`, `/motd/`); `views.py` → a `views/` package; `index.html`
  → a shared `base.html` plus one template + JS per page.
- The fleet-detail **Fleet Type** selector is driven by the plugin's own `FleetType`
  (categorises FAT/SRP links by name and is the Fleet Ping target).
- `Add FC` now requires the character to belong to the user (`CharacterOwnership`).
- Full **i18n** (views + templates) with a German translation; AA extension logger
  throughout; menu order set to `9999`.

### Fixed

- Active fleet and member list no longer stay empty after stopping and restarting the
  same fleet — an ESI 304 (ETag) prevented rebuilding the cascade-deleted rows; Fleet
  Start / Sync now force a cache-bypassing fetch and both self-heal on a 304.
- DataTables "Requested unknown parameter" crash on empty Commanders/Members tables.

## [0.1.0] - 2026-06-09

### Added

- Live fleet member table with ESI sync every 30 seconds
- Fleet composition counters: FC / WC / SC / Members
- Doctrine compliance tracking — highlights members flying off-doctrine ships
- MOTD template library with one-click "Load MOTD" injection via ESI
- Wing and squad management (create, rename, delete) via ESI write
- Member actions: invite, kick, move to wing/squad
- Fleet layout templates — save and apply wing/squad structures in one click
- Free-move toggle and station / docked status per member
- FAT link integration (aFAT) and SRP link integration (AA-SRP)
