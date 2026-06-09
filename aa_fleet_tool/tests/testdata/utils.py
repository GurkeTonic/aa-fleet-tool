"""Test data utilities"""

# Standard Library
import datetime as dt

# Django
from django.contrib.auth.models import User

# Alliance Auth
from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCharacter
from allianceauth.tests.auth_utils import AuthUtils
from esi.models import Scope, Token


def _store_as_token(token: dict, user: object) -> Token:
    obj = Token.objects.create(
        access_token=token["access_token"],
        refresh_token=token["refresh_token"],
        user=user,
        character_id=token["CharacterID"],
        character_name=token["CharacterName"],
        token_type=token["TokenType"],
        character_owner_hash=token["CharacterOwnerHash"],
    )
    for scope_name in token["Scopes"].split(" "):
        scope, _ = Scope.objects.get_or_create(name=scope_name)
        obj.scopes.add(scope)
    return obj


def add_new_token(
    user: User,
    character: EveCharacter,
    scopes: list[str] | None = None,
) -> Token:
    if scopes is None:
        scopes = ["publicData"]
    timestamp_dt = dt.datetime.utcnow()
    token = {
        "access_token": "access_token",
        "token_type": "Bearer",
        "expires_in": 1200,
        "refresh_token": "refresh_token",
        "timestamp": int(timestamp_dt.timestamp()),
        "CharacterID": character.character_id,
        "CharacterName": character.character_name,
        "ExpiresOn": (timestamp_dt + dt.timedelta(seconds=1200)).isoformat(),
        "Scopes": " ".join(scopes),
        "TokenType": "Character",
        "CharacterOwnerHash": "testhash",
        "IntellectualProperty": "EVE",
    }
    return _store_as_token(token, user)


def add_character_to_user(
    user: User,
    character: EveCharacter,
    is_main: bool = False,
    scopes: list[str] | None = None,
) -> CharacterOwnership:
    if not scopes:
        scopes = ["publicData"]
    add_new_token(user, character, scopes)
    if is_main:
        user.profile.main_character = character
        user.profile.save()
        user.save()
    return CharacterOwnership.objects.get(user=user, character=character)


def create_user_from_evecharacter(
    character_id: int,
    permissions: list[str] | None = None,
    scopes: list[str] | None = None,
) -> tuple[User, CharacterOwnership]:
    auth_character = EveCharacter.objects.get(character_id=character_id)
    user = AuthUtils.create_user(auth_character.character_name.replace(" ", "_"))
    character_ownership = add_character_to_user(
        user, auth_character, is_main=True, scopes=scopes
    )
    if permissions:
        for permission_name in permissions:
            user = AuthUtils.add_permission_to_user_by_name(permission_name, user)
    return user, character_ownership
