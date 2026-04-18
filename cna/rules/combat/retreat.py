"""Section 13.0 — Retreat Before Assault.

Implements Cases 13.1-13.2: which units may retreat and how far.

Non-phasing units may retreat before assault if they are not Pinned
and not shattered (Cohesion ≤ -26). Retreat costs CP and follows
normal movement rules.

Key rules:
  - Case 13.1: Non-phasing, non-pinned units may retreat.
  - Case 13.2: Units adjacent to enemy may retreat unlimited CP.
    Units not adjacent may retreat max 4 CP (minimum 1 hex).
  - Cannot retreat into enemy ZoC.
  - Break Off costs apply if in Contact/Engaged.

Cross-references:
  - Case 8.6: Breaking Off costs (2 CP Contact, 4 CP Engaged).
  - Case 6.26: Shattered units cannot retreat.
  - Case 10.23: Cannot retreat into enemy ZoC.
"""

from __future__ import annotations

from dataclasses import dataclass

from cna.engine.game_state import (
    HexCoord,
    Unit,
)
from cna.rules.capability_points import is_shattered


# ---------------------------------------------------------------------------
# Retreat eligibility (Case 13.1)
# ---------------------------------------------------------------------------


def can_retreat_before_assault(unit: Unit) -> bool:
    """Whether *unit* may perform Retreat Before Assault.

    Case 13.1 — Non-pinned, non-shattered units may retreat.
    (Phasing-player check is caller's responsibility.)
    """
    if unit.pinned:
        return False
    if is_shattered(unit):
        return False
    return True


# ---------------------------------------------------------------------------
# Retreat CP limits (Case 13.2)
# ---------------------------------------------------------------------------


MAX_CP_NON_ADJACENT = 4  # Case 13.2: max 4 CP if not adjacent to enemy.


@dataclass(frozen=True)
class RetreatLimits:
    """CP and hex limits for a Retreat Before Assault.

    Case 13.2 — Adjacent to enemy → unlimited CP for retreat.
    Not adjacent → max 4 CP (but at least 1 hex).
    """
    max_cp: int
    min_hexes: int

    @staticmethod
    def for_unit(adjacent_to_enemy: bool) -> "RetreatLimits":
        """Case 13.2 — Determine retreat limits based on adjacency."""
        if adjacent_to_enemy:
            return RetreatLimits(max_cp=9999, min_hexes=0)
        return RetreatLimits(max_cp=MAX_CP_NON_ADJACENT, min_hexes=1)


# ---------------------------------------------------------------------------
# Retreat path validation (Case 13.2)
# ---------------------------------------------------------------------------


def retreat_path_valid(
    state: "GameState",
    unit: Unit,
    path: list["HexCoord"],
) -> list[str]:
    """Validate a proposed retreat path.

    Case 13.2 — Retreat must follow normal movement rules except:
    - Cannot retreat into enemy ZoC (Case 10.23).
    - Must be consecutive hexes.
    - Cannot enter enemy-occupied hexes.

    Returns list of violation descriptions (empty = valid).
    """
    from cna.engine.game_state import GameState, HexCoord
    from cna.engine.hex_map import HexMap, is_adjacent
    from cna.rules.zones_of_control import is_enemy_zoc

    errors: list[str] = []
    if not path or len(path) < 2:
        return errors

    hex_map = HexMap(state.map)
    for i in range(1, len(path)):
        prev, cur = path[i - 1], path[i]
        if not is_adjacent(prev, cur):
            errors.append(f"{prev} → {cur} not adjacent (Case 13.2)")
        if cur not in hex_map:
            errors.append(f"{cur} is off-map")
            continue
        enemy = [u for u in state.units_at(cur) if u.side != unit.side]
        if enemy:
            errors.append(f"{cur} enemy-occupied (Case 8.13)")
        if is_enemy_zoc(state, cur, unit.side):
            errors.append(f"{cur} is in enemy ZoC (Case 10.23)")
    return errors


def execute_retreat(
    state: "GameState",
    unit: Unit,
    path: list["HexCoord"],
) -> int:
    """Execute a Retreat Before Assault along *path*.

    Case 13.2 — Moves the unit hex-by-hex, spending CP per terrain.
    Retreat is involuntary movement (bypasses Case 8.17 voluntary cap).

    Returns total CP spent.
    """
    from cna.rules.land_movement import move_unit
    if len(path) < 2:
        return 0
    result = move_unit(state, unit.id, path, voluntary=False)
    return result.cp_spent
