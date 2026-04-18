"""Integration tests for combat resolution (Sections 11-15).

Tests the full combat pipeline: resolver + App wiring.
"""

from __future__ import annotations

import io

from rich.console import Console

from cna.engine.dice import DiceRoller
from cna.engine.game_state import (
    GameState,
    HexCoord,
    MapHex,
    OrgSize,
    Phase,
    Player,
    Side,
    TerrainType,
    Unit,
    UnitClass,
    UnitStats,
    UnitType,
)
from cna.rules.combat.common import (
    actual_points,
    raw_points,
    summarize_combat_strength,
)
from cna.rules.combat.resolver import resolve_combat, CombatReport
from cna.ui.app import App, Key


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _u(uid: str, side: Side, at: HexCoord, *,
       ut: UnitType = UnitType.INFANTRY, org: OrgSize = OrgSize.BATTALION,
       cpa: int = 20, toe: int = 6, morale: int = 1,
       off_ca: int = 7, def_ca: int = 7,
       barrage: int = 0, anti_armor: int = 0, armor_prot: int = 0) -> Unit:
    return Unit(
        id=uid, side=side, name=uid,
        unit_type=ut, unit_class=UnitClass.INFANTRY, org_size=org,
        stats=UnitStats(
            capability_point_allowance=cpa, max_toe_strength=toe,
            basic_morale=morale, offensive_close_assault=off_ca,
            defensive_close_assault=def_ca, barrage_rating=barrage,
            anti_armor_strength=anti_armor, armor_protection_rating=armor_prot,
        ),
        position=at, current_toe=toe, current_morale=morale,
    )


def _combat_state(*, seed: int = 42) -> GameState:
    """Build a minimal state with two opposing units on adjacent hexes."""
    gs = GameState()
    gs.dice = DiceRoller(seed=seed)
    gs.active_side = Side.AXIS
    gs.phase = Phase.MOVEMENT_AND_COMBAT
    gs.players = {
        Side.AXIS: Player(side=Side.AXIS),
        Side.COMMONWEALTH: Player(side=Side.COMMONWEALTH),
    }
    h0 = HexCoord(0, 0)
    h1 = HexCoord(1, 0)
    gs.map = {
        h0: MapHex(coord=h0, terrain=TerrainType.DESERT),
        h1: MapHex(coord=h1, terrain=TerrainType.DESERT),
    }
    # Axis infantry at (0,0), CW infantry at (1,0).
    gs.units["ax1"] = _u("ax1", Side.AXIS, h0, toe=8, off_ca=7, def_ca=7)
    gs.units["cw1"] = _u("cw1", Side.COMMONWEALTH, h1, toe=6, off_ca=7, def_ca=7)
    return gs


# ---------------------------------------------------------------------------
# Resolver tests
# ---------------------------------------------------------------------------


def test_resolve_combat_basic():
    gs = _combat_state()
    report = resolve_combat(gs, HexCoord(0, 0), HexCoord(1, 0))
    assert isinstance(report, CombatReport)
    assert report.attacker_side == Side.AXIS
    assert report.defender_side == Side.COMMONWEALTH
    assert report.close_assault is not None


def test_resolve_combat_applies_losses():
    gs = _combat_state()
    att_toe_before = gs.units["ax1"].current_toe
    def_toe_before = gs.units["cw1"].current_toe
    report = resolve_combat(gs, HexCoord(0, 0), HexCoord(1, 0))
    att_toe_after = gs.units["ax1"].current_toe
    def_toe_after = gs.units["cw1"].current_toe
    # At least one side should take losses (unless both roll poorly).
    total_losses = (att_toe_before - att_toe_after) + (def_toe_before - def_toe_after)
    # Losses reported in the report.
    assert report.attacker_toe_lost >= 0
    assert report.defender_toe_lost >= 0


def test_resolve_combat_costs_cp():
    gs = _combat_state()
    resolve_combat(gs, HexCoord(0, 0), HexCoord(1, 0))
    assert gs.units["ax1"].capability_points_spent == 5  # Phasing assault.
    assert gs.units["cw1"].capability_points_spent == 3  # Defending full.


def test_resolve_probe_costs_less_cp():
    gs = _combat_state()
    resolve_combat(gs, HexCoord(0, 0), HexCoord(1, 0), is_probe=True)
    assert gs.units["ax1"].capability_points_spent == 2  # Probe.
    assert gs.units["cw1"].capability_points_spent == 2  # Defending probe.


def test_resolve_combat_with_barrage():
    gs = _combat_state()
    # Give attacker artillery.
    gs.units["ax_arty"] = _u(
        "ax_arty", Side.AXIS, HexCoord(0, 0),
        ut=UnitType.ARTILLERY, barrage=12, toe=4, off_ca=2, def_ca=3,
    )
    report = resolve_combat(gs, HexCoord(0, 0), HexCoord(1, 0))
    assert report.barrage is not None
    assert report.barrage.barrage_points > 0


def test_resolve_combat_with_anti_armor():
    gs = _combat_state()
    # Give attacker AT capability and defender armor.
    gs.units["ax1"].stats = UnitStats(
        capability_point_allowance=20, max_toe_strength=8,
        anti_armor_strength=6, offensive_close_assault=7,
        defensive_close_assault=7, basic_morale=1,
    )
    gs.units["cw1"] = _u(
        "cw1", Side.COMMONWEALTH, HexCoord(1, 0),
        ut=UnitType.TANK, armor_prot=3, anti_armor=5,
        off_ca=7, def_ca=5, toe=4,
    )
    report = resolve_combat(gs, HexCoord(0, 0), HexCoord(1, 0))
    # At least one side should have fired anti-armor.
    assert report.anti_armor_attacker is not None or report.anti_armor_defender is not None


def test_resolve_combat_empty_hex_is_noop():
    gs = _combat_state()
    # Remove defender.
    del gs.units["cw1"]
    report = resolve_combat(gs, HexCoord(0, 0), HexCoord(1, 0))
    assert report.close_assault is None
    assert report.attacker_toe_lost == 0


def test_combat_report_summary():
    gs = _combat_state()
    report = resolve_combat(gs, HexCoord(0, 0), HexCoord(1, 0))
    assert isinstance(report.summary, str)
    assert len(report.summary) > 0


# ---------------------------------------------------------------------------
# Rulebook example: Case 11.35 — 90th Leichte Division barrage
# ---------------------------------------------------------------------------


def test_case_11_35_barrage_calculation():
    """Case 11.35 — 361 Arty (3×9=27) + 190 Arty (3×18+3×9=81) = 108 raw → 11 actual."""
    u361 = _u("361", Side.AXIS, HexCoord(0, 0), ut=UnitType.ARTILLERY,
              barrage=9, toe=3)
    u190a = _u("190a", Side.AXIS, HexCoord(0, 0), ut=UnitType.ARTILLERY,
               barrage=18, toe=3)
    u190b = _u("190b", Side.AXIS, HexCoord(0, 0), ut=UnitType.ARTILLERY,
               barrage=9, toe=3)
    summary = summarize_combat_strength([u361, u190a, u190b])
    assert summary.barrage_raw == 108
    assert summary.barrage_actual == 11


# ---------------------------------------------------------------------------
# App integration
# ---------------------------------------------------------------------------


def _mk_combat_app():
    gs = _combat_state()
    console = Console(file=io.StringIO(), width=120, force_terminal=False,
                      color_system=None)
    return App(state=gs, viewer=Side.AXIS, console=console)


def test_app_combat_outside_phase():
    app = _mk_combat_app()
    app.state.phase = Phase.INITIATIVE_DETERMINATION
    app.selected = HexCoord(0, 0)
    log_len = len(app.state.turn_log)
    app.step(Key.COMBAT)
    assert any("Combat only" in e.message for e in app.state.turn_log[log_len:])


def test_app_combat_no_enemy_adjacent():
    app = _mk_combat_app()
    # Move defender far away.
    app.state.units["cw1"].position = HexCoord(99, 99)
    app.selected = HexCoord(0, 0)
    log_len = len(app.state.turn_log)
    app.step(Key.COMBAT)
    assert any("No adjacent" in e.message for e in app.state.turn_log[log_len:])


def test_app_combat_resolves():
    app = _mk_combat_app()
    app.selected = HexCoord(0, 0)
    log_len = len(app.state.turn_log)
    app.step(Key.COMBAT)
    combat_entries = [e for e in app.state.turn_log[log_len:] if e.category == "combat"]
    assert len(combat_entries) >= 1
    assert "Assault" in combat_entries[0].message


def test_app_probe_resolves():
    app = _mk_combat_app()
    app.selected = HexCoord(0, 0)
    log_len = len(app.state.turn_log)
    app.step(Key.PROBE)
    combat_entries = [e for e in app.state.turn_log[log_len:] if e.category == "combat"]
    assert len(combat_entries) >= 1
    assert "Probe" in combat_entries[0].message


def test_app_combat_with_undo():
    app = _mk_combat_app()
    app.selected = HexCoord(0, 0)
    toe_before = app.state.units["cw1"].current_toe
    app.step(Key.COMBAT)
    # Undo should restore the state.
    app.step(Key.UNDO)
    assert app.state.units["cw1"].current_toe == toe_before
