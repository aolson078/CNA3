"""Section 12.0 — Barrage (Artillery Combat).

Implements Cases 12.1-12.6: artillery positions, target selection,
terrain effects, and the Barrage Results Table.

Artillery units fire indirectly at enemy hexes. Guns may be placed
Forward (can coordinate fire, participate in Anti-Armor and Assault)
or Back (independent fire only, safer from Close Assault).

The Barrage Results Table is indexed by Actual Barrage Points and a
sequential dice roll (11-66). Results are:
  - P = Pinned (infantry/armor only).
  - 0 = No effect.
  - 1, 2, ... = TOE Strength Points destroyed in target hex.

Cross-references:
  - Case 11.32: Actual Points formula.
  - Case 10.33: Holding Off Barrage satisfies ZoC combat requirements.
  - Case 6.12: Barrage costs CP (5 phasing, 3 non-phasing).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from cna.engine.dice import DiceRoller
from cna.engine.game_state import (
    GameState,
    HexCoord,
    Side,
    Unit,
    UnitType,
)
from cna.rules.combat.common import actual_points, raw_points


# ---------------------------------------------------------------------------
# Artillery position (Case 12.1)
# ---------------------------------------------------------------------------


class GunPosition(str, Enum):
    """Case 12.1 — Forward or Back position for Gun-class units."""
    FORWARD = "forward"
    BACK = "back"


# ---------------------------------------------------------------------------
# Barrage Results Table (Case 12.6)
# ---------------------------------------------------------------------------

# The BRT is indexed by (barrage_points_band, dice_roll).
# Results: -1 = Pinned, 0 = no effect, positive = TOE losses.
# OCR is heavily garbled; these are placeholder rows that capture the
# basic shape: higher barrage points + higher rolls → more damage.
# TODO-12.6: replace with manually verified BRT.

# Dice roll bands for sequential 2d6 (11-66).
# We bucket into 6 columns: 11-21, 22-32, 33-43, 44-54, 55-65, 66.
_DICE_BANDS: list[tuple[int, int]] = [
    (11, 21), (22, 32), (33, 43), (44, 54), (55, 65), (66, 66),
]

# BRT rows keyed by (min_barrage, max_barrage) → list of results per band.
# Negative = Pinned (-1).
_BRT: list[tuple[tuple[int, int], list[int]]] = [
    ((1, 2),   [0, 0, 0, -1, -1, 1]),
    ((3, 4),   [0, 0, -1, -1, 1, 1]),
    ((5, 6),   [0, -1, -1, 1, 1, 2]),
    ((7, 8),   [0, -1, 1, 1, 2, 2]),
    ((9, 10),  [-1, -1, 1, 1, 2, 3]),
    ((11, 12), [-1, 1, 1, 2, 2, 3]),
    ((13, 14), [-1, 1, 1, 2, 3, 4]),
    ((15, 99), [-1, 1, 2, 2, 3, 5]),
]


@dataclass(frozen=True)
class BarrageResult:
    """Outcome of a single barrage resolution.

    Case 12.4 — Barrage results.
    """
    pinned: bool = False
    toe_losses: int = 0
    dice_roll: int = 0
    barrage_points: int = 0


def _dice_band_index(roll: int) -> int:
    for i, (lo, hi) in enumerate(_DICE_BANDS):
        if lo <= roll <= hi:
            return i
    return len(_DICE_BANDS) - 1


def resolve_barrage(
    barrage_actual_points: int,
    dice: DiceRoller,
    *,
    column_shifts: int = 0,
) -> BarrageResult:
    """Resolve a single barrage against a target hex.

    Case 12.6 — Roll on the Barrage Results Table.

    Args:
        barrage_actual_points: Total Actual Barrage Points directed at target.
        dice: DiceRoller for the sequential roll.
        column_shifts: Terrain/fortification shifts (negative = left/defender benefit).

    Returns:
        BarrageResult with pinned flag and/or TOE losses.
    """
    if barrage_actual_points <= 0:
        return BarrageResult()

    roll = dice.roll_concat()
    band = _dice_band_index(roll)
    band = max(0, min(band + column_shifts, len(_DICE_BANDS) - 1))

    # Find the BRT row.
    result_val = 0
    for (lo, hi), results in _BRT:
        if lo <= barrage_actual_points <= hi:
            result_val = results[band]
            break
    else:
        # Above max → use last row.
        result_val = _BRT[-1][1][band]

    pinned = result_val < 0
    losses = max(0, result_val)
    return BarrageResult(
        pinned=pinned,
        toe_losses=losses,
        dice_roll=roll,
        barrage_points=barrage_actual_points,
    )
