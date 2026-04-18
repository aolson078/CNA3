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
