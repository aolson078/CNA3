"""Tests for cna.data.scenarios.operation_compass (Section 60.0)."""

from __future__ import annotations

from cna.data.scenarios.operation_compass import (
    SCENARIO_ID_GRAZIANI,
    SCENARIO_ID_ITALIAN_CAMPAIGN,
    build_grazianis_offensive,
    build_italian_campaign,
)
from cna.engine.game_state import (
    OperationsStage,
    Phase,
    Side,
    TerrainType,
)
from cna.engine.sequence_of_play import PhaseDriver
from cna.rules.initiative import (
    handle_initiative_declaration_phase,
    handle_initiative_determination_phase,
    initiative_holder,
)
from cna.ui.views import build_view


# ---------------------------------------------------------------------------
# Graziani's Offensive (Case 60.22)
# ---------------------------------------------------------------------------


class TestGrazianisOffensive:
    def setup_method(self):
        self.gs = build_grazianis_offensive()

    def test_scenario_id(self):
        assert self.gs.scenario_id == SCENARIO_ID_GRAZIANI

    def test_starts_at_turn1_stage1(self):
        # Case 60.22 — starts Game-Turn 1 OpStage 1.
        assert self.gs.game_turn == 1
        assert self.gs.operations_stage == OperationsStage.FIRST
        assert self.gs.phase == Phase.INITIATIVE_DETERMINATION

    def test_both_players_configured(self):
        assert Side.AXIS in self.gs.players
        assert Side.COMMONWEALTH in self.gs.players

    def test_map_has_named_hexes(self):
        names = {mh.name for mh in self.gs.map.values()}
        assert "Tobruk" in names
        assert "Bardia" in names
        assert "Mersa Matruh" in names
        assert "Alexandria" in names
        assert "Cairo" in names

    def test_tobruk_is_axis_port(self):
        # Case 60.7 — Tobruk at Efficiency Level 7 (port_capacity=4 in
        # the abbreviated deployment).
        tobruk = [mh for mh in self.gs.map.values() if mh.name == "Tobruk"]
        assert len(tobruk) == 1
        assert tobruk[0].controller == Side.AXIS
        assert tobruk[0].port_capacity > 0

    def test_axis_units_deployed(self):
        axis = [u for u in self.gs.units.values() if u.side == Side.AXIS]
        assert len(axis) >= 10  # At least 10 Italian formations.
        names = {u.name for u in axis}
        assert "1st CCNN Division" in names
        assert "Libyan Tank Command" in names

    def test_commonwealth_units_deployed(self):
        cw = [u for u in self.gs.units.values() if u.side == Side.COMMONWEALTH]
        assert len(cw) >= 5
        names = {u.name for u in cw}
        assert any("7th Armoured" in n for n in names)
        assert any("4th Indian" in n or "4th Ind" in n for n in names)

    def test_all_units_on_map(self):
        for u in self.gs.units.values():
            assert u.position is not None, f"Unit {u.id} has no position"
            assert u.position in self.gs.map, f"Unit {u.id} at {u.position} not on map"

    def test_initiative_predetermined_axis(self):
        # Case 60.6 — Axis has Initiative for the entire first Game-Turn.
        assert self.gs.extras.get("scenario_turn1_initiative") == "axis"

    def test_initiative_ratings_set(self):
        # Case 7.14 example: Axis (no Germans) = 1, CW turns 1-42 = 3.
        ratings = self.gs.extras.get("initiative_ratings")
        assert ratings["axis"] == 1
        assert ratings["commonwealth"] == 3

    def test_scenario_length(self):
        # Case 60.22 — ends after Game-Turn 6.
        assert self.gs.extras.get("scenario_length_turns") == 6

    def test_log_has_scenario_loaded(self):
        assert len(self.gs.turn_log) >= 1
        assert "Graziani" in self.gs.turn_log[0].message

    def test_phasedriver_initiative_integration(self):
        # Drive the scenario through initiative determination and declaration.
        driver = PhaseDriver(self.gs)
        driver.register(Phase.INITIATIVE_DETERMINATION,
                       handle_initiative_determination_phase)
        driver.register(Phase.INITIATIVE_DECLARATION,
                       handle_initiative_declaration_phase)
        driver.step()  # Initiative Determination → Naval Convoy Schedule
        assert initiative_holder(self.gs) == Side.AXIS

    def test_dashboard_renders_without_error(self):
        view = build_view(self.gs, viewer=Side.AXIS)
        assert len(view.units) == len(self.gs.units)
        assert len(view.hexes) == len(self.gs.map)
        # Enemy units are opaque.
        enemy = [u for u in view.units if not u.is_friendly]
        for u in enemy:
            assert u.name is None


# ---------------------------------------------------------------------------
# The Italian Campaign (Case 60.23)
# ---------------------------------------------------------------------------


class TestItalianCampaign:
    def setup_method(self):
        self.gs = build_italian_campaign()

    def test_scenario_id(self):
        assert self.gs.scenario_id == SCENARIO_ID_ITALIAN_CAMPAIGN

    def test_scenario_length(self):
        # Case 60.23 — ends after Game-Turn 20.
        assert self.gs.extras.get("scenario_length_turns") == 20

    def test_same_deployment_as_graziani(self):
        # Both scenarios share the same initial deployment; only length differs.
        graz = build_grazianis_offensive()
        assert set(self.gs.units.keys()) == set(graz.units.keys())
        assert set(self.gs.map.keys()) == set(graz.map.keys())


# ---------------------------------------------------------------------------
# Save round-trip
# ---------------------------------------------------------------------------


def test_scenario_save_roundtrip():
    from cna.engine.saves import from_json, to_json

    gs = build_grazianis_offensive()
    restored = from_json(to_json(gs))
    assert restored.scenario_id == gs.scenario_id
    assert len(restored.units) == len(gs.units)
    assert len(restored.map) == len(gs.map)
    assert restored.extras["scenario_turn1_initiative"] == "axis"
