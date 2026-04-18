"""Tests for Operation Compass scenario builder (Section 60.0)."""

from __future__ import annotations

from cna.data.scenarios.operation_compass import (
    SCENARIO_ID_GRAZIANI,
    SCENARIO_ID_ITALIAN_CAMPAIGN,
    build_grazianis_offensive,
    build_italian_campaign,
)
from cna.engine.dice import DiceRoller
from cna.engine.game_state import (
    OperationsStage,
    Phase,
    Side,
    Unit,
)
from cna.rules.initiative import (
    current_ratings,
    handle_initiative_determination_phase,
    initiative_holder,
)


# ---------------------------------------------------------------------------
# Graziani's Offensive
# ---------------------------------------------------------------------------


def test_graziani_sets_scenario_metadata():
    state = build_grazianis_offensive()
    assert state.scenario_id == SCENARIO_ID_GRAZIANI
    assert state.extras["scenario_name"] == "Graziani's Offensive"
    assert state.extras["scenario_length_turns"] == 6


def test_graziani_starts_turn_1_stage_1_initiative_phase():
    state = build_grazianis_offensive()
    assert state.game_turn == 1
    assert state.operations_stage == OperationsStage.FIRST
    assert state.phase == Phase.INITIATIVE_DETERMINATION


def test_graziani_configures_both_players():
    state = build_grazianis_offensive()
    assert Side.AXIS in state.players
    assert Side.COMMONWEALTH in state.players


def test_graziani_encodes_case_60_6_italian_initiative():
    # Case 60.6 — Italian Player has Initiative for the first Game-Turn.
    state = build_grazianis_offensive()
    assert state.extras["scenario_turn1_initiative"] == "axis"

    # Exercise the turn-1 handler: it should honour the predetermined
    # winner without touching the dice.
    state.dice = DiceRoller(seed=0)  # fresh, empty log
    handle_initiative_determination_phase(state, None)
    assert initiative_holder(state) == Side.AXIS
    assert state.dice.roll_log == []  # no rolls consumed


def test_graziani_sets_default_initiative_ratings():
    # Case 7.14 worked example values apply to turn 1, Sept 1940.
    state = build_grazianis_offensive()
    r = current_ratings(state)
    assert r.axis == 1
    assert r.commonwealth == 3


def test_graziani_populates_named_hexes():
    state = build_grazianis_offensive()
    names = {mh.name for mh in state.map.values() if mh.name}
    # A handful of headline hexes should be present.
    for expected in ("Tobruk", "Mersa Matruh", "Cairo",
                     "Alexandria", "Sidi Barrani", "Bardia", "Siwa"):
        assert expected in names, f"missing named hex: {expected}"


def test_graziani_hex_controllers_split_axis_cw():
    state = build_grazianis_offensive()
    axis_hexes = [mh for mh in state.map.values() if mh.controller == Side.AXIS]
    cw_hexes = [mh for mh in state.map.values() if mh.controller == Side.COMMONWEALTH]
    assert len(axis_hexes) >= 8
    assert len(cw_hexes) >= 5
    # Tobruk (on the Libyan coast) starts Axis; Alexandria Commonwealth.
    tobruk = next(mh for mh in state.map.values() if mh.name == "Tobruk")
    alex = next(mh for mh in state.map.values() if mh.name == "Alexandria")
    assert tobruk.controller == Side.AXIS
    assert alex.controller == Side.COMMONWEALTH


def test_graziani_populates_axis_and_commonwealth_units():
    state = build_grazianis_offensive()
    axis = state.units_on_side(Side.AXIS)
    cw = state.units_on_side(Side.COMMONWEALTH)
    assert len(axis) >= 10
    assert len(cw) >= 5
    # Every unit must have a valid position on the encoded map.
    for u in axis + cw:
        assert u.position is None or u.position in state.map


def test_graziani_tobruk_holds_libyan_tank_command():
    # Case 60.31 — Tobruk: HQ: Libyan Tank Command.
    state = build_grazianis_offensive()
    tobruk = next(mh for mh in state.map.values() if mh.name == "Tobruk")
    units_here = state.units_at(tobruk.coord)
    names = [u.name for u in units_here]
    assert "Libyan Tank Command" in names


def test_graziani_7_armd_and_4_ind_deployed_near_matruh():
    # Case 60.41 — 7th Armoured at D3612, 4th Indian at D3615,
    # both near Mersa Matruh (D3714). With real hex IDs, they are
    # at their historical positions, not consolidated at Matruh.
    state = build_grazianis_offensive()
    unit_names = {u.name for u in state.units.values()}
    assert "7th Armoured Division" in unit_names
    assert "4th Indian Division" in unit_names
    # Both should be on the map.
    armd = next(u for u in state.units.values() if u.name == "7th Armoured Division")
    ind = next(u for u in state.units.values() if u.name == "4th Indian Division")
    assert armd.position is not None
    assert ind.position is not None


def test_graziani_logs_scenario_load_entry():
    state = build_grazianis_offensive()
    scenario_entries = [e for e in state.turn_log if e.category == "scenario"]
    assert len(scenario_entries) == 1
    assert "Graziani's Offensive" in scenario_entries[0].message


def test_graziani_unit_current_toe_matches_max():
    state = build_grazianis_offensive()
    for u in state.units.values():
        assert u.current_toe == u.stats.max_toe_strength


# ---------------------------------------------------------------------------
# Italian Campaign
# ---------------------------------------------------------------------------


def test_italian_campaign_sets_20_turn_length():
    state = build_italian_campaign()
    assert state.scenario_id == SCENARIO_ID_ITALIAN_CAMPAIGN
    assert state.extras["scenario_length_turns"] == 20


def test_both_scenarios_share_initial_deployment():
    # Case 60.22 and 60.23 start from the same OOB and same map; only the
    # length differs.
    g = build_grazianis_offensive()
    c = build_italian_campaign()
    assert set(g.units.keys()) == set(c.units.keys())
    assert set(g.map.keys()) == set(c.map.keys())


# ---------------------------------------------------------------------------
# Save/load round trip
# ---------------------------------------------------------------------------


def test_scenario_round_trips_through_json(tmp_path):
    from cna.engine.saves import load, save

    state = build_grazianis_offensive()
    path = tmp_path / "save.json"
    save(state, path)
    restored = load(path)

    assert restored.scenario_id == state.scenario_id
    assert len(restored.units) == len(state.units)
    assert len(restored.map) == len(state.map)
    tobruk = next(mh for mh in restored.map.values() if mh.name == "Tobruk")
    assert tobruk.controller == Side.AXIS
    assert restored.extras["scenario_turn1_initiative"] == "axis"


# ---------------------------------------------------------------------------
# Dashboard smoke (end-to-end render)
# ---------------------------------------------------------------------------


def test_scenario_renders_through_dashboard():
    import io
    from rich.console import Console
    from cna.ui.dashboard import build_layout
    from cna.ui.views import build_view

    state = build_grazianis_offensive()
    view = build_view(state, viewer=Side.AXIS)
    buf = io.StringIO()
    console = Console(file=buf, width=220, force_terminal=False, color_system=None)
    console.print(build_layout(view))
    out = buf.getvalue()
    # Spot-check that the scenario propagated to the dashboard.
    assert "Turn 1" in out
    assert "Initiative Determination" in out
    # Scenario-load log entry reaches the Phase Log panel.
    assert "Graziani" in out
    # Redacted enemy OOB heading is present.
    assert "Commonwealth OOB (redacted)" in out
    # Enemy division names are NOT revealed to the Axis viewer.
    assert "7th Armoured Division" not in out
    assert "4th Indian Division" not in out
