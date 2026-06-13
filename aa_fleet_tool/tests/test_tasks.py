"""Tests for the ESI sync tasks (ESI client fully mocked — no network)."""

# Standard Library
from types import SimpleNamespace
from unittest.mock import Mock, patch

# Alliance Auth (External Libs)
from esi.exceptions import HTTPClientError

# AA Fleet Tool
from aa_fleet_tool import tasks
from aa_fleet_tool.models import ActiveFleet, FleetCommander, FleetMember
from aa_fleet_tool.tests import FleetToolTestCase


def _fleet_info(fleet_id=42):
    return SimpleNamespace(
        fleet_id=fleet_id, fleet_boss_id=1001, role="fleet_commander",
        squad_id=None, wing_id=None,
    )


def _fleet_detail():
    return SimpleNamespace(
        motd="Form up", is_free_move=True, is_registered=False, is_voice_enabled=False,
    )


def _member(character_id=1001, ship_type_id=587, system_id=30000142):
    return SimpleNamespace(
        character_id=character_id, ship_type_id=ship_type_id, solar_system_id=system_id,
        role="fleet_commander", role_name="", wing_id=None, squad_id=None,
        join_time=None, takes_fleet_warp=True, station_id=None,
    )


class TestCheckFcInFleet(FleetToolTestCase):
    """check_fc_in_fleet creates/clears the ActiveFleet based on ESI."""

    def setUp(self):
        self.fc = FleetCommander.objects.create(user=self.user, character=self.user_character.character)

    @patch.object(tasks, "update_fleet_members")
    @patch.object(tasks, "get_token")
    @patch.object(tasks, "esi")
    def test_creates_active_fleet(self, mock_esi, mock_get_token, mock_update):
        mock_get_token.return_value = Mock()
        fleets = mock_esi.client.Fleets
        fleets.GetCharactersCharacterIdFleet.return_value.result.return_value = _fleet_info(42)
        fleets.GetFleetsFleetId.return_value.result.return_value = _fleet_detail()

        tasks.check_fc_in_fleet(self.fc.pk)

        af = ActiveFleet.objects.get(fc=self.fc)
        self.assertEqual(af.fleet_id, 42)
        self.assertEqual(af.motd, "Form up")
        self.assertTrue(af.is_free_move)
        mock_update.delay.assert_called_once_with(self.fc.pk, force=False)

    @patch.object(tasks, "get_token")
    @patch.object(tasks, "esi")
    def test_clears_active_fleet_on_404(self, mock_esi, mock_get_token):
        mock_get_token.return_value = Mock()
        ActiveFleet.objects.create(fc=self.fc, fleet_id=99)
        fleets = mock_esi.client.Fleets
        fleets.GetCharactersCharacterIdFleet.return_value.result.side_effect = (
            HTTPClientError(status_code=404, headers={}, data=None)
        )

        tasks.check_fc_in_fleet(self.fc.pk)

        self.assertFalse(ActiveFleet.objects.filter(fc=self.fc).exists())

    @patch.object(tasks, "get_token")
    @patch.object(tasks, "esi")
    def test_no_token_is_noop(self, mock_esi, mock_get_token):
        mock_get_token.return_value = None
        tasks.check_fc_in_fleet(self.fc.pk)
        self.assertFalse(ActiveFleet.objects.filter(fc=self.fc).exists())
        mock_esi.client.Fleets.GetCharactersCharacterIdFleet.assert_not_called()


class TestActivationGating(FleetToolTestCase):
    """Only active FCs are polled; fleets auto-stop when they end."""

    def setUp(self):
        self.fc = FleetCommander.objects.create(
            user=self.user, character=self.user_character.character
        )

    @patch.object(tasks.check_fc_in_fleet, "delay")
    def test_only_active_fcs_are_polled(self, mock_delay):
        # Inactive FC → not polled
        tasks.check_all_fc_status()
        mock_delay.assert_not_called()
        # Active FC → polled
        self.fc.start()
        tasks.check_all_fc_status()
        mock_delay.assert_called_once_with(self.fc.pk)

    @patch.object(tasks, "get_token")
    @patch.object(tasks, "esi")
    def test_auto_stop_when_fleet_ends(self, mock_esi, mock_get_token):
        from esi.exceptions import HTTPClientError

        mock_get_token.return_value = Mock()
        self.fc.start()
        ActiveFleet.objects.create(fc=self.fc, fleet_id=7)  # a fleet was running
        mock_esi.client.Fleets.GetCharactersCharacterIdFleet.return_value.result.side_effect = (
            HTTPClientError(status_code=404, headers={}, data=None)
        )

        tasks.check_fc_in_fleet(self.fc.pk)

        self.fc.refresh_from_db()
        self.assertFalse(self.fc.is_active)
        self.assertFalse(ActiveFleet.objects.filter(fc=self.fc).exists())

    @patch.object(tasks, "update_fleet_members")
    @patch.object(tasks, "get_token")
    @patch.object(tasks, "esi")
    def test_304_with_no_active_fleet_self_heals(self, mock_esi, mock_get_token, mock_update):
        """Restarting a fleet the FC never left (ETag 304, no ActiveFleet) rebuilds it."""
        from esi.exceptions import HTTPNotModified

        mock_get_token.return_value = Mock()
        self.fc.start()  # active, but ActiveFleet was deleted on the previous Stop
        fleets = mock_esi.client.Fleets
        # First (non-forced) call → 304; forced retry → real fleet info
        fleets.GetCharactersCharacterIdFleet.return_value.result.side_effect = [
            HTTPNotModified(status_code=304, headers={}),
            _fleet_info(77),
        ]
        fleets.GetFleetsFleetId.return_value.result.return_value = _fleet_detail()

        tasks.check_fc_in_fleet(self.fc.pk)

        self.assertTrue(ActiveFleet.objects.filter(fc=self.fc, fleet_id=77).exists())

    @patch.object(tasks, "get_token")
    @patch.object(tasks, "esi")
    def test_stays_active_within_grace(self, mock_esi, mock_get_token):
        from esi.exceptions import HTTPClientError

        mock_get_token.return_value = Mock()
        self.fc.start()  # activated just now, no fleet formed yet
        mock_esi.client.Fleets.GetCharactersCharacterIdFleet.return_value.result.side_effect = (
            HTTPClientError(status_code=404, headers={}, data=None)
        )

        tasks.check_fc_in_fleet(self.fc.pk)

        self.fc.refresh_from_db()
        self.assertTrue(self.fc.is_active)  # within grace → keep waiting


class TestUpdateFleetMembers(FleetToolTestCase):
    """update_fleet_members rebuilds the member list from ESI."""

    def setUp(self):
        self.fc = FleetCommander.objects.create(user=self.user, character=self.user_character.character)
        self.fleet = ActiveFleet.objects.create(fc=self.fc, fleet_id=42)

    @patch.object(tasks, "_resolve_sde_names")
    @patch.object(tasks, "get_token")
    @patch.object(tasks, "esi")
    def test_members_synced(self, mock_esi, mock_get_token, mock_sde):
        from django.core.cache import cache
        cache.delete("fleet_tool_name_1001")  # force ESI resolution, not a cached name
        mock_get_token.return_value = Mock()
        fleets = mock_esi.client.Fleets
        fleets.GetFleetsFleetIdMembers.return_value.result.return_value = [_member(1001)]
        fleets.GetFleetsFleetIdWings.return_value.result.return_value = []
        # Characters via ESI, ships/systems via SDE (mocked here).
        mock_esi.client.Universe.PostUniverseNames.return_value.result.return_value = [
            SimpleNamespace(id=1001, name="Bruce Wayne"),
        ]
        mock_sde.side_effect = lambda model, ids: (
            {587: "Rifter"} if model == "ItemType" else {30000142: "Jita"}
        )

        tasks.update_fleet_members(self.fc.pk)

        member = FleetMember.objects.get(fleet=self.fleet, character_id=1001)
        self.assertEqual(member.character_name, "Bruce Wayne")
        self.assertEqual(member.ship_name, "Rifter")
        self.assertEqual(member.system_name, "Jita")

        # A composition snapshot was captured for the graph
        from aa_fleet_tool.models import FleetSnapshot
        snap = FleetSnapshot.objects.filter(fleet=self.fleet).latest("timestamp")
        self.assertEqual(snap.total, 1)

    @patch.object(tasks, "_resolve_sde_names")
    @patch.object(tasks, "get_token")
    @patch.object(tasks, "esi")
    def test_members_self_heal_on_304_when_empty(self, mock_esi, mock_get_token, mock_sde):
        """A 304 with no local members (after stop/start) forces a refetch."""
        from esi.exceptions import HTTPNotModified

        mock_get_token.return_value = Mock()
        mock_sde.return_value = {}
        fleets = mock_esi.client.Fleets
        fleets.GetFleetsFleetIdMembers.return_value.result.side_effect = [
            HTTPNotModified(status_code=304, headers={}),  # first (non-forced) call
            [_member(1001)],                                # forced retry
        ]
        fleets.GetFleetsFleetIdWings.return_value.result.return_value = []
        mock_esi.client.Universe.PostUniverseNames.return_value.result.return_value = [
            SimpleNamespace(id=1001, name="Heal Me"),
        ]

        self.assertEqual(self.fleet.members.count(), 0)
        tasks.update_fleet_members(self.fc.pk)

        self.assertTrue(
            FleetMember.objects.filter(fleet=self.fleet, character_id=1001).exists()
        )

    def test_snapshots_cascade_deleted_with_fleet(self):
        from django.utils import timezone

        from aa_fleet_tool.models import FleetSnapshot
        FleetSnapshot.objects.create(fleet=self.fleet, timestamp=timezone.now(), total=3)
        self.assertEqual(FleetSnapshot.objects.count(), 1)
        self.fleet.delete()
        self.assertEqual(FleetSnapshot.objects.count(), 0)

    def test_snapshot_window_prunes_old(self):
        from datetime import timedelta

        from django.utils import timezone

        from aa_fleet_tool.models import FleetSnapshot
        # An hour-old snapshot exists; writing a new one prunes anything > 10 min.
        FleetSnapshot.objects.create(
            fleet=self.fleet, timestamp=timezone.now() - timedelta(hours=1), total=1
        )
        tasks._write_snapshot(self.fleet)
        timestamps = list(self.fleet.snapshots.values_list("timestamp", flat=True))
        self.assertEqual(len(timestamps), 1)  # old pruned, only the fresh one remains
        self.assertGreater(timestamps[0], timezone.now() - timedelta(minutes=10))
