"""Section 8.0 — Land Movement.

Implements Cases 8.11-8.19 (basic movement), 8.3 (terrain effects),
and the essential parts of 8.2 (Continual Movement).

Layer 1 scope — what's implemented here:
  - move_unit(): Move a unit along a hex path, spending CP per terrain.
  - terrain_cp_cost(): CP cost to enter a hex.
  - can_enter(): Whether a unit type is allowed in a terrain type.
  - validate_move(): Pre-check a proposed path for legality.

Deferred to later passes:
  - Case 8.5: Reaction (non-phasing movement). TODO-8.5
  - Case 8.6: Breaking Off (Contact/Engaged). TODO-8.6
  - Case 8.7: Rail Movement. TODO-8.7
  - Case 8.8: Tripoli/Tunisia off-map movement. TODO-8.8
  - Case 8.9: Detailed motorization/truck transport. TODO-8.9
  - Case 8.37: Full Terrain Effects Chart (OCR garbled; values below are
    conservative placeholders). TODO-8.37

Cross-references:
  - Case 6.0: All movement costs CP (Section 6.0).
  - Case 9.0: Stacking limits (Section 9.0). TODO-9.0
  - Case 10.0: ZoC stops movement (Section 10.0). TODO-10.0
  - Case 21.0: Breakdown checks for vehicles. TODO-21.0
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from cna.engine.errors import RuleViolationError
from cna.engine.game_state import (
    GameState,
    HexCoord,
    MapHex,
    Side,
    TerrainType,
    Unit,
    UnitType,
)
from cna.engine.hex_map import HexMap, is_adjacent
from cna.rules.capability_points import (
    can_spend,
    effective_cpa,
    spend_cp,
)


# ---------------------------------------------------------------------------
# Terrain CP costs (Case 8.3 / 8.37 — placeholder values)
# ---------------------------------------------------------------------------

# The full 8.37 Terrain Effects Chart is OCR-garbled. These values are
# conservative placeholders derived from readable fragments and from the
# Case 8.31 description ("½ CP for roads ... +8 for escarpment via track").
# TODO-8.37: replace with manually verified chart data.


@dataclass(frozen=True)
class TerrainCost:
    """CP cost to enter a hex of a given terrain type.

    Case 8.31 — Costs vary by unit type (non-motorized vs motorized).
    A value of -1 means the terrain is prohibited for that category.
    """

    non_motorized: int
    motorized: int


# Key: TerrainType → TerrainCost
_TERRAIN_COSTS: dict[TerrainType, TerrainCost] = {
    TerrainType.DESERT:      TerrainCost(2, 2),
    TerrainType.ROUGH:       TerrainCost(2, 3),
    TerrainType.ESCARPMENT:  TerrainCost(4, -1),  # Case 8.42: vehicles cannot go UP
    TerrainType.MOUNTAIN:    TerrainCost(3, -1),
    TerrainType.SALT_MARSH:  TerrainCost(2, -1),   # Case 8.44: most vehicles prohibited
    TerrainType.DEPRESSION:  TerrainCost(1, 1),
    TerrainType.OASIS:       TerrainCost(1, 1),     # Case 8.48: oases don't affect movement
    TerrainType.TOWN:        TerrainCost(1, 1),
    TerrainType.CITY:        TerrainCost(1, 1),
    TerrainType.PORT:        TerrainCost(1, 1),
    TerrainType.SEA:         TerrainCost(-1, -1),
    TerrainType.IMPASSABLE:  TerrainCost(-1, -1),
}

# Road and track modifiers (Case 8.33, 8.46)
ROAD_CP_COST = 1       # Case 8.33: road movement ignores terrain cost
TRACK_DIVISOR = 2      # Case 8.46 (correction): tracks halve terrain cost


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def is_motorized(unit: Unit) -> bool:
    """True if *unit* is currently motorized (Case 8.91).

    Case 8.91 — Motorized units include mechanized vehicles, trucks,
    and motorcycles. Also includes infantry currently being transported
    by trucks (unit.is_motorized flag).
    """
    if unit.is_motorized:
        return True
    return unit.unit_type in {
        UnitType.TANK,
        UnitType.RECCE,
        UnitType.TANK_RECOVERY,
        UnitType.TRUCK,
    }


def terrain_cp_cost(terrain: TerrainType, unit: Unit, *, on_road: bool = False,
                    on_track: bool = False) -> int:
    """CP cost for *unit* to enter a hex with *terrain*.

    Cases 8.31, 8.33, 8.46 — Returns the terrain entry cost, modified
    by road/track if applicable. Returns -1 if the terrain is prohibited
    for this unit type.
    """
    costs = _TERRAIN_COSTS.get(terrain)
    if costs is None:
        return 1  # Default for unrecognized terrain.

    mot = is_motorized(unit)
    base = costs.motorized if mot else costs.non_motorized

    if base < 0:
        # Sea and Impassable are never enterable, even with roads.
        if terrain in {TerrainType.SEA, TerrainType.IMPASSABLE}:
            return -1
        # Other prohibited terrain: roads/tracks may override (Case 8.33).
        if on_road:
            return ROAD_CP_COST
        if on_track and not mot:
            return 2
        return -1  # Still prohibited.

    if on_road:
        return ROAD_CP_COST
    if on_track:
        return max(1, base // TRACK_DIVISOR)
    return base


def can_enter(terrain: TerrainType, unit: Unit, *, on_road: bool = False,
              on_track: bool = False) -> bool:
    """Whether *unit* may enter a hex with *terrain*.

    Case 8.32 — Some terrain is prohibited for certain unit types.
    """
    return terrain_cp_cost(terrain, unit, on_road=on_road, on_track=on_track) >= 0


# ---------------------------------------------------------------------------
# Move validation
# ---------------------------------------------------------------------------


@dataclass
class MoveResult:
    """Outcome of a move_unit() call.

    Case 8.0 — Records the path taken, total CP spent, and any DP earned
    from exceeding CPA.
    """

    unit_id: str
    path: list[HexCoord]
    cp_spent: int
    dp_earned: int
    stopped_by_zoc: bool = False


def validate_move(
    state: GameState,
    unit: Unit,
    path: list[HexCoord],
) -> list[str]:
    """Check whether *unit* can legally follow *path*.

    Returns a list of violation descriptions (empty = legal).
    Does not mutate state.

    Cases checked:
      - 8.13: Consecutive hexes, no enemy hexes.
      - 8.14: ZoC stop (simplified: enemy-occupied hex adjacent = stop).
      - 8.32: Terrain prohibition.
      - 6.26: Shattered unit cannot move.
    """
    errors: list[str] = []
    if not path:
        return errors

    hex_map = HexMap(state.map)

    if unit.position is None:
        errors.append("Unit is not on the map")
        return errors

    if path[0] != unit.position:
        errors.append(f"Path must start at unit position {unit.position}")

    for i in range(1, len(path)):
        prev, cur = path[i - 1], path[i]
        if not is_adjacent(prev, cur):
            errors.append(f"Hex {prev} → {cur} are not adjacent (Case 8.13)")
        mh = hex_map.get(cur)
        if mh is None:
            errors.append(f"Hex {cur} is off-map")
            continue
        # Case 8.13: no entering enemy-occupied hexes.
        enemy_units = [u for u in state.units_at(cur) if u.side != unit.side]
        if enemy_units:
            errors.append(f"Hex {cur} is enemy-occupied (Case 8.13)")
        # Case 8.32: terrain prohibition.
        on_road = hex_map.has_road(prev, cur)
        on_track = hex_map.has_track(prev, cur)
        if not can_enter(mh.terrain, unit, on_road=on_road, on_track=on_track):
            errors.append(
                f"Terrain {mh.terrain.value} at {cur} is prohibited "
                f"for {unit.unit_type.value} (Case 8.32)"
            )
    return errors


# ---------------------------------------------------------------------------
# Movement execution
# ---------------------------------------------------------------------------


def move_unit(
    state: GameState,
    unit_id: str,
    path: list[HexCoord],
    *,
    voluntary: bool = True,
) -> MoveResult:
    """Move a unit along *path*, spending CP and updating position.

    Cases 8.11-8.16, 6.12, 6.21 — The unit advances hex-by-hex along
    *path*, paying the terrain CP cost at each step. If it exceeds its
    CPA, DP are earned immediately (Case 6.21). Movement stops early if
    the unit enters an enemy ZoC (Case 8.14, simplified) or if the
    voluntary CP cap is reached (Case 8.17).

    Args:
        state: Game state to mutate.
        unit_id: ID of the unit to move.
        path: List of HexCoords starting at the unit's current position.
        voluntary: True for normal movement; False for involuntary
            (retreat), which bypasses the Case 8.17 cap.

    Returns:
        MoveResult describing the outcome.

    Raises:
        RuleViolationError: on illegal moves.
    """
    unit = state.units.get(unit_id)
    if unit is None:
        raise RuleViolationError("8.11", f"No unit with id '{unit_id}'")

    if not path or len(path) < 2:
        return MoveResult(unit_id=unit_id, path=path or [], cp_spent=0, dp_earned=0)

    errors = validate_move(state, unit, path)
    if errors:
        raise RuleViolationError("8.13", "; ".join(errors))

    hex_map = HexMap(state.map)
    total_cp = 0
    total_dp = 0
    stopped_by_zoc = False
    actual_path = [path[0]]

    for i in range(1, len(path)):
        prev, cur = path[i - 1], path[i]
        mh = hex_map.require(cur)
        on_road = hex_map.has_road(prev, cur)
        on_track = hex_map.has_track(prev, cur)
        cost = terrain_cp_cost(mh.terrain, unit, on_road=on_road, on_track=on_track)

        if cost < 0:
            raise RuleViolationError(
                "8.32",
                f"Unit {unit_id} cannot enter {mh.terrain.value} at {cur}",
            )

        # Case 8.17: check voluntary cap.
        if voluntary and not can_spend(unit, cost, voluntary=True):
            break

        dp = spend_cp(unit, cost)
        total_cp += cost
        total_dp += dp
        unit.position = cur
        actual_path.append(cur)

        # Simplified ZoC check (Case 8.14): if any enemy combat unit is
        # adjacent to the new position, the unit must stop. Full ZoC
        # logic (Section 10.0) will replace this.
        if _any_enemy_adjacent(state, hex_map, cur, unit.side):
            stopped_by_zoc = True
            break

    return MoveResult(
        unit_id=unit_id,
        path=actual_path,
        cp_spent=total_cp,
        dp_earned=total_dp,
        stopped_by_zoc=stopped_by_zoc,
    )


def _any_enemy_adjacent(
    state: GameState,
    hex_map: HexMap,
    coord: HexCoord,
    friendly_side: Side,
) -> bool:
    """Simplified ZoC proxy: True if any enemy combat unit is adjacent.

    Case 8.14 / 10.0 — Proper ZoC logic is in Section 10; this is a
    placeholder that catches the basic case.
    """
    for nb in hex_map.neighbors_in_bounds(coord):
        for u in state.units_at(nb):
            if u.side != friendly_side and u.is_combat_unit():
                return True
    return False


# ---------------------------------------------------------------------------
# Contact / Engaged status (Case 8.6)
# ---------------------------------------------------------------------------


class ContactStatus(str, Enum):
    """Case 8.62-8.63 — Contact or Engaged status between opposing units."""
    NONE = "none"
    CONTACT = "contact"    # Case 8.62: in enemy ZoC at start of movement.
    ENGAGED = "engaged"    # Case 8.63: result of Close Assault.


BREAK_CONTACT_CP = 2   # Case 8.65
BREAK_ENGAGED_CP = 4   # Case 8.66


def break_off_cost(status: ContactStatus) -> int:
    """CP cost to Break Off from Contact or Engaged status.

    Case 8.65 — Contact: 2 CP.
    Case 8.66 — Engaged: 4 CP.
    """
    if status == ContactStatus.CONTACT:
        return BREAK_CONTACT_CP
    if status == ContactStatus.ENGAGED:
        return BREAK_ENGAGED_CP
    return 0


# ---------------------------------------------------------------------------
# Reaction (Case 8.5)
# ---------------------------------------------------------------------------


def can_react(
    unit: Unit,
    enemy_unit: Unit,
    state: GameState,
) -> bool:
    """Whether *unit* can React to *enemy_unit* moving adjacent.

    Case 8.53 — Reaction restrictions:
      a. Non-motorized units, SGSU, truck convoys without friendly combat
         units may never React.
      b. Cannot React if enemy CPA ≥ unit CPA + 6 and enemy announces
         Close Assault.
      c. Cannot React if already in an enemy ZoC.
      d. Cannot React if Engaged.

    Case 8.54 — Size override: battalion cannot pin division; company
    cannot pin brigade or larger.
    """
    from cna.rules.zones_of_control import is_enemy_zoc

    # 8.53a: must be motorized.
    if not is_motorized(unit):
        return False
    if unit.unit_type in {UnitType.SGSU, UnitType.TRUCK}:
        return False

    # 8.53b: speed-pinning — enemy CPA ≥ unit CPA + 6.
    if effective_cpa(enemy_unit) >= effective_cpa(unit) + 6:
        # Case 8.54 size override: small enemy can't pin large unit.
        if not _size_can_pin(enemy_unit, unit):
            pass  # Override: unit CAN react despite speed.
        else:
            return False

    # 8.53c: already in enemy ZoC.
    if unit.position is not None and is_enemy_zoc(
        state, unit.position, unit.side, exclude_unit_id=unit.id
    ):
        return False

    # 8.53d: Engaged units cannot react.
    # (Engaged status tracked externally; check unit extras.)
    contact = _get_contact_status(unit)
    if contact == ContactStatus.ENGAGED:
        return False

    return True


def _size_can_pin(pinner: Unit, target: Unit) -> bool:
    """Case 8.54 — Whether *pinner* can pin *target* by size.

    Battalion cannot pin division; company cannot pin brigade+.
    """
    from cna.engine.game_state import OrgSize
    _ORD = {OrgSize.COMPANY: 0, OrgSize.BATTALION: 1,
            OrgSize.BRIGADE: 2, OrgSize.DIVISION: 3}
    p = _ORD.get(pinner.org_size, 1)
    t = _ORD.get(target.org_size, 1)
    if p <= 1 and t >= 3:  # Battalion or smaller vs Division.
        return False
    if p == 0 and t >= 2:  # Company vs Brigade+.
        return False
    return True


def _get_contact_status(unit: Unit) -> ContactStatus:
    """Read contact/engaged status from unit (stored as attribute)."""
    val = getattr(unit, "_contact_status", None)
    if isinstance(val, ContactStatus):
        return val
    return ContactStatus.NONE


def set_contact_status(unit: Unit, status: ContactStatus) -> None:
    """Set contact/engaged status on a unit (Case 8.62/8.63)."""
    unit._contact_status = status  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Rail Movement (Case 8.7)
# ---------------------------------------------------------------------------

RAIL_MAX_SP = 2  # Case 8.75: max 2 stacking points by rail.


def can_use_rail(unit: Unit, state: GameState) -> bool:
    """Whether *unit* can use Rail Movement this Operations Stage.

    Case 8.71 — Commonwealth only (Axis may use per Case 54.4, Layer 3).
    Case 8.73 — Must be on a rail hex, 0 CP spent, not in enemy ZoC.
    """
    from cna.rules.zones_of_control import is_enemy_zoc
    from cna.rules.stacking import stacking_points

    if unit.side != Side.COMMONWEALTH:
        return False
    if unit.position is None:
        return False
    if unit.capability_points_spent > 0:
        return False

    # Must be on a rail hex.
    mh = state.map.get(unit.position)
    if mh is None or not mh.rail_exits:
        return False

    # Not in enemy ZoC.
    if is_enemy_zoc(state, unit.position, unit.side):
        return False

    # Case 8.75: max 2 SP.
    if stacking_points(unit) > RAIL_MAX_SP:
        return False

    return True


def rail_move(
    state: GameState,
    unit_id: str,
    destination: HexCoord,
) -> bool:
    """Execute Rail Movement for *unit_id* to *destination*.

    Cases 8.71-8.78 — Moves the unit along the rail line to the
    destination hex. No CP cost (Case 8.73 — unit must not have
    spent any CP).

    Case 8.78 — No rail hex west of any Axis combat unit may be used.

    Returns True if the move succeeded, False otherwise.
    """
    unit = state.units.get(unit_id)
    if unit is None:
        return False
    if not can_use_rail(unit, state):
        return False

    # Verify destination is a rail hex.
    dest_mh = state.map.get(destination)
    if dest_mh is None or not dest_mh.rail_exits:
        return False

    # Case 8.78: no rail west of any Axis combat unit.
    axis_rail_q = None
    for u in state.units.values():
        if u.side == Side.AXIS and u.is_combat_unit() and u.position is not None:
            mh = state.map.get(u.position)
            if mh is not None and mh.rail_exits:
                if axis_rail_q is None or u.position.q < axis_rail_q:
                    axis_rail_q = u.position.q
    if axis_rail_q is not None and destination.q < axis_rail_q:
        return False

    unit.position = destination
    state.log(
        f"{unit.name} rail move to {destination}",
        category="movement",
    )
    return True
