"""Section 10.0 — Zones of Control.

Implements Cases 10.11-10.29 (which units exert ZoC, effects) and
10.31-10.36 (combat requirements / holding off).

CNA uses a Rigid, Active ZoC system (Case 3.1). A unit entering an
enemy ZoC must stop immediately and may not move further until the
next Movement Segment. Exiting an enemy ZoC costs CP (Breaking Off,
see Section 8.6).

Key rules:
  - Case 10.11: Combat units with >1 SP exert ZoC; or any stack >1 SP.
  - Case 10.14: Shattered units (Cohesion ≤ -26) do not exert ZoC.
  - Case 10.21: ZoC doesn't extend through sea hexsides, escarpments,
    or into hexes the unit couldn't enter.
  - Case 10.22: No CP cost to enter enemy ZoC (but must stop).
  - Case 10.23: Must stop upon entering enemy ZoC.
  - Case 10.24: Cannot move from one enemy ZoC directly to another.
  - Case 10.26: Friendly combat unit negates enemy ZoC in same hex.
  - Case 10.29: Truck convoys may not enter enemy ZoC unless friendly
    combat unit present.

Cross-references:
  - Case 8.14: Movement stops in enemy ZoC.
  - Case 8.15/8.24: Breaking Off costs (Contact 2 CP, Engaged 4 CP).
  - Case 9.0: Stacking points determine ZoC eligibility.
  - Case 6.26: Shattered units cannot exert ZoC.
"""

from __future__ import annotations

from cna.engine.game_state import (
    GameState,
    HexCoord,
    Side,
    TerrainType,
    Unit,
    UnitType,
)
from cna.engine.hex_map import HexMap, neighbors
from cna.rules.capability_points import is_shattered
from cna.rules.stacking import stacking_points


# ---------------------------------------------------------------------------
# ZoC exertion (Case 10.1)
# ---------------------------------------------------------------------------


def unit_exerts_zoc(unit: Unit) -> bool:
    """Whether a single *unit* contributes to ZoC exertion.

    Case 10.11 — Combat units above battalion-equivalent (>1 SP) exert
    ZoC. Truck convoys (Case 10.11), SGSU, and empty HQs never exert.
    Case 10.14 — Shattered units do not exert ZoC.
    """
    if is_shattered(unit):
        return False
    if unit.unit_type in {UnitType.TRUCK, UnitType.SGSU}:
        return False
    if unit.unit_type == UnitType.HEADQUARTERS and not unit.attached_unit_ids:
        return False
    return stacking_points(unit) > 1


def hex_exerts_zoc(state: GameState, coord: HexCoord, side: Side) -> bool:
    """Whether the units of *side* at *coord* collectively exert a ZoC.

    Case 10.11 — Even if no single unit qualifies, if total SP at the hex
    exceeds 1 then the hex exerts a ZoC. Shattered units excluded.
    """
    units_here = [u for u in state.units_at(coord)
                  if u.side == side and not is_shattered(u)]
    if not units_here:
        return False
    # Any single qualifying unit is sufficient.
    if any(unit_exerts_zoc(u) for u in units_here):
        return True
    # Otherwise check combined SP > 1.
    total_sp = sum(stacking_points(u) for u in units_here)
    return total_sp > 1


# ---------------------------------------------------------------------------
# ZoC projection (Case 10.21)
# ---------------------------------------------------------------------------

# Terrain types that block ZoC extension across hexsides.
_ZOC_BLOCKING_TERRAIN: set[TerrainType] = {
    TerrainType.SEA,
    TerrainType.IMPASSABLE,
}


def controlled_hexes(
    state: GameState,
    coord: HexCoord,
    side: Side,
) -> list[HexCoord]:
    """Return the hexes into which *side*'s units at *coord* project ZoC.

    Case 10.21 — ZoC extends to all six adjacent hexes except:
      a. Through sea/impassable hexsides.
      b. Through escarpment hexsides.
      c. Into hexes the unit couldn't enter.
    For (c) we use a simplified check: the target hex must exist on the
    map and not be sea/impassable.

    Returns an empty list if *side* does not exert ZoC from *coord*.
    """
    if not hex_exerts_zoc(state, coord, side):
        return []
    hex_map = HexMap(state.map)
    result: list[HexCoord] = []
    for nb in neighbors(coord):
        if nb not in hex_map:
            continue
        nb_hex = hex_map.require(nb)
        if nb_hex.terrain in _ZOC_BLOCKING_TERRAIN:
            continue
        # Case 10.21b: ZoC doesn't extend through escarpment hexsides.
        # Simplified: if the target hex is an escarpment, skip.
        # (Full implementation would check the hexside direction.)
        if nb_hex.terrain == TerrainType.ESCARPMENT:
            continue
        result.append(nb)
    return result


def is_enemy_zoc(
    state: GameState,
    coord: HexCoord,
    moving_side: Side,
    *,
    exclude_unit_id: str | None = None,
) -> bool:
    """Whether *coord* is in an enemy ZoC from *moving_side*'s perspective.

    Case 10.0 — True if any adjacent hex contains enemy units that
    project ZoC into *coord*.

    Case 10.26 — Friendly combat unit presence negates enemy ZoC.
    If *exclude_unit_id* is set, that unit is not counted as a friendly
    negator (used by Case 10.24 to check whether the moving unit's
    current hex is in enemy ZoC ignoring its own presence).
    """
    friendly_combat = [
        u for u in state.units_at(coord)
        if u.side == moving_side and u.is_combat_unit()
        and u.id != exclude_unit_id
    ]
    if friendly_combat:
        return False

    enemy_side = Side.COMMONWEALTH if moving_side == Side.AXIS else Side.AXIS
    hex_map = HexMap(state.map)
    for nb in hex_map.neighbors_in_bounds(coord):
        if hex_exerts_zoc(state, nb, enemy_side):
            if coord in controlled_hexes(state, nb, enemy_side):
                return True
    return False


# ---------------------------------------------------------------------------
# Movement integration
# ---------------------------------------------------------------------------


def must_stop_for_zoc(
    state: GameState,
    coord: HexCoord,
    moving_unit: Unit,
) -> bool:
    """Whether *moving_unit* must stop upon entering *coord*.

    Case 10.23, 8.14 — All units must cease movement upon entering an
    enemy-controlled hex. The unit must wait until the next Movement
    Segment to leave (paying Break Off cost).
    """
    return is_enemy_zoc(state, coord, moving_unit.side)


def can_enter_zoc(
    state: GameState,
    coord: HexCoord,
    unit: Unit,
) -> bool:
    """Whether *unit* is allowed to enter *coord* considering ZoC rules.

    Case 10.24 — Cannot move from one enemy ZoC directly into another.
    Case 10.29 — Truck convoys may not enter enemy ZoC unless a
    friendly combat unit is already there.

    Note: this checks entry permission, not the "must stop" rule. A unit
    *can* enter an enemy ZoC (and must stop); but it *cannot* enter if
    it is currently in an enemy ZoC (10.24) or if it is a truck convoy
    without friendly escort (10.29).
    """
    if not is_enemy_zoc(state, coord, unit.side):
        return True

    # Case 10.29: trucks need friendly combat escort.
    if unit.unit_type == UnitType.TRUCK:
        friendly_combat = [
            u for u in state.units_at(coord)
            if u.side == unit.side and u.is_combat_unit()
        ]
        if not friendly_combat:
            return False

    # Case 10.24: cannot move directly from one enemy ZoC to another.
    # Exclude the moving unit from the friendly-negation check at its
    # current hex — it can't shield itself from the ZoC it's leaving.
    if unit.position is not None and is_enemy_zoc(
        state, unit.position, unit.side, exclude_unit_id=unit.id
    ):
        return False

    return True
