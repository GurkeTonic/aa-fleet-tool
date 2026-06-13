# Changelog

All notable changes to this project are documented here
([Keep a Changelog](https://keepachangelog.com/), [SemVer](https://semver.org/)).

## [Unreleased]

## [0.3.0] - 2026-06-13

### Added

- A second composition graph next to the first, showing only the fleet
  members in the FC's system (undocked).

## [0.2.6] - 2026-06-13

### Fixed

- Fix an unreliable test (no functional change).

## [0.2.5] - 2026-06-13

### Fixed

- Server error when applying a fleet layout to an active fleet.

## [0.2.4] - 2026-06-13

### Changed

- Documentation cleanup.

## [0.2.3] - 2026-06-13

### Fixed

- Fix an unreliable test (no functional change).

## [0.2.2] - 2026-06-13

### Fixed

- Fix the CI build on newer Python versions.

## [0.2.1] - 2026-06-13

### Fixed

- Restore a green CI pipeline and apply consistent code formatting.

## [0.2.0] - 2026-06-13

### Added

- On-demand tracking: FCs start and stop tracking per fleet; only active fleets use ESI.
- Always-on fleet composition (DPS / Logi / Booster / EWAR / Other) with a live graph.
- Discord Fleet Ping: a form-up message with optional `@here`/`@everyone`, staging,
  note and FAT/SRP links.
- Private MOTD templates per FC, alongside the shared library.

### Changed

- ESI now uses the django-esi client (caching, rate limits); ship and system names
  come from the local SDE, reducing ESI calls.
- Tabs split into real sub-pages.
- Fleet types are managed in the plugin and drive FAT/SRP categories and the ping.
- Add FC requires the character to belong to the user.
- Full translation support, including German.

### Fixed

- Active fleet and members no longer stay empty after a stop and restart.
- Crash on empty Commanders/Members tables.

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
