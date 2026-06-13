"""Tests for the doctrine-independent composition classifier."""

from unittest.mock import patch

from django.test import TestCase

from aa_fleet_tool import composition


class TestComposition(TestCase):
    @patch("aa_fleet_tool.composition.ship_roles")
    def test_composition_counts(self, mock_roles):
        mock_roles.return_value = {587: "dps", 11987: "logi", 22442: "booster"}
        comp = composition.composition_counts([587, 587, 11987, 22442])
        self.assertEqual(comp["dps"]["count"], 2)
        self.assertEqual(comp["logi"]["count"], 1)
        self.assertEqual(comp["booster"]["count"], 1)
        self.assertEqual(comp["dps"]["pct"], 50)  # 2 of 4
        self.assertEqual(comp["logi"]["pct"], 25)

    @patch("aa_fleet_tool.composition.ship_roles")
    def test_unknown_ship_defaults_to_dps(self, mock_roles):
        mock_roles.return_value = {}  # SDE returned nothing
        comp = composition.composition_counts([1, 2, 3])
        self.assertEqual(comp["dps"]["count"], 3)
        self.assertEqual(comp["other"]["count"], 0)

    def test_empty(self):
        comp = composition.composition_counts([])
        self.assertEqual(comp["dps"]["count"], 0)
        self.assertEqual(comp["dps"]["pct"], 0)

    @patch("aa_fleet_tool.composition.ship_roles")
    def test_doctrine_fully_overrides_sde(self, mock_roles):
        # SDE would call both dps, but with a doctrine the SDE is ignored entirely:
        # in-doctrine ship → its role, off-doctrine ship → "other" (not dps).
        mock_roles.return_value = {587: "dps", 999: "dps"}
        doctrine_roles = {587: "logi"}  # only 587 is in the doctrine
        comp = composition.composition_counts([587, 999], doctrine_roles)
        self.assertEqual(comp["logi"]["count"], 1)  # 587 → logi
        self.assertEqual(comp["other"]["count"], 1)  # 999 off-doctrine → other
        self.assertEqual(comp["dps"]["count"], 0)
        mock_roles.assert_not_called()  # SDE bypassed in doctrine mode

    def test_doctrine_overrides_maps_only_buckets(self):
        # role_hint mapping: only dps/logi/booster/ewar override; any/fc/etc. ignored
        ov = composition.doctrine_overrides(
            {1: "logi", 2: "ewar", 3: "any", 4: "fc", 5: "scout"}
        )
        self.assertEqual(ov, {1: "logi", 2: "ewar"})
