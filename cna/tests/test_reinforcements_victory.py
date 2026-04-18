"""Tests for reinforcement arrival and victory conditions."""

from __future__ import annotations

from cna.data.scenarios.operation_compass import build_grazianis_offensive
from cna.data.scenarios.victory import (
    VictoryLevel,
    check_graziani_victory,
    check_italian_campaign_victory,
)
from cna.engine.game_state import (
    GameState,
    HexCoord,
    OrgSize,
    Phase,
    Side,
    Unit,
    UnitClass,
    UnitStats,
    UnitType,
)
from cna.data.maps.coords import hex_id_to_coord
from cna.rules.units.reinforcements import (
    get_due_reinforcements,
    place_reinforcements,
)


# ---------------------------------------------------------------------------
# Reinforcement scheduling
# ---------------------------------------------------------------------------


def test_no_reinforcements_turn_1():
    gs = build_grazianis_offensive()
    gs.game_turn = 1
    due = get_due_reinforcements(gs)
    assert len(due) == 0


def test_reinforcements_due_turn_7():
    gs = build_grazianis_offensive()
    gs.game_turn = 7
    due = get_due_reinforcements(gs)
    assert len(due) == 1
    assert due[0].unit_id == "cw.7rtr"


def test_place_reinforcements():
    gs = build_grazianis_offensive()
    gs.game_turn = 7
    placed = place_reinforcements(gs)
    assert "cw.7rtr" in placed
    unit = gs.units["cw.7rtr"]
    assert unit.name == "7th RTR"
    assert unit.side == Side.COMMONWEALTH
    assert unit.unit_type == UnitType.TANK
    assert unit.position is not None


def test_place_reinforcements_idempotent():
    gs = build_grazianis_offensive()
    gs.game_turn = 7
    place_reinforcements(gs)
    # Placing again should not duplicate.
    placed = place_reinforcements(gs)
    assert "cw.7rtr" not in placed


def test_multiple_reinforcements_same_turn():
    gs = build_grazianis_offensive()
    gs.game_turn = 10
    placed = place_reinforcements(gs)
    assert "cw.19aus_bde" in placed
    assert "cw.6div_arty" in placed


# ---------------------------------------------------------------------------
# Victory conditions — Graziani's Offensive (Case 60.81)
# ---------------------------------------------------------------------------


def _place_unit_at(gs: GameState, uid: str, side: Side, place: str):
    """Place a combat unit at a named location."""
    from cna.data.maps.hex_catalog import get_by_name
    entry = get_by_name(place)
    assert entry is not None, f"Unknown place: {place}"
    gs.units[uid] = Unit(
        id=uid, side=side, name=uid, unit_type=UnitType.INFANTRY,
        unit_class=UnitClass.INFANTRY, org_size=OrgSize.BATTALION,
        stats=UnitStats(max_toe_strength=6, offensive_close_assault=7,
                       defensive_close_assault=7),
        position=entry.coord, current_toe=6,
    )


def test_graziani_draw_at_start():
    gs = build_grazianis_offensive()
    result = check_graziani_victory(gs)
    assert result.level == VictoryLevel.DRAW


def test_graziani_axis_strategic_holds_alexandria():
    gs = build_grazianis_offensive()
    _place_unit_at(gs, "ax.test", Side.AXIS, "Alexandria")
    result = check_graziani_victory(gs)
    assert result.winner == Side.AXIS
    assert result.level == VictoryLevel.STRATEGIC


def test_graziani_axis_tactical_holds_frontier():
    gs = build_grazianis_offensive()
    for place in ("Sidi Barrani", "Sollum", "Fort Maddalena", "Giarabub"):
        _place_unit_at(gs, f"ax.{place}", Side.AXIS, place)
    result = check_graziani_victory(gs)
    assert result.winner == Side.AXIS
    assert result.level == VictoryLevel.TACTICAL


def test_graziani_cw_strategic_holds_tobruk():
    gs = build_grazianis_offensive()
    _place_unit_at(gs, "cw.tobruk", Side.COMMONWEALTH, "Tobruk")
    result = check_graziani_victory(gs)
    assert result.winner == Side.COMMONWEALTH
    assert result.level == VictoryLevel.STRATEGIC


def test_graziani_cw_tactical_holds_frontier():
    gs = build_grazianis_offensive()
    for place in ("Sollum", "Halfaya Pass", "Siwa"):
        _place_unit_at(gs, f"cw.{place}", Side.COMMONWEALTH, place)
    result = check_graziani_victory(gs)
    assert result.winner == Side.COMMONWEALTH
    assert result.level == VictoryLevel.TACTICAL


# ---------------------------------------------------------------------------
# Victory conditions — Italian Campaign (Case 60.82)
# ---------------------------------------------------------------------------


def test_italian_campaign_no_axis_is_cw_strategic():
    gs = build_grazianis_offensive()
    # Remove all Axis combat units.
    to_remove = [uid for uid, u in gs.units.items()
                 if u.side == Side.AXIS and u.is_combat_unit()]
    for uid in to_remove:
        del gs.units[uid]
    result = check_italian_campaign_victory(gs)
    assert result.winner == Side.COMMONWEALTH
    assert result.level == VictoryLevel.STRATEGIC


def test_italian_campaign_vp_count():
    gs = build_grazianis_offensive()
    # Place CW at Tobruk (5 VP) and Benghazi (5 VP).
    _place_unit_at(gs, "cw.tobruk", Side.COMMONWEALTH, "Tobruk")
    _place_unit_at(gs, "cw.benghazi", Side.COMMONWEALTH, "Benghazi")
    result = check_italian_campaign_victory(gs)
    assert result.winner == Side.COMMONWEALTH
    assert "VP" in result.reason
