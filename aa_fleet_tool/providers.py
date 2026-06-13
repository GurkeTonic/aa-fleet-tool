"""ESI client provider.

A single, lazily-constructed django-esi client for this app. Construction does
no network I/O until the first ``.client`` access, so it is safe at module
level. The client handles caching, ETags, the floating-window rate limit, the
error limit, the User-Agent (incl. ``ESI_USER_CONTACT_EMAIL``) and the
compatibility date for us — none of that has to be built by hand.
"""

# Third Party
from esi.openapi_clients import ESIClientProvider

# AA Fleet Tool
from aa_fleet_tool import (
    __app_name_useragent__,
    __esi_compatibility_date__,
    __github_url__,
    __version__,
)

# Operations are filtered to keep the loaded spec (and memory) small.
_FLEET_OPERATIONS = [
    "GetCharactersCharacterIdFleet",
    "GetFleetsFleetId",
    "PutFleetsFleetId",
    "GetFleetsFleetIdMembers",
    "PostFleetsFleetIdMembers",
    "DeleteFleetsFleetIdMembersMemberId",
    "PutFleetsFleetIdMembersMemberId",
    "GetFleetsFleetIdWings",
    "PostFleetsFleetIdWings",
    "PutFleetsFleetIdWingsWingId",
    "DeleteFleetsFleetIdWingsWingId",
    "PostFleetsFleetIdWingsWingIdSquads",
    "PutFleetsFleetIdSquadsSquadId",
    "DeleteFleetsFleetIdSquadsSquadId",
    "PostUniverseNames",
]

esi = ESIClientProvider(
    compatibility_date=__esi_compatibility_date__,
    ua_appname=__app_name_useragent__,
    ua_version=__version__,
    ua_url=__github_url__,
    operations=_FLEET_OPERATIONS,
)


def get_token(character_id: int, scope: str):
    """Return a valid Token for the given character carrying ``scope``, or None."""
    # Imported lazily so importing this module does not pull in the app registry.
    from esi.models import Token

    return (
        Token.objects.filter(character_id=character_id)
        .require_valid()
        .filter(scopes__name=scope)
        .first()
    )
