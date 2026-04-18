"""Section 26.0 — Minefields.

Implements Cases 26.1-26.2: minefield types and combat effects.

Key rules:
  - Case 26.11: Real and dummy minefields (two sides of counter).
  - Case 26.13: Engineer alone in minefield 1 ops stage (0 CP) clears it.
  - Case 26.14: Dummy cleared when enemy enters.
  - Case 26.21: Entry costs from Terrain Effects Chart.
  - Case 26.24: Engineer reduces entry cost to 4 CP.
  - Case 26.25: Vehicle entering enemy minefield without engineer: roll
    1d6 per battalion, 5-6 destroys 1 TOE.
  - Case 26.26: Defender in friendly minefield gets +1 CRT column.

Cross-references:
  - Case 23.21: Engineer reduces entry cost.
  - Case 24.3: Minefield construction.
  - Case 8.37: Terrain Effects Chart minefield rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from cna.engine.dice import DiceRoller


class MinefieldType(str, Enum):
    """Case 26.11 — Real vs Dummy minefields."""
    REAL = "real"
    DUMMY = "dummy"


# CP cost to enter minefields (Case 26.21, 26.24, 23.21).
MINEFIELD_CP_COST_MOTORIZED = 8        # Without engineer
MINEFIELD_CP_COST_NON_MOTORIZED = 4    # Without engineer
MINEFIELD_CP_WITH_ENGINEER = 4         # Case 26.24 / 23.21

# Combat modifier (Case 26.26).
MINEFIELD_DEFENDER_CRT_SHIFT = 1  # +1 column (defender benefit = left shift)


def vehicle_minefield_loss_check(toe_battalions: int, dice: DiceRoller) -> int:
    """Roll for vehicle losses entering enemy minefield without engineer.

    Case 26.25 — Roll 1d6 per battalion; 5-6 destroys 1 TOE.

    Returns number of TOE destroyed.
    """
    losses = 0
    for _ in range(toe_battalions):
        if dice.roll() >= 5:
            losses += 1
    return losses
