# Changelog

## [0.1.0] - 2026-06-09

### Added

- Live fleet member table with ESI sync every 30 seconds
- Fleet composition counters: FC / WC / SC / Members
- Doctrine compliance tracking — highlights members flying off-doctrine ships
- MOTD template library with one-click "Load MOTD" injection via ESI
- Wing and squad management (create, rename, delete) via ESI write
- Member actions: invite, kick, move to wing/squad
- Fleet layout templates — save and apply wing/squad structures in one click
- Fleet type selection with URL persistence
- Free-move toggle
- Station / docked status column per member
- FAT link integration (aFAT)
- SRP link integration (AA-SRP)
- CCP ESI compliance: User-Agent, X-Compatibility-Date, Expires-based caching,
  Error-Limit monitoring and abort

### Fixed

- Active fleet not removed when FC leaves or fleet dissolves — ESI 404 response
  was silently discarded by the cache helper, leaving stale fleet entries in the
  database
