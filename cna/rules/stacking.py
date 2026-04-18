"""Section 9.0 — Stacking.

Implements Cases 9.11-9.35 and the 9.4 Stacking Point Values table.

Stacking limits the number of units that may occupy a hex at the end of
any Movement Segment. Each unit has a Stacking Point (SP) value, and
each terrain type has a maximum SP capacity.

Key rules:
  - Case 9.11: Each unit has a printed SP value.
  - Case 9.12: HQ units have 0 SP when no combat units attached, else
    their printed value.
  - Case 9.14: Terrain-specific stacking limits (from 8.37).
  - Case 9.16: Garrisons stack free at assigned hex; AA free in cities.
  - Case 9.25: Company-size units (SP 0) — max 5 per hex except cities.
  - Case 9.29: Attached trucks don't count toward stacking.
  - Case 9.31: Cannot end movement violating stacking.
  - Case 9.32: May pass through friendly units; limits apply at rest.
  - Case 9.33: Road/track stacking limit of 5 SP.

Cross-references:
  - Case 3.33: HQ stacking points (full vs. empty).
  - Case 8.37: Terrain Effects Chart stacking column.
  - Case 15.82: Units unable to retreat due to stacking → extra losses.
"""

from __future__ import annotations

from cna.engine.game_state import (
    GameState,
    HexCoord,
    MapHex,
    OrgSize,
    Side,
    TerrainType,
    Unit,
    UnitType,
)


# ---------------------------------------------------------------------------
# Stacking Point values (Case 9.4)
# ---------------------------------------------------------------------------

_SP_BY_ORG_SIZE: dict[OrgSize, int] = {
    OrgSize.DIVISION: 5,
    OrgSize.BRIGADE: 3,
    OrgSize.BATTALION: 1,
    OrgSize.COMPANY: 0,
}

ROAD_TRACK_STACK_LIMIT = 5  # Case 9.33
MAX_ZERO_SP_UNITS = 5       # Case 9.25


def stacking_points(unit: Unit) -> int:
    """Return the Stacking Point value for *unit*.

    Case 9.11, 9.12, 9.4 — SP depends on org size. HQ units with no
    attached combat units have SP 0 (Case 9.12 / 3.33).
    """
    if unit.unit_type == UnitType.HEADQUARTERS and not unit.attached_unit_ids:
        return 0
    if unit.unit_type == UnitType.TRUCK:
        return 0  # Case 9.29: attached trucks don't count.
    return _SP_BY_ORG_SIZE.get(unit.org_size, 1)


# ---------------------------------------------------------------------------
# Terrain stacking limits (Case 9.14 / 8.37)
# ---------------------------------------------------------------------------

# Stacking limits per terrain type. The 8.37 chart is OCR-garbled;
# these are conservative placeholders.
# TODO-8.37: verify against manually transcribed chart.
_TERRAIN_STACK_LIMIT: dict[TerrainType, int] = {
    TerrainType.DESERT: 10,
    TerrainType.ROUGH: 8,
    TerrainType.ESCARPMENT: 8,
    TerrainType.MOUNTAIN: 5,
    TerrainType.SALT_MARSH: 5,
    TerrainType.DEPRESSION: 10,
    TerrainType.OASIS: 10,
    TerrainType.TOWN: 10,
    TerrainType.CITY: 15,
    TerrainType.PORT: 10,
    TerrainType.SEA: 0,
    TerrainType.IMPASSABLE: 0,
}


def hex_stacking_limit(terrain: TerrainType) -> int:
    """Maximum Stacking Points allowed in a hex of *terrain*.

    Case 9.14 / 8.37 — Terrain-specific limits.
    """
    return _TERRAIN_STACK_LIMIT.get(terrain, 10)


# ---------------------------------------------------------------------------
# Stacking checks
# ---------------------------------------------------------------------------


def current_stacking(state: GameState, coord: HexCoord) -> int:
    """Total Stacking Points currently at *coord*.

    Case 9.11 — Sum of all units' SP values at the hex.
    """
    return sum(stacking_points(u) for u in state.units_at(coord))


def would_violate_stacking(
    state: GameState,
    coord: HexCoord,
    entering_unit: Unit,
) -> bool:
    """True if placing *entering_unit* at *coord* would violate stacking.

    Case 9.31 — Units may not end movement exceeding the hex's limit.
    """
    mh = state.map.get(coord)
    if mh is None:
        return True
    limit = hex_stacking_limit(mh.terrain)
    sp_entering = stacking_points(entering_unit)
    sp_current = current_stacking(state, coord)
    # Don't double-count if the unit is already at this hex.
    if entering_unit.position == coord:
        sp_current -= stacking_points(entering_unit)
    if sp_current + sp_entering > limit:
        return True
    # Case 9.25: max 5 zero-SP units (except cities).
    if sp_entering == 0 and mh.terrain != TerrainType.CITY:
        zero_sp_count = sum(
            1 for u in state.units_at(coord)
            if stacking_points(u) == 0 and u.id != entering_unit.id
        )
        if zero_sp_count >= MAX_ZERO_SP_UNITS:
            return True
    return False


def check_hex_stacking(state: GameState, coord: HexCoord) -> list[str]:
    """Return violation descriptions for the current stack at *coord*.

    Case 9.31 — Called after movement to verify. Returns empty list if OK.
    """
    errors: list[str] = []
    mh = state.map.get(coord)
    if mh is None:
        return errors
    limit = hex_stacking_limit(mh.terrain)
    total = current_stacking(state, coord)
    if total > limit:
        errors.append(
            f"Hex {coord}: {total} SP exceeds limit {limit} "
            f"for {mh.terrain.value} (Case 9.14)"
        )
    # Case 9.25: zero-SP unit cap.
    if mh.terrain != TerrainType.CITY:
        zero_count = sum(1 for u in state.units_at(coord) if stacking_points(u) == 0)
        if zero_count > MAX_ZERO_SP_UNITS:
            errors.append(
                f"Hex {coord}: {zero_count} zero-SP units exceeds "
                f"limit of {MAX_ZERO_SP_UNITS} (Case 9.25)"
            )
    return errors


def available_stacking(state: GameState, coord: HexCoord) -> int:
    """Remaining SP capacity at *coord*.

    Case 9.14 — Returns how many more SP can fit.
    """
    mh = state.map.get(coord)
    if mh is None:
        return 0
    return max(0, hex_stacking_limit(mh.terrain) - current_stacking(state, coord))
