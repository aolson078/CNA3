"""Tests for cna.data.oob — Order of Battle data validation."""

from __future__ import annotations

from cna.data.oob.italian import build_italian_oob
from cna.data.oob.commonwealth import build_commonwealth_oob
from cna.data.oob.unit_types import (
    CPA_FOOT_INFANTRY,
    CPA_GARRISON,
    CPA_RECCE,
    CPA_TANK,
    FIELD_ARTILLERY_LIGHT,
    INFANTRY,
    TWENTY_FIVE_POUNDER,
)
from cna.data.maps.coords import hex_id_to_coord
from cna.engine.game_state import Side, UnitType, OrgSize


# ---------------------------------------------------------------------------
# Italian OOB
# ---------------------------------------------------------------------------


class TestItalianOOB:
    def setup_method(self):
        self.units = build_italian_oob()

    def test_unit_count(self):
        assert len(self.units) >= 20  # Divisions + garrisons + arty + AT.

    def test_all_axis(self):
        for u in self.units:
            assert u.side == Side.AXIS

    def test_all_have_positions(self):
        for u in self.units:
            assert u.position is not None, f"{u.id} has no position"

    def test_no_duplicate_ids(self):
        ids = [u.id for u in self.units]
        assert len(ids) == len(set(ids))

    def test_toe_within_max(self):
        for u in self.units:
            assert u.current_toe <= u.stats.max_toe_strength, (
                f"{u.id}: current_toe {u.current_toe} > max {u.stats.max_toe_strength}"
            )

    def test_1ccnn_is_infantry_division(self):
        u = next(u for u in self.units if u.id == "ax.1ccnn")
        assert u.unit_type == UnitType.INFANTRY
        assert u.org_size == OrgSize.DIVISION
        assert u.stats.capability_point_allowance == CPA_FOOT_INFANTRY

    def test_trivoli_is_armor(self):
        u = next(u for u in self.units if u.id == "ax.trivoli")
        assert u.unit_type == UnitType.TANK
        assert u.stats.anti_armor_strength > 0
        assert u.stats.armor_protection_rating > 0

    def test_garrisons_have_zero_cpa(self):
        garrisons = [u for u in self.units if "gar." in u.id]
        assert len(garrisons) >= 5
        for u in garrisons:
            assert u.stats.capability_point_allowance == CPA_GARRISON

    def test_artillery_has_barrage(self):
        arty = [u for u in self.units if u.unit_type == UnitType.ARTILLERY]
        assert len(arty) >= 2
        for u in arty:
            assert u.stats.barrage_rating > 0

    def test_at_has_anti_armor(self):
        at = [u for u in self.units if u.unit_type == UnitType.ANTI_TANK]
        assert len(at) >= 1
        for u in at:
            assert u.stats.anti_armor_strength > 0


# ---------------------------------------------------------------------------
# Commonwealth OOB
# ---------------------------------------------------------------------------


class TestCommonwealthOOB:
    def setup_method(self):
        self.units = build_commonwealth_oob()

    def test_unit_count(self):
        assert len(self.units) >= 15

    def test_all_commonwealth(self):
        for u in self.units:
            assert u.side == Side.COMMONWEALTH

    def test_all_have_positions(self):
        for u in self.units:
            assert u.position is not None, f"{u.id} has no position"

    def test_no_duplicate_ids(self):
        ids = [u.id for u in self.units]
        assert len(ids) == len(set(ids))

    def test_1krrc_cpa_is_10(self):
        """Case 6.15 — 1st KRRC without trucks has CPA 10."""
        u = next(u for u in self.units if u.id == "cw.1krrc")
        assert u.stats.capability_point_allowance == 10

    def test_1rnf_cpa_is_8(self):
        """Case 6.14 — 1st RNF is non-motorized with CPA 8."""
        u = next(u for u in self.units if u.id == "cw.1rnf")
        assert u.stats.capability_point_allowance == 8

    def test_11th_hussars_is_recce(self):
        u = next(u for u in self.units if u.id == "cw.11hus")
        assert u.unit_type == UnitType.RECCE
        assert u.stats.capability_point_allowance == CPA_RECCE

    def test_1rtr_is_tank_with_7_7_assault(self):
        """Case 60.41 — 1st RTR '(7/7)' = assault ratings 7/7."""
        u = next(u for u in self.units if u.id == "cw.1rtr")
        assert u.unit_type == UnitType.TANK
        assert u.stats.offensive_close_assault == 7
        assert u.stats.defensive_close_assault == 7

    def test_25pdr_has_barrage_and_anti_armor(self):
        """25-pdrs (4th RHA, 31st Field) have both barrage and anti-armor."""
        arty = [u for u in self.units if u.unit_type == UnitType.ARTILLERY]
        has_dual = any(
            u.stats.barrage_rating > 0 and u.stats.anti_armor_strength > 0
            for u in arty
        )
        assert has_dual, "No dual-role artillery found"

    def test_morale_generally_positive(self):
        """CW units in 1940 are generally well-trained (morale >= 1)."""
        combat = [u for u in self.units
                  if u.unit_type not in {UnitType.HEADQUARTERS}]
        avg_morale = sum(u.stats.basic_morale for u in combat) / len(combat)
        assert avg_morale >= 1.0


# ---------------------------------------------------------------------------
# Weapon profiles
# ---------------------------------------------------------------------------


def test_weapon_profile_infantry_no_barrage():
    assert INFANTRY.barrage == 0
    assert INFANTRY.anti_armor == 0
    assert INFANTRY.off_assault == 7

def test_weapon_profile_25pdr_dual_role():
    assert TWENTY_FIVE_POUNDER.barrage > 0
    assert TWENTY_FIVE_POUNDER.anti_armor > 0

def test_weapon_profile_field_arty_has_vulnerability():
    assert FIELD_ARTILLERY_LIGHT.vulnerability > 0
