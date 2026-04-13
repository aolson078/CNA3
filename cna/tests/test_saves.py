"""Smoke tests for cna.engine.saves (JSON round-trip)."""

from __future__ import annotations

import json

import pytest

from cna.engine.game_state import (
    GameState,
    HexCoord,
    MapHex,
    OperationsStage,
    OrgSize,
    Phase,
    Player,
    Side,
    TerrainType,
    Unit,
    UnitClass,
    UnitStats,
    UnitType,
    WeatherState,
)
from cna.engine.saves import (
    SaveFormatError,
    SchemaVersionMismatch,
    from_json,
    load,
    save,
    to_json,
)


def _populated_state() -> GameState:
    gs = GameState()
    gs.scenario_id = "operation_compass"
    gs.game_turn = 3
    gs.operations_stage = OperationsStage.SECOND
    gs.phase = Phase.MOVEMENT_AND_COMBAT
    gs.active_side = Side.COMMONWEALTH
    gs.weather = WeatherState.SANDSTORM
    gs.players = {
        Side.AXIS: Player(side=Side.AXIS, name="Rommel", has_initiative=True),
        Side.COMMONWEALTH: Player(side=Side.COMMONWEALTH, name="O'Connor", is_player_a=True),
    }
    h1 = HexCoord(0, 0)
    h2 = HexCoord(1, 0)
    gs.map = {
        h1: MapHex(coord=h1, terrain=TerrainType.TOWN, name="Tobruk", port_capacity=4,
                   road_exits=frozenset({h2}), controller=Side.COMMONWEALTH),
        h2: MapHex(coord=h2, terrain=TerrainType.DESERT, road_exits=frozenset({h1})),
    }
    u = Unit(
        id="ax.21pz.hq",
        side=Side.AXIS,
        name="21st Panzer HQ",
        unit_type=UnitType.HEADQUARTERS,
        unit_class=UnitClass.ARMOR,
        org_size=OrgSize.DIVISION,
        stats=UnitStats(capability_point_allowance=10, basic_morale=2, max_toe_strength=12),
        position=h2,
        current_toe=10,
        current_morale=2,
        capability_points_spent=3,
    )
    gs.units = {u.id: u}
    gs.dice.seed = 42
    gs.turn_log = ["turn start", "weather clear"]
    gs.extras = {"ammo_pool": {"axis": 5, "cw": 3}}
    return gs


def test_roundtrip_preserves_scalar_fields():
    gs = _populated_state()
    restored = from_json(to_json(gs))
    assert restored.scenario_id == gs.scenario_id
    assert restored.game_turn == gs.game_turn
    assert restored.operations_stage == gs.operations_stage
    assert restored.phase == gs.phase
    assert restored.active_side == gs.active_side
    assert restored.weather == gs.weather


def test_roundtrip_preserves_players():
    gs = _populated_state()
    restored = from_json(to_json(gs))
    assert set(restored.players.keys()) == {Side.AXIS, Side.COMMONWEALTH}
    assert restored.players[Side.AXIS].name == "Rommel"
    assert restored.players[Side.AXIS].has_initiative is True
    assert restored.players[Side.COMMONWEALTH].is_player_a is True


def test_roundtrip_preserves_map():
    gs = _populated_state()
    restored = from_json(to_json(gs))
    assert set(restored.map.keys()) == set(gs.map.keys())
    tobruk = restored.map[HexCoord(0, 0)]
    assert tobruk.name == "Tobruk"
    assert tobruk.terrain == TerrainType.TOWN
    assert tobruk.port_capacity == 4
    assert HexCoord(1, 0) in tobruk.road_exits
    assert tobruk.controller == Side.COMMONWEALTH


def test_roundtrip_preserves_units():
    gs = _populated_state()
    restored = from_json(to_json(gs))
    assert list(restored.units.keys()) == ["ax.21pz.hq"]
    u = restored.units["ax.21pz.hq"]
    assert u.position == HexCoord(1, 0)
    assert u.stats.capability_point_allowance == 10
    assert u.current_toe == 10
    assert u.capability_points_spent == 3


def test_roundtrip_preserves_dice_seed_and_log():
    gs = _populated_state()
    gs.dice.roll(); gs.dice.roll_concat()
    before = list(gs.dice.roll_log)
    restored = from_json(to_json(gs))
    assert restored.dice.seed == gs.dice.seed
    # roll_log entries should round-trip (list of dicts of JSON-safe values).
    assert len(restored.dice.roll_log) == len(before)
    assert restored.dice.roll_log[0]["mode"] == before[0]["mode"]


def test_roundtrip_preserves_extras():
    gs = _populated_state()
    restored = from_json(to_json(gs))
    assert restored.extras == {"ammo_pool": {"axis": 5, "cw": 3}}


def test_schema_version_mismatch_rejected():
    gs = _populated_state()
    data = json.loads(to_json(gs))
    data["schema_version"] = 999
    with pytest.raises(SchemaVersionMismatch):
        from_json(json.dumps(data))


def test_invalid_json_raises_save_format_error():
    with pytest.raises(SaveFormatError):
        from_json("not json at all {")


def test_extras_with_non_json_raises():
    gs = _populated_state()
    gs.extras["bad"] = object()  # not JSON-serializable
    with pytest.raises(SaveFormatError):
        to_json(gs)


def test_save_and_load_to_disk(tmp_path):
    gs = _populated_state()
    path = tmp_path / "save.json"
    save(gs, path)
    restored = load(path)
    assert restored.scenario_id == gs.scenario_id
    assert restored.units["ax.21pz.hq"].name == "21st Panzer HQ"
