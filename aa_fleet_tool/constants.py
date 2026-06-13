"""
Constants
"""

# AA Fleet Tool
from aa_fleet_tool import __title__, __version__  # noqa: F401

# ESI scopes used by this app
READ_SCOPE = "esi-fleets.read_fleet.v1"
WRITE_SCOPE = "esi-fleets.write_fleet.v1"
FLEET_SCOPES = [READ_SCOPE, WRITE_SCOPE]

# Composition role buckets (display order)
COMP_ROLES = ["dps", "logi", "booster", "ewar", "other"]

# Doctrine-independent ship classification by EVE ship group (from the SDE).
# Anything combat-ish not listed here defaults to "dps"; non-combat → "other".
# Easy to tweak — e.g. move Recon groups (833/906) out of EWAR if preferred.
SHIP_GROUP_ROLE = {
    # Logistics
    832: "logi",  # Logistics (cruisers)
    1527: "logi",  # Logistics Frigate
    1538: "logi",  # Force Auxiliary
    # Boosters / command
    540: "booster",  # Command Ship
    1534: "booster",  # Command Destroyer
    # EWAR
    893: "ewar",  # Electronic Attack Ship
    833: "ewar",  # Force Recon Ship
    906: "ewar",  # Combat Recon Ship
    # Non-combat
    29: "other",  # Capsule
    31: "other",  # Shuttle
    28: "other",  # Industrial
    1202: "other",  # Blockade Runner
    380: "other",  # Deep Space Transport
}
