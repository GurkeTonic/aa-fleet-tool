"""Tests for Fleet Tool views."""

# Standard Library
from http import HTTPStatus

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
