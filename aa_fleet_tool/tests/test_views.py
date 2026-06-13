"""Tests for Fleet Tool views."""

# Standard Library
from http import HTTPStatus
from unittest.mock import patch

# Django
from django.test import Client
from django.urls import reverse

# AA Fleet Tool
from aa_fleet_tool.tests import FleetToolTestCase


class TestIndexView(FleetToolTestCase):
    """Tests for the index view."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = Client()

    def test_index_not_logged_in(self):
        """Unauthenticated users should be redirected to login."""
        response = self.client.get(reverse("aa_fleet_tool:index"))
        self.assertEqual(response.status_code, HTTPStatus.FOUND)

    def test_index_no_permission(self):
        """Users without permission should be redirected."""
        self.client.force_login(self.user)
        # Remove permission
        from django.contrib.auth.models import Permission

        perm = Permission.objects.get(codename="view_fleet_tool")
        self.user.user_permissions.remove(perm)
        self.user = type(self.user).objects.get(pk=self.user.pk)
        response = self.client.get(reverse("aa_fleet_tool:index"))
        self.assertIn(response.status_code, [HTTPStatus.FOUND, HTTPStatus.FORBIDDEN])

    def test_index_with_permission(self):
        """Users with permission should get a 200 response."""
        self.client.force_login(self.user)
        response = self.client.get(reverse("aa_fleet_tool:index"))
        self.assertEqual(response.status_code, HTTPStatus.OK)


class TestFleetWriteViews(FleetToolTestCase):
    """Write endpoints route through the django-esi client and enforce ownership."""

    def setUp(self):
        from aa_fleet_tool.models import ActiveFleet, FleetCommander

        self.client = Client()
        self.client.force_login(self.user)
        self.fc = FleetCommander.objects.create(
            user=self.user, character=self.user_character.character
        )
        self.fleet = ActiveFleet.objects.create(fc=self.fc, fleet_id=42)

    @patch("aa_fleet_tool.views.common.get_token")
    @patch("aa_fleet_tool.views.fleets.esi")
    def test_set_motd_calls_esi_and_stores(self, mock_esi, mock_get_token):
        mock_get_token.return_value = object()  # truthy write token
        mock_esi.client.Fleets.PutFleetsFleetId.return_value.result.return_value = None

        response = self.client.post(
            reverse("aa_fleet_tool:set_motd", args=[self.fleet.pk]),
            data={"motd": "Form up at Jita"},
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTrue(response.json()["ok"])
        mock_esi.client.Fleets.PutFleetsFleetId.assert_called_once()
        self.fleet.refresh_from_db()
        self.assertEqual(self.fleet.motd, "Form up at Jita")

    @patch("aa_fleet_tool.views.common.get_token")
    def test_set_motd_without_write_token_forbidden(self, mock_get_token):
        # No valid write token → 403, no ESI call attempted.
        mock_get_token.return_value = None
        response = self.client.post(
            reverse("aa_fleet_tool:set_motd", args=[self.fleet.pk]),
            data={"motd": "x"},
        )
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)


class TestFleetStartStop(FleetToolTestCase):
    """Fleet Start activates polling for an FC; Stop deactivates and clears it."""

    def setUp(self):
        from aa_fleet_tool.models import FleetCommander

        self.client = Client()
        self.client.force_login(self.user)
        self.fc = FleetCommander.objects.create(
            user=self.user, character=self.user_character.character
        )

    @patch("aa_fleet_tool.views.commanders.check_fc_in_fleet")
    def test_start_fleet_activates(self, mock_task):
        response = self.client.post(
            reverse("aa_fleet_tool:start_fleet"), data={"fc_pk": self.fc.pk}
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.fc.refresh_from_db()
        self.assertTrue(self.fc.is_active)
        self.assertIsNotNone(self.fc.activated_at)
        mock_task.delay.assert_called_once_with(self.fc.pk, force=True)

    def test_stop_fleet_deactivates_and_clears(self):
        from aa_fleet_tool.models import ActiveFleet

        self.fc.start()
        ActiveFleet.objects.create(fc=self.fc, fleet_id=5)
        response = self.client.post(
            reverse("aa_fleet_tool:stop_fleet"), data={"fc_pk": self.fc.pk}
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.fc.refresh_from_db()
        self.assertFalse(self.fc.is_active)
        self.assertFalse(ActiveFleet.objects.filter(fc=self.fc).exists())

    def test_cannot_start_foreign_fc(self):
        from django.contrib.auth.models import User

        from aa_fleet_tool.models import FleetCommander

        other = User.objects.create_user("other_user")
        FleetCommander.objects.filter(pk=self.fc.pk).update(user=other)
        response = self.client.post(
            reverse("aa_fleet_tool:start_fleet"), data={"fc_pk": self.fc.pk}
        )
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)


class TestFleetMembersJson(FleetToolTestCase):
    """The live endpoint always returns composition + the snapshot history."""

    def setUp(self):
        from django.utils import timezone

        from aa_fleet_tool.models import (
            ActiveFleet,
            FleetCommander,
            FleetMember,
            FleetSnapshot,
        )

        self.client = Client()
        self.client.force_login(self.user)
        fc = FleetCommander.objects.create(
            user=self.user, character=self.user_character.character
        )
        self.fleet = ActiveFleet.objects.create(
            fc=fc, fleet_id=42, last_updated=timezone.now()
        )
        FleetMember.objects.create(fleet=self.fleet, character_id=1, ship_type_id=587)
        FleetMember.objects.create(fleet=self.fleet, character_id=2, ship_type_id=587)
        FleetSnapshot.objects.create(
            fleet=self.fleet, timestamp=timezone.now(), total=2, dps=2, logi=0
        )

    def test_json_has_breakdown_and_history(self):
        response = self.client.get(
            reverse("aa_fleet_tool:fleet_members_json", args=[self.fleet.pk])
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        # composition is always present (no doctrine required)
        self.assertIn("role_breakdown", data)
        self.assertEqual(sum(r["count"] for r in data["role_breakdown"].values()), 2)
        # snapshot history for the graph
        self.assertEqual(len(data["history"]), 1)
        self.assertEqual(data["history"][0]["total"], 2)


class TestMotdTemplates(FleetToolTestCase):
    """Public MOTDs need manage_doctrine; private MOTDs belong to their owner."""

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)  # has view_fleet_tool, NOT manage_doctrine

    def test_create_private_template_as_plain_fc(self):
        from aa_fleet_tool.models import MOTDTemplate

        response = self.client.post(
            reverse("aa_fleet_tool:create_motd_template"),
            data={"name": "My Form-Up", "text": "x", "is_public": "false"},
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        tpl = MOTDTemplate.objects.get(name="My Form-Up")
        self.assertFalse(tpl.is_public)
        self.assertEqual(tpl.created_by, self.user)

    def test_plain_fc_cannot_create_public(self):
        response = self.client.post(
            reverse("aa_fleet_tool:create_motd_template"),
            data={"name": "Shared", "text": "x", "is_public": "true"},
        )
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_manager_can_create_public(self):
        from allianceauth.tests.auth_utils import AuthUtils

        from aa_fleet_tool.models import MOTDTemplate

        self.user = AuthUtils.add_permission_to_user_by_name(
            "aa_fleet_tool.manage_doctrine", self.user
        )
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("aa_fleet_tool:create_motd_template"),
            data={"name": "Shared", "text": "x", "is_public": "true"},
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTrue(MOTDTemplate.objects.get(name="Shared").is_public)

    def test_cannot_edit_other_users_private_template(self):
        from django.contrib.auth.models import User

        from aa_fleet_tool.models import MOTDTemplate

        other = User.objects.create_user("other_fc")
        tpl = MOTDTemplate.objects.create(
            name="Theirs", text="x", is_public=False, created_by=other
        )
        url = reverse("aa_fleet_tool:update_motd_template", args=[tpl.pk])
        response = self.client.post(url, data={"name": "Hijacked", "text": "y"})
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_motd_page_separates_public_and_private(self):
        from django.contrib.auth.models import User

        from aa_fleet_tool.models import MOTDTemplate

        other = User.objects.create_user("other_fc2")
        MOTDTemplate.objects.create(name="PublicOne", text="x", is_public=True)
        MOTDTemplate.objects.create(
            name="MinePriv", text="x", is_public=False, created_by=self.user
        )
        MOTDTemplate.objects.create(
            name="TheirPriv", text="x", is_public=False, created_by=other
        )

        response = self.client.get(reverse("aa_fleet_tool:motd"))
        public_names = {t.name for t in response.context["public_templates"]}
        mine_names = {t.name for t in response.context["my_templates"]}
        self.assertIn("PublicOne", public_names)
        self.assertIn("MinePriv", mine_names)
        self.assertNotIn("TheirPriv", mine_names)
        self.assertNotIn("TheirPriv", public_names)


class TestDoctrineCrud(FleetToolTestCase):
    """Doctrine CRUD needs the manage_doctrine permission and touches no ESI."""

    def setUp(self):
        from allianceauth.tests.auth_utils import AuthUtils

        self.user = AuthUtils.add_permission_to_user_by_name(
            "aa_fleet_tool.manage_doctrine", self.user
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_create_doctrine(self):
        from aa_fleet_tool.models import Doctrine

        response = self.client.post(
            reverse("aa_fleet_tool:create_doctrine"), data={"name": "Shield Ferox"}
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTrue(Doctrine.objects.filter(name="Shield Ferox").exists())

    def test_create_doctrine_requires_name(self):
        response = self.client.post(reverse("aa_fleet_tool:create_doctrine"), data={})
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
