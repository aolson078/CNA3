"""Section 21.0 — Breakdown.

Implements Cases 21.1-21.6: which units break down, when breakdown
occurs, how it is determined, broken down vehicles, towing.

Vehicles accumulate Breakdown Points (BP) as they move through terrain.
When BP exceed a threshold, the unit rolls on the Breakdown Table to
determine how many TOE Strength Points break down.

Key rules:
  - Case 21.11: Trucks, tanks, armored recce/cars, SP guns subject.
    HQs and motorcycles exempt.
  - Case 21.21: Each terrain type has a BP value (from 8.37).
  - Case 21.27: No breakdown check until >3 BP accumulated.
  - Case 21.31: Two-dice roll on Breakdown Table; column = BP range
    adjusted by BAR (Breakdown Adjustment Rating) + weather.
  - Case 21.35: Round fractions up.
  - Case 21.41: Broken down vehicles cannot move until repaired.
  - Case 21.61: Towing costs 10 CP.

Cross-references:
  - Case 8.37: Terrain breakdown point values.
  - Case 22.0: Repair of broken down vehicles.
  - Case 29.0: Weather affects breakdown.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from cna.engine.dice import DiceRoller
from cna.engine.game_state import (
    Unit,
    UnitType,
)


# ---------------------------------------------------------------------------
# Breakdown eligibility (Case 21.11)
# ---------------------------------------------------------------------------

_BREAKDOWN_TYPES: frozenset[UnitType] = frozenset({
    UnitType.TRUCK,
    UnitType.TANK,
    UnitType.RECCE,
    UnitType.TANK_RECOVERY,
})


def is_breakdown_eligible(unit: Unit) -> bool:
    """Case 21.11 — Whether *unit* is subject to breakdown."""
    return unit.unit_type in _BREAKDOWN_TYPES


# ---------------------------------------------------------------------------
# Breakdown Points accumulation
# ---------------------------------------------------------------------------

BREAKDOWN_CHECK_THRESHOLD = 3  # Case 21.27: no check until >3 BP.
TOW_CP_COST = 10               # Case 21.61: towing costs 10 CP.


def terrain_breakdown_points(terrain_value: int, *, on_road: bool = False,
                              on_track: bool = False) -> int:
    """Breakdown points for entering a hex (Case 21.21).

    Case 8.37: roads negate breakdown; tracks halve it.
    """
    if on_road:
        return 0
    if on_track:
        return max(0, terrain_value // 2)
    return terrain_value


# ---------------------------------------------------------------------------
# Breakdown Table (Case 21.31)
# ---------------------------------------------------------------------------

# Simplified Breakdown Table. Columns are BP ranges.
# Result = percentage of TOE that breaks down.
# TODO-21.31: replace with full table.

_BREAKDOWN_TABLE: list[tuple[int, int, list[int]]] = [
    # (min_bp, max_bp, results_by_dice_band[0..5])
    # Dice bands: 11-21, 22-32, 33-43, 44-54, 55-65, 66
    (4, 10,    [0, 0, 0, 0, 5, 10]),
    (11, 20,   [0, 0, 0, 5, 10, 15]),
    (21, 35,   [0, 0, 5, 10, 15, 20]),
    (36, 50,   [0, 5, 10, 15, 20, 25]),
    (51, 70,   [5, 10, 15, 20, 25, 30]),
    (71, 999,  [10, 15, 20, 25, 30, 40]),
]


@dataclass(frozen=True)
class BreakdownResult:
    """Outcome of a breakdown check.

    Case 21.31 — Percentage and TOE lost to breakdown.
    """
    breakdown_points: int
    dice_roll: int
    loss_pct: int
    toe_lost: int
    bar_adjustment: int


def check_breakdown(
    unit: Unit,
    breakdown_points: int,
    dice: DiceRoller,
    *,
    weather_modifier: int = 0,
) -> BreakdownResult:
    """Roll on the Breakdown Table (Case 21.31).

    Args:
        unit: Unit being checked.
        breakdown_points: Accumulated BP this operations stage.
        dice: DiceRoller for the check.
        weather_modifier: Column shift from weather (Case 21.37).

    Returns:
        BreakdownResult. If BP ≤ threshold, no check needed → 0 losses.
    """
    if breakdown_points <= BREAKDOWN_CHECK_THRESHOLD:
        return BreakdownResult(breakdown_points, 0, 0, 0, 0)

    bar = unit.stats.breakdown_adjustment
    effective_bp = max(0, breakdown_points + bar + weather_modifier)

    roll = dice.roll_concat()
    band = _dice_band(roll)

    loss_pct = 0
    for min_bp, max_bp, results in _BREAKDOWN_TABLE:
        if min_bp <= effective_bp <= max_bp:
            loss_pct = results[band]
            break
    else:
        loss_pct = _BREAKDOWN_TABLE[-1][2][band]

    # Case 21.35: round fractions up.
    toe_lost = math.ceil(unit.current_toe * loss_pct / 100) if loss_pct > 0 else 0

    return BreakdownResult(
        breakdown_points=breakdown_points,
        dice_roll=roll,
        loss_pct=loss_pct,
        toe_lost=toe_lost,
        bar_adjustment=bar,
    )


def apply_breakdown(unit: Unit, result: BreakdownResult) -> None:
    """Apply breakdown losses and set the broken_down flag (Case 21.41)."""
    if result.toe_lost > 0:
        unit.current_toe = max(0, unit.current_toe - result.toe_lost)
        unit.broken_down = True


def _dice_band(roll: int) -> int:
    bands = [(11, 21), (22, 32), (33, 43), (44, 54), (55, 65), (66, 66)]
    for i, (lo, hi) in enumerate(bands):
        if lo <= roll <= hi:
            return i
    return 5
