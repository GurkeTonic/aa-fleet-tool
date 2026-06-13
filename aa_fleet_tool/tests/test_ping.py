"""Tests for the Fleet Ping (Discord webhook) and the webhook helper."""

from http import HTTPStatus
from unittest.mock import Mock, patch

from django.test import Client, TestCase
from django.urls import reverse

from aa_fleet_tool.discord import post_webhook
from aa_fleet_tool.tests import FleetToolTestCase


class TestDiscordWebhook(TestCase):
    @patch("aa_fleet_tool.discord.requests.post")
    def test_ok_sets_allowed_mentions(self, mock_post):
        mock_post.return_value = Mock(status_code=204)
        ok, _ = post_webhook("https://discord/x", content="<@&1> form up")
        self.assertTrue(ok)
        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["allowed_mentions"]["parse"], ["everyone"])

    @patch("aa_fleet_tool.discord.requests.post")
    def test_bad_status_is_error(self, mock_post):
        mock_post.return_value = Mock(status_code=404, text="nope")
        ok, _ = post_webhook("https://discord/x")
        self.assertFalse(ok)

    def test_no_webhook_is_error(self):
        ok, _ = post_webhook("")
        self.assertFalse(ok)

    @patch("aa_fleet_tool.discord.time.sleep")
    @patch("aa_fleet_tool.discord.requests.post")
    def test_429_is_retried(self, mock_post, mock_sleep):
        # First a rate limit (429 + Retry-After), then success.
        mock_post.side_effect = [
            Mock(status_code=429, headers={"Retry-After": "0.5"}, text="limited"),
            Mock(status_code=204),
        ]
        ok, _ = post_webhook("https://discord/x")
        self.assertTrue(ok)
        self.assertEqual(mock_post.call_count, 2)
        mock_sleep.assert_called_once()


class TestFleetPing(FleetToolTestCase):
    def setUp(self):
        from aa_fleet_tool.models import ActiveFleet, FleetCommander, FleetType, Webhook

        self.client = Client()
        self.client.force_login(self.user)
        self.fc = FleetCommander.objects.create(
            user=self.user, character=self.user_character.character
        )
        self.fleet = ActiveFleet.objects.create(
            fc=self.fc, fleet_id=42, name="Op Test", srp_link_code="ABC123"
        )
        self.wh = Webhook.objects.create(name="CTA Channel", url="https://discord/x")
        self.ft = FleetType.objects.create(name="CTA", mention="here")
        self.ft.webhooks.add(self.wh)

    @patch("aa_fleet_tool.views.ping.post_fleet_ping")
    def test_send_ping_builds_message(self, mock_task):
        response = self.client.post(
            reverse("aa_fleet_tool:send_fleet_ping", args=[self.fleet.pk]),
            data={"fleet_type_pk": self.ft.pk, "note": "Undock now"},
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTrue(response.json()["ok"])
        # The view dispatches a task with (webhook_urls, content, embed).
        mock_task.delay.assert_called_once()
        urls, content, embed = mock_task.delay.call_args.args
        self.assertEqual(urls, [self.wh.url])  # webhook target
        self.assertIn("@here", content)  # mention from FleetType
        fields = embed["fields"]
        values = " ".join(f["value"] for f in fields)
        self.assertIn("ABC123", values)  # stored SRP link
        self.assertIn("Undock now", values)  # note
        # Doctrine is always "Read MOTD"; the Members field is gone.
        doctrine = next(f for f in fields if f["name"] == "Doctrine")
        self.assertEqual(doctrine["value"], "Read MOTD")
        self.assertFalse(any(f["name"] == "Members" for f in fields))

    @patch("aa_fleet_tool.views.ping.post_fleet_ping")
    def test_posts_to_all_linked_webhooks(self, mock_task):
        from aa_fleet_tool.models import Webhook

        self.ft.webhooks.add(
            Webhook.objects.create(name="Second", url="https://discord/y")
        )
        self.client.post(
            reverse("aa_fleet_tool:send_fleet_ping", args=[self.fleet.pk]),
            data={"fleet_type_pk": self.ft.pk},
        )
        urls = mock_task.delay.call_args.args[0]
        self.assertEqual(len(urls), 2)

    def test_missing_fleet_type_is_400(self):
        response = self.client.post(
            reverse("aa_fleet_tool:send_fleet_ping", args=[self.fleet.pk]), data={}
        )
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)

    def test_fleet_type_without_webhook_is_400(self):
        from aa_fleet_tool.models import FleetType

        nowh = FleetType.objects.create(name="NoHook")  # no webhooks linked
        response = self.client.post(
            reverse("aa_fleet_tool:send_fleet_ping", args=[self.fleet.pk]),
            data={"fleet_type_pk": nowh.pk},
        )
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)

    def test_foreign_fleet_forbidden(self):
        from django.contrib.auth.models import User

        from aa_fleet_tool.models import FleetCommander

        other = User.objects.create_user("ping_other")
        FleetCommander.objects.filter(pk=self.fc.pk).update(user=other)
        response = self.client.post(
            reverse("aa_fleet_tool:send_fleet_ping", args=[self.fleet.pk]),
            data={"fleet_type_pk": self.ft.pk},
        )
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
