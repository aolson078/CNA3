"""CNA engine package.

Core engine modules:
  - dice: Seeded dice rolling (Case 4.0).
  - errors: RuleViolationError (all rule violations).
  - game_state: Runtime dataclasses (Case 2.0, 3.0).
  - hex_map: Hex geometry (Case 4.0).
  - sequence_of_play: Phase driver (Case 5.2).
  - saves: JSON save/load boundary.
"""

from cna.engine.dice import DiceRoller
from cna.engine.errors import RuleViolationError
from cna.engine.game_state import (
    CohesionLevel,
    GameState,
    HexCoord,
    LogEntry,
    MapHex,
    OperationsStage,
    OrgSize,
    Phase,
    Player,
    ReserveStatus,
    Side,
    TerrainType,
    Unit,
    UnitClass,
    UnitStats,
    UnitType,
    WeatherState,
)
from cna.engine.hex_map import HexMap, distance, hex_range, hex_ring, is_adjacent, neighbors
from cna.engine.sequence_of_play import PhaseDriver, PhaseStep, next_phase, phases_this_turn

__all__ = [
    "CohesionLevel",
    "DiceRoller",
    "GameState",
    "HexCoord",
    "HexMap",
    "LogEntry",
    "MapHex",
    "OperationsStage",
    "OrgSize",
    "Phase",
    "PhaseDriver",
    "PhaseStep",
    "Player",
    "ReserveStatus",
    "RuleViolationError",
    "Side",
    "TerrainType",
    "Unit",
    "UnitClass",
    "UnitStats",
    "UnitType",
    "WeatherState",
    "distance",
    "hex_range",
    "hex_ring",
    "is_adjacent",
    "neighbors",
    "next_phase",
    "phases_this_turn",
]
