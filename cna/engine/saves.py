"""Save / load boundary — pydantic validation for GameState serialization.

Per CLAUDE.md convention:
  - Runtime state is plain @dataclass objects (cna/engine/game_state.py).
  - pydantic is used *only* at the save/load boundary.

This module:
  1. Defines pydantic models mirroring the dataclass schema.
  2. Converts dataclass <-> pydantic at the file boundary.
  3. Validates schema_version on load, raising on mismatch.

File format: JSON, with a top-level "schema_version" field used to detect
stale saves. When the schema changes, bump GameState.SCHEMA_VERSION and
add a migration path here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from cna.engine.dice import DiceRoller
from cna.engine.game_state import (
    CohesionLevel,
    GameState,
    HexCoord,
    LogEntry,
    MapHex,
    OperationsStage,
    Phase,
    Player,
    ReserveStatus,
    Side,
    TerrainType,
    Unit,
    UnitClass,
    UnitStats,
    UnitType,
    OrgSize,
    WeatherState,
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SaveFormatError(Exception):
    """Raised when a save file cannot be parsed or validated."""


class SchemaVersionMismatch(SaveFormatError):
    """Raised when a save file's schema_version is incompatible."""

    def __init__(self, found: int, expected: int):
        self.found = found
        self.expected = expected
        super().__init__(
            f"Save schema version {found} does not match current version {expected}"
        )


# ---------------------------------------------------------------------------
# Pydantic models (validation-only, not used at runtime)
# ---------------------------------------------------------------------------


class HexCoordModel(BaseModel):
    q: int
    r: int


class UnitStatsModel(BaseModel):
    capability_point_allowance: int = 0
    barrage_rating: int = 0
    vulnerability: int = 0
    anti_armor_strength: int = 0
    armor_protection_rating: int = 0
    offensive_close_assault: int = 0
    defensive_close_assault: int = 0
    anti_aircraft_rating: int = 0
    basic_morale: int = 0
    fuel_rate: int = 0
    breakdown_adjustment: int = 0
    max_toe_strength: int = 0


class UnitModel(BaseModel):
    id: str
    side: Side
    name: str
    unit_type: UnitType
    unit_class: UnitClass
    org_size: OrgSize
    stats: UnitStatsModel = Field(default_factory=UnitStatsModel)
    position: HexCoordModel | None = None
    parent_id: str | None = None
    attached_unit_ids: list[str] = Field(default_factory=list)
    current_toe: int = 0
    current_morale: int = 0
    cohesion: CohesionLevel = CohesionLevel.ORGANIZED
    reserve_status: ReserveStatus = ReserveStatus.NONE
    pinned: bool = False
    broken_down: bool = False
    capability_points_spent: int = 0
    is_motorized: bool = False


class MapHexModel(BaseModel):
    coord: HexCoordModel
    terrain: TerrainType = TerrainType.DESERT
    name: str = ""
    elevation: int = 0
    road_exits: list[HexCoordModel] = Field(default_factory=list)
    track_exits: list[HexCoordModel] = Field(default_factory=list)
    rail_exits: list[HexCoordModel] = Field(default_factory=list)
    has_airfield: bool = False
    has_landing_strip: bool = False
    has_flying_boat_basin: bool = False
    has_flying_boat_area: bool = False
    port_capacity: int = 0
    controller: Side | None = None


class PlayerModel(BaseModel):
    side: Side
    name: str = ""
    has_initiative: bool = False
    is_player_a: bool = False


class DiceRollerModel(BaseModel):
    seed: int = 0
    roll_log: list[dict[str, Any]] = Field(default_factory=list)


class LogEntryModel(BaseModel):
    seq: int
    turn: int
    stage: OperationsStage | None = None
    phase: Phase
    side: Side | None = None
    message: str
    category: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class GameStateModel(BaseModel):
    schema_version: int
    scenario_id: str = ""
    game_turn: int = 1
    operations_stage: OperationsStage = OperationsStage.FIRST
    phase: Phase = Phase.INITIATIVE_DETERMINATION
    active_side: Side = Side.AXIS
    weather: WeatherState = WeatherState.CLEAR
    players: list[PlayerModel] = Field(default_factory=list)
    map: list[MapHexModel] = Field(default_factory=list)
    units: list[UnitModel] = Field(default_factory=list)
    dice: DiceRollerModel = Field(default_factory=DiceRollerModel)
    turn_log: list[LogEntryModel] = Field(default_factory=list)
    extras: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------


def _coord_to_model(c: HexCoord) -> HexCoordModel:
    return HexCoordModel(q=c.q, r=c.r)


def _coord_from_model(m: HexCoordModel) -> HexCoord:
    return HexCoord(q=m.q, r=m.r)


def _unit_to_model(u: Unit) -> UnitModel:
    return UnitModel(
        id=u.id,
        side=u.side,
        name=u.name,
        unit_type=u.unit_type,
        unit_class=u.unit_class,
        org_size=u.org_size,
        stats=UnitStatsModel(**u.stats.__dict__),
        position=_coord_to_model(u.position) if u.position is not None else None,
        parent_id=u.parent_id,
        attached_unit_ids=list(u.attached_unit_ids),
        current_toe=u.current_toe,
        current_morale=u.current_morale,
        cohesion=u.cohesion,
        reserve_status=u.reserve_status,
        pinned=u.pinned,
        broken_down=u.broken_down,
        capability_points_spent=u.capability_points_spent,
        is_motorized=u.is_motorized,
    )


def _unit_from_model(m: UnitModel) -> Unit:
    return Unit(
        id=m.id,
        side=m.side,
        name=m.name,
        unit_type=m.unit_type,
        unit_class=m.unit_class,
        org_size=m.org_size,
        stats=UnitStats(**m.stats.model_dump()),
        position=_coord_from_model(m.position) if m.position is not None else None,
        parent_id=m.parent_id,
        attached_unit_ids=list(m.attached_unit_ids),
        current_toe=m.current_toe,
        current_morale=m.current_morale,
        cohesion=m.cohesion,
        reserve_status=m.reserve_status,
        pinned=m.pinned,
        broken_down=m.broken_down,
        capability_points_spent=m.capability_points_spent,
        is_motorized=m.is_motorized,
    )


def _hex_to_model(h: MapHex) -> MapHexModel:
    return MapHexModel(
        coord=_coord_to_model(h.coord),
        terrain=h.terrain,
        name=h.name,
        elevation=h.elevation,
        road_exits=[_coord_to_model(c) for c in h.road_exits],
        track_exits=[_coord_to_model(c) for c in h.track_exits],
        rail_exits=[_coord_to_model(c) for c in h.rail_exits],
        has_airfield=h.has_airfield,
        has_landing_strip=h.has_landing_strip,
        has_flying_boat_basin=h.has_flying_boat_basin,
        has_flying_boat_area=h.has_flying_boat_area,
        port_capacity=h.port_capacity,
        controller=h.controller,
    )


def _hex_from_model(m: MapHexModel) -> MapHex:
    return MapHex(
        coord=_coord_from_model(m.coord),
        terrain=m.terrain,
        name=m.name,
        elevation=m.elevation,
        road_exits=frozenset(_coord_from_model(c) for c in m.road_exits),
        track_exits=frozenset(_coord_from_model(c) for c in m.track_exits),
        rail_exits=frozenset(_coord_from_model(c) for c in m.rail_exits),
        has_airfield=m.has_airfield,
        has_landing_strip=m.has_landing_strip,
        has_flying_boat_basin=m.has_flying_boat_basin,
        has_flying_boat_area=m.has_flying_boat_area,
        port_capacity=m.port_capacity,
        controller=m.controller,
    )


def _state_to_model(state: GameState) -> GameStateModel:
    return GameStateModel(
        schema_version=state.schema_version,
        scenario_id=state.scenario_id,
        game_turn=state.game_turn,
        operations_stage=state.operations_stage,
        phase=state.phase,
        active_side=state.active_side,
        weather=state.weather,
        players=[
            PlayerModel(
                side=p.side,
                name=p.name,
                has_initiative=p.has_initiative,
                is_player_a=p.is_player_a,
            )
            for p in state.players.values()
        ],
        map=[_hex_to_model(h) for h in state.map.values()],
        units=[_unit_to_model(u) for u in state.units.values()],
        dice=DiceRollerModel(seed=state.dice.seed, roll_log=list(state.dice.roll_log)),
        turn_log=[_log_to_model(e) for e in state.turn_log],
        extras=_coerce_extras(state.extras),
    )


def _log_to_model(e: LogEntry) -> LogEntryModel:
    return LogEntryModel(
        seq=e.seq,
        turn=e.turn,
        stage=e.stage,
        phase=e.phase,
        side=e.side,
        message=e.message,
        category=e.category,
        data=_coerce_extras(e.data),
    )


def _log_from_model(m: LogEntryModel) -> LogEntry:
    return LogEntry(
        seq=m.seq,
        turn=m.turn,
        stage=m.stage,
        phase=m.phase,
        side=m.side,
        message=m.message,
        category=m.category,
        data=dict(m.data),
    )


def _state_from_model(m: GameStateModel) -> GameState:
    dice = DiceRoller(seed=m.dice.seed)
    dice.roll_log = list(m.dice.roll_log)
    state = GameState(
        schema_version=m.schema_version,
        scenario_id=m.scenario_id,
        game_turn=m.game_turn,
        operations_stage=m.operations_stage,
        phase=m.phase,
        active_side=m.active_side,
        weather=m.weather,
        players={p.side: Player(
            side=p.side, name=p.name, has_initiative=p.has_initiative, is_player_a=p.is_player_a
        ) for p in m.players},
        map={_coord_from_model(h.coord): _hex_from_model(h) for h in m.map},
        units={u.id: _unit_from_model(u) for u in m.units},
        dice=dice,
        turn_log=[_log_from_model(e) for e in m.turn_log],
        extras=dict(m.extras),
    )
    return state


def _coerce_extras(extras: dict[str, object]) -> dict[str, Any]:
    """Ensure extras is JSON-serializable.

    Rules modules stash per-game bookkeeping in GameState.extras. This
    boundary enforces that whatever they put there round-trips through
    JSON; objects that don't serialize raise SaveFormatError here rather
    than silently corrupting saves.
    """
    try:
        json.dumps(extras)
    except TypeError as exc:
        raise SaveFormatError(f"GameState.extras contains non-JSON value: {exc}") from exc
    return dict(extras)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def to_json(state: GameState) -> str:
    """Serialize *state* to a JSON string."""
    model = _state_to_model(state)
    return model.model_dump_json(indent=2)


def from_json(data: str | bytes) -> GameState:
    """Parse a JSON string/bytes into a GameState.

    Raises:
        SaveFormatError: if parsing fails.
        SchemaVersionMismatch: if schema_version is unexpected.
    """
    try:
        raw = json.loads(data)
    except json.JSONDecodeError as exc:
        raise SaveFormatError(f"Invalid JSON: {exc}") from exc

    found = raw.get("schema_version")
    if found != GameState.SCHEMA_VERSION:
        raise SchemaVersionMismatch(
            found=found if isinstance(found, int) else -1,
            expected=GameState.SCHEMA_VERSION,
        )

    try:
        model = GameStateModel.model_validate(raw)
    except ValidationError as exc:
        raise SaveFormatError(f"Save validation failed: {exc}") from exc

    return _state_from_model(model)


def save(state: GameState, path: str | Path) -> None:
    """Write *state* to *path* as JSON."""
    Path(path).write_text(to_json(state), encoding="utf-8")


def load(path: str | Path) -> GameState:
    """Load a GameState from *path*.

    Raises:
        SaveFormatError / SchemaVersionMismatch on bad data.
    """
    return from_json(Path(path).read_text(encoding="utf-8"))
