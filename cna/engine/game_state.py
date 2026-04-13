"""Section 2.0, 3.0 — Core game state dataclasses.

This module defines the runtime data model for CNA. Per project convention
(CLAUDE.md), runtime state is plain @dataclass objects; pydantic is used
only at the save/load boundary (see cna/engine/saves.py).

The dataclasses here encode the minimum structure required to drive the
Land Game spine (Sections 5-11). Rule-specific details (barrage ratings,
TOE log sheets, supply categories, etc.) are attached as additional fields
in later sections and are deliberately kept sparse here.

Cross-references:
  - Unit characteristics: Case 3.5
  - Unit classes (Infantry/Armor/Gun/Truck): Case 3.22
  - Headquarters semantics: Cases 3.3-3.36
  - Limited intelligence: Case 3.6
  - Sequence of play phases: Case 5.2
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from cna.engine.dice import DiceRoller


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Side(str, Enum):
    """The two sides in CNA.

    Case 3.1 — The Axis and Commonwealth are the two opposing Players.
    """

    AXIS = "axis"
    COMMONWEALTH = "commonwealth"


class UnitClass(str, Enum):
    """Target classes used by Barrage and Bombardment resolution.

    Case 3.22 — Infantry-class, Armor-class, Gun-class, Truck-class.
    """

    INFANTRY = "infantry"
    ARMOR = "armor"
    GUN = "gun"
    TRUCK = "truck"


class UnitType(str, Enum):
    """Unit type categories.

    Case 3.21 — Infantry, Tank, Recce, Artillery, Anti-Tank, Anti-Aircraft,
    Headquarters, Engineers, Tank Recovery Squadrons, SGSU, Dummy Tank
    Formations, Trucks.
    """

    INFANTRY = "infantry"
    TANK = "tank"
    RECCE = "recce"
    ARTILLERY = "artillery"
    ANTI_TANK = "anti_tank"
    ANTI_AIRCRAFT = "anti_aircraft"
    HEADQUARTERS = "headquarters"
    ENGINEER = "engineer"
    TANK_RECOVERY = "tank_recovery"
    SGSU = "sgsu"
    DUMMY_TANK = "dummy_tank"
    TRUCK = "truck"


class OrgSize(str, Enum):
    """Organization-Size of a unit.

    Case 3.1 — Division, Brigade, Battalion, Company equivalents.
    """

    DIVISION = "division"
    BRIGADE = "brigade"
    BATTALION = "battalion"
    COMPANY = "company"


class Phase(str, Enum):
    """Phases of a single Operations Stage.

    Case 5.2 — The Land Game Sequence of Play. Stage-level phases
    (Initiative, Naval Convoy) are handled separately; this enum covers
    the per-Operations-Stage phases that cycle between Player A and B.
    """

    # Stage-level (once per Game-Turn / per Stage)
    INITIATIVE_DETERMINATION = "initiative_determination"  # Stage I
    NAVAL_CONVOY_SCHEDULE = "naval_convoy_schedule"  # Stage II.A
    TACTICAL_SHIPPING = "tactical_shipping"  # Stage II.B

    # Per Operations Stage
    INITIATIVE_DECLARATION = "initiative_declaration"  # III.A
    WEATHER_DETERMINATION = "weather_determination"  # III.B
    ORGANIZATION = "organization"  # III.C
    NAVAL_CONVOY_ARRIVAL = "naval_convoy_arrival"  # III.D
    COMMONWEALTH_FLEET = "commonwealth_fleet"  # III.E
    RESERVE_DESIGNATION = "reserve_designation"  # III.F
    MOVEMENT_AND_COMBAT = "movement_and_combat"  # III.G
    TRUCK_CONVOY = "truck_convoy"  # III.H
    RAIL_MOVEMENT = "rail_movement"  # III.J (Commonwealth only)
    REPAIR = "repair"  # III.K
    PATROL = "patrol"  # III.L

    END_OF_TURN = "end_of_turn"  # VI


class OperationsStage(int, Enum):
    """Each Game-Turn has three Operations Stages.

    Case 5.1 — Three Operations Stages per Game-Turn (each ~2-3 days).
    """

    FIRST = 1
    SECOND = 2
    THIRD = 3


class CohesionLevel(str, Enum):
    """Unit combat effectiveness level.

    Case 3.1 — Cohesion is affected by Reorganization and Disorganization
    Points (see Section 19.0).
    """

    ORGANIZED = "organized"
    DISORGANIZED = "disorganized"
    SHATTERED = "shattered"


class ReserveStatus(str, Enum):
    """Reserve status of a unit.

    Case 18.0 — Reserve I (first-level) and Reserve II (second-level).
    """

    NONE = "none"
    RESERVE_I = "reserve_i"
    RESERVE_II = "reserve_ii"


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HexCoord:
    """Axial hex coordinate.

    Case 4.0 — The map uses a hex grid. We store axial (q, r) coordinates;
    see cna/engine/hex_map.py for neighbor and distance math.
    """

    q: int
    r: int

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"Hex({self.q},{self.r})"


# ---------------------------------------------------------------------------
# Units
# ---------------------------------------------------------------------------


@dataclass
class UnitStats:
    """Combat ratings for a Unit.

    Case 3.5 — Unit characteristics printed on the counter / TOE log sheet.
    Ratings default to zero; a specific unit populates only those relevant
    to its type. Parenthesized ratings (Case 3.4 clarification) are tracked
    as a separate flag per rating on the attached TOE record when needed.
    """

    capability_point_allowance: int = 0  # CPA, Case 3.5
    barrage_rating: int = 0  # Case 12.0
    vulnerability: int = 0  # Case 12.1
    anti_armor_strength: int = 0  # Case 14.0
    armor_protection_rating: int = 0  # Case 14.0
    offensive_close_assault: int = 0  # Case 15.0
    defensive_close_assault: int = 0  # Case 15.0
    anti_aircraft_rating: int = 0  # Case 41.0
    basic_morale: int = 0  # Case 17.0 (-3 .. +3)
    fuel_rate: int = 0  # Case 3.5
    breakdown_adjustment: int = 0  # Case 21.0
    max_toe_strength: int = 0  # Case 4.46


@dataclass
class Unit:
    """A game-map counter.

    Case 3.1 — "A counter capable of expending Capability Points."
    Case 3.5 — Unit characteristics.
    Case 3.3 — HQs represent attached subsidiary units.

    Attributes:
        id: Stable identifier (e.g. "axis.21pz.hq").
        side: Owning side.
        name: Display name (e.g. "21st Panzer Division HQ").
        unit_type: Primary type (Case 3.21).
        unit_class: Target class for barrage (Case 3.22).
        org_size: Organization-Size (Case 3.1).
        stats: Combat/capability ratings (Case 3.5).
        position: Current hex, or None if off-map (reinforcement pool).
        parent_id: ID of parent Unit if assigned (Case 3.1 "Assigned").
        attached_unit_ids: IDs of units attached (Case 3.1 "Attached").
        current_toe: Present TOE Strength Points (Case 4.46). <= stats.max_toe_strength.
        current_morale: Current morale, may exceed basic via success (Case 17.0).
        cohesion: Cohesion level (Case 3.1 / Section 19.0).
        reserve_status: Reserve marker (Case 18.0).
        pinned: Pinned by barrage/air bombardment (Case 3.1 / Case 41.9).
        broken_down: Vehicle Breakdown marker (Case 21.0).
        capability_points_spent: CP spent this Operations Stage (Case 6.0).
        is_motorized: Currently moving via truck/vehicle transport (Case 3.4).
    """

    id: str
    side: Side
    name: str
    unit_type: UnitType
    unit_class: UnitClass
    org_size: OrgSize
    stats: UnitStats = field(default_factory=UnitStats)

    position: Optional[HexCoord] = None
    parent_id: Optional[str] = None
    attached_unit_ids: list[str] = field(default_factory=list)

    current_toe: int = 0
    current_morale: int = 0
    cohesion: CohesionLevel = CohesionLevel.ORGANIZED
    reserve_status: ReserveStatus = ReserveStatus.NONE
    pinned: bool = False
    broken_down: bool = False
    capability_points_spent: int = 0
    is_motorized: bool = False

    def remaining_cp(self) -> int:
        """CP remaining this Operations Stage (Case 6.0)."""
        return max(0, self.stats.capability_point_allowance - self.capability_points_spent)

    def is_combat_unit(self) -> bool:
        """Case 3.23 — Combat-unit classification.

        Infantry, Tank, Recce, Artillery, Anti-Tank, and Anti-Aircraft
        units are always combat units. HQs and Engineers are combat units
        "in certain situations" (Case 3.22, Case 3.31); we return True for
        an HQ when it has combat units attached.
        """
        if self.unit_type in {
            UnitType.INFANTRY,
            UnitType.TANK,
            UnitType.RECCE,
            UnitType.ARTILLERY,
            UnitType.ANTI_TANK,
            UnitType.ANTI_AIRCRAFT,
            UnitType.ENGINEER,
        }:
            return True
        if self.unit_type == UnitType.HEADQUARTERS:
            return bool(self.attached_unit_ids)
        return False


# ---------------------------------------------------------------------------
# Map hex
# ---------------------------------------------------------------------------


class TerrainType(str, Enum):
    """Terrain types found on the CNA map.

    Case 8.0 / Case 29.0 — Terrain affects movement and combat. The full
    list is fleshed out in cna/engine/hex_map.py; here we enumerate the
    gross categories needed for the engine spine.
    """

    DESERT = "desert"
    ROUGH = "rough"
    ESCARPMENT = "escarpment"
    MOUNTAIN = "mountain"
    SALT_MARSH = "salt_marsh"
    DEPRESSION = "depression"
    OASIS = "oasis"
    TOWN = "town"
    CITY = "city"
    PORT = "port"
    SEA = "sea"
    IMPASSABLE = "impassable"


@dataclass
class MapHex:
    """A single hex on the game map.

    Case 4.0 — Hex attributes. Terrain details, road/track connections,
    improvements (fortifications, minefields, airfields), and control are
    tracked per-hex.

    Attributes:
        coord: Axial hex coordinate.
        terrain: Primary terrain type.
        name: Named feature (e.g. "Tobruk"), if any.
        elevation: Elevation in meters (for line of sight later).
        road_exits: Axial neighbor coords with road connections.
        track_exits: Axial neighbor coords with track connections.
        rail_exits: Axial neighbor coords with rail connections.
        has_airfield: Large airbase (Case 3.1 "Air Facility").
        has_landing_strip: Small airbase.
        has_flying_boat_basin: Large flying-boat base.
        has_flying_boat_area: Small flying-boat base.
        port_capacity: Port capacity if this is a port hex (Case 30.0), else 0.
        controller: Side currently controlling the hex, or None if contested/neutral.
    """

    coord: HexCoord
    terrain: TerrainType = TerrainType.DESERT
    name: str = ""
    elevation: int = 0
    road_exits: frozenset[HexCoord] = field(default_factory=frozenset)
    track_exits: frozenset[HexCoord] = field(default_factory=frozenset)
    rail_exits: frozenset[HexCoord] = field(default_factory=frozenset)
    has_airfield: bool = False
    has_landing_strip: bool = False
    has_flying_boat_basin: bool = False
    has_flying_boat_area: bool = False
    port_capacity: int = 0
    controller: Optional[Side] = None


# ---------------------------------------------------------------------------
# Weather
# ---------------------------------------------------------------------------


class WeatherState(str, Enum):
    """Weather states (Case 29.0)."""

    CLEAR = "clear"
    OVERCAST = "overcast"
    RAIN = "rain"
    SANDSTORM = "sandstorm"


# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------


@dataclass
class Player:
    """A game player.

    Attributes:
        side: Which side this player controls.
        name: Display name.
        has_initiative: True if this player holds the Initiative for the
            current Game-Turn (Case 7.0).
        is_player_a: True if this player is designated "A" for the current
            Operations Stage (Case 5.2 III.A).
    """

    side: Side
    name: str = ""
    has_initiative: bool = False
    is_player_a: bool = False


# ---------------------------------------------------------------------------
# GameState
# ---------------------------------------------------------------------------


@dataclass
class GameState:
    """Top-level runtime state for a CNA game.

    Case 2.0 — Minimal container for all per-game information. Larger
    subsystems (full logistics ledger, air game state, TOE log sheets)
    attach their own structures via the `extras` dict until they are
    promoted to first-class fields by a later section's encoding.

    Attributes:
        schema_version: Bumped whenever on-disk save format changes.
        scenario_id: Which scenario is being played (Sections 60-65).
        game_turn: 1-indexed Game-Turn number (Case 5.1).
        operations_stage: Which of the three stages we are in (Case 5.1).
        phase: Current phase within the current stage (Case 5.2).
        active_side: Side whose phase it is right now.
        weather: Current weather (Case 29.0).
        players: Players keyed by side.
        map: All hexes keyed by coord.
        units: All units (on-map and off-map) keyed by id.
        dice: Seeded dice roller (deterministic replay).
        turn_log: Human-readable log of significant events.
        extras: Untyped bag for rules modules to stash per-game bookkeeping.
    """

    SCHEMA_VERSION: int = 1

    schema_version: int = SCHEMA_VERSION
    scenario_id: str = ""
    game_turn: int = 1
    operations_stage: OperationsStage = OperationsStage.FIRST
    phase: Phase = Phase.INITIATIVE_DETERMINATION
    active_side: Side = Side.AXIS
    weather: WeatherState = WeatherState.CLEAR
    players: dict[Side, Player] = field(default_factory=dict)
    map: dict[HexCoord, MapHex] = field(default_factory=dict)
    units: dict[str, Unit] = field(default_factory=dict)
    dice: DiceRoller = field(default_factory=DiceRoller)
    turn_log: list[str] = field(default_factory=list)
    extras: dict[str, object] = field(default_factory=dict)

    # -- accessors -------------------------------------------------------

    def units_on_side(self, side: Side) -> list[Unit]:
        """All units belonging to *side* (on-map and off-map)."""
        return [u for u in self.units.values() if u.side == side]

    def units_at(self, coord: HexCoord) -> list[Unit]:
        """All units currently stacked at *coord*."""
        return [u for u in self.units.values() if u.position == coord]

    def enemy(self, side: Side) -> Side:
        """The opposing side."""
        return Side.COMMONWEALTH if side == Side.AXIS else Side.AXIS

    def player(self, side: Side) -> Player:
        """Fetch the Player for *side*, raising if unconfigured."""
        try:
            return self.players[side]
        except KeyError as exc:  # pragma: no cover - defensive
            raise LookupError(f"No player configured for side {side}") from exc

    def log(self, message: str) -> None:
        """Append a line to the turn log."""
        self.turn_log.append(message)
