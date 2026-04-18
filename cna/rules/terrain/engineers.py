"""Section 23.0 — Engineers.

Implements Cases 23.1-23.2: engineer units and their uses.

Engineers are non-combat units that assist with construction,
minefield clearance, and fortification assault bonuses.

Key rules:
  - Case 23.11: No combat value; parenthesized strength only with combat.
  - Case 23.21: Engineers reduce minefield entry cost.
  - Case 23.22: Engineer alone in minefield 1 ops stage clears it.
  - Case 23.23: Build fortifications, repair roads, construct facilities.
  - Case 23.24: Unpinned engineer in assault adds +1 differential vs forts.

Cross-references:
  - Case 24.0: Construction rules use engineers.
  - Case 26.0: Minefield interactions.
"""

from __future__ import annotations

from cna.engine.game_state import Unit, UnitType


def is_engineer(unit: Unit) -> bool:
    """Case 23.11 — Whether *unit* is an Engineer unit."""
    return unit.unit_type == UnitType.ENGINEER


# Minefield CP costs with engineer (Case 23.21).
MINEFIELD_CP_WITH_ENGINEER_MOTORIZED = 6
MINEFIELD_CP_WITH_ENGINEER_NON_MOTORIZED = 3

# Assault bonus vs fortification (Case 23.24).
ENGINEER_FORT_ASSAULT_BONUS = 1
