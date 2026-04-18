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

# The BRT is indexed by (barrage_points_band, sequential_dice_roll).
# Results: -1 = Pinned (no losses), -2 = Pinned + 1 TOE loss,
# 0 = no effect, positive = TOE losses without pinning.
#
# Extracted from Case 12.6 OCR (references/section_12.md lines 437-490).
# The table has columns by target class (Infantry, Armor, Gun) and rows
# by barrage point band. Each cell has a dice range → result mapping.
#
# Format: (min_bp, max_bp) → list of (dice_max, result) tuples.
# Dice are sequential (11-66). First matching band wins.
# Result: 0=no effect, -1=pinned, 1+=TOE losses (pinned implied).

_BRT_INFANTRY: list[tuple[tuple[int, int], tuple[tuple[int, int], ...]]] = [
    ((1, 2),   ((34, 0), (64, -1), (66, 1))),
    ((3, 4),   ((24, 0), (61, -1), (66, 1))),
    ((5, 6),   ((16, 0), (44, -1), (55, -2), (66, 1))),
    ((7, 8),   ((12, 0), (35, -1), (55, -2), (66, 2))),
    ((9, 10),  ((31, -1), (56, -2), (65, 1), (66, 2))),
    ((11, 12), ((31, -1), (55, -2), (63, 1), (66, 2))),
    ((13, 14), ((32, -1), (55, -2), (62, 1), (65, 2), (66, 3))),
    ((15, 99), ((31, -1), (54, -2), (62, 1), (65, 2), (66, 3))),
]

_BRT_ARMOR: list[tuple[tuple[int, int], tuple[tuple[int, int], ...]]] = [
    ((1, 2),   ((31, 0), (66, -1))),
    ((3, 4),   ((22, 0), (66, -1))),
    ((5, 6),   ((63, -1), (66, 0))),
    ((7, 8),   ((62, -1), (66, 1))),
    ((9, 10),  ((54, -1), (66, 1))),
    ((11, 12), ((56, -1), (65, 1), (66, 2))),
    ((13, 14), ((41, -1), (56, 0), (66, 1))),
    ((15, 99), ((41, -1), (56, 0), (65, 1), (66, 2))),
]

_BRT_GUN: list[tuple[tuple[int, int], tuple[tuple[int, int], ...]]] = [
    ((1, 2),   ((66, 0),)),
    ((3, 4),   ((56, 0), (66, 1))),
    ((5, 6),   ((41, 0), (66, 1))),
    ((7, 8),   ((31, 0), (56, 1), (66, 2))),
    ((9, 10),  ((22, 0), (44, 1), (66, 2))),
    ((11, 12), ((31, 0), (44, 1), (56, 2), (66, 3))),
    ((13, 14), ((22, 0), (41, 1), (56, 2), (66, 3))),
    ((15, 99), ((22, 0), (36, 1), (53, 2), (66, 3))),
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


class TargetClass(str, Enum):
    """Case 3.22 — Target class for barrage resolution."""
    INFANTRY = "infantry"
    ARMOR = "armor"
    GUN = "gun"


def _lookup_brt(
    table: list[tuple[tuple[int, int], tuple[tuple[int, int], ...]]],
    barrage_points: int,
    dice_roll: int,
) -> int:
    """Look up a result in a BRT sub-table (Case 12.6).

    Returns: 0=no effect, -1=pinned, -2=pinned+1 loss, positive=losses.
    """
    for (lo, hi), bands in table:
        if lo <= barrage_points <= hi:
            for dice_max, result in bands:
                if dice_roll <= dice_max:
                    return result
            return bands[-1][1] if bands else 0
    # Above max → use last row.
    last_bands = table[-1][1]
    for dice_max, result in last_bands:
        if dice_roll <= dice_max:
            return result
    return last_bands[-1][1] if last_bands else 0


def resolve_barrage(
    barrage_actual_points: int,
    dice: DiceRoller,
    *,
    target_class: TargetClass = TargetClass.INFANTRY,
    column_shifts: int = 0,
) -> BarrageResult:
    """Resolve a single barrage against a target hex.

    Case 12.6 — Roll on the Barrage Results Table. The table is indexed
    by target class (Infantry, Armor, Gun), barrage points, and a
    sequential dice roll (11-66).

    Args:
        barrage_actual_points: Total Actual Barrage Points directed at target.
        dice: DiceRoller for the sequential roll.
        target_class: What type of units are being barraged.
        column_shifts: Terrain/fortification shifts applied to barrage
            points (negative = reduce effective points).

    Returns:
        BarrageResult with pinned flag and/or TOE losses.
    """
    if barrage_actual_points <= 0:
        return BarrageResult()

    effective_bp = max(0, barrage_actual_points + column_shifts)
    if effective_bp <= 0:
        return BarrageResult()

    roll = dice.roll_concat()

    table = {
        TargetClass.INFANTRY: _BRT_INFANTRY,
        TargetClass.ARMOR: _BRT_ARMOR,
        TargetClass.GUN: _BRT_GUN,
    }[target_class]

    result_val = _lookup_brt(table, effective_bp, roll)

    pinned = result_val < 0
    losses = 0
    if result_val == -2:
        losses = 1
    elif result_val > 0:
        losses = result_val

    return BarrageResult(
        pinned=pinned,
        toe_losses=losses,
        dice_roll=roll,
        barrage_points=barrage_actual_points,
    )


# ---------------------------------------------------------------------------
# Barrage targeting (Case 12.2)
# ---------------------------------------------------------------------------


def can_barrage_target(
    firing_hex: "HexCoord",
    target_hex: "HexCoord",
    position: GunPosition,
) -> bool:
    """Whether an artillery unit at *firing_hex* can barrage *target_hex*.

    Case 12.21 — Any adjacent hex containing enemy units may be barraged.
    Case 12.22 — Forward guns can coordinate fire with other Forward guns
    in same or different hexes against the same target.
    Case 12.23 — Back guns fire independently.
    """
    from cna.engine.hex_map import is_adjacent
    return is_adjacent(firing_hex, target_hex)


def max_targets_per_unit(position: GunPosition) -> int:
    """Maximum number of different hexes one artillery unit can barrage.

    Case 12.22 — Forward: may split fire among multiple targets.
    Case 12.23 — Back: may only fire at one target.
    """
    if position == GunPosition.BACK:
        return 1
    return 3  # Forward guns can split across up to 3 targets (est).


# ---------------------------------------------------------------------------
# Terrain effects on barrage (Case 12.3)
# ---------------------------------------------------------------------------


def terrain_barrage_shift(terrain: "TerrainType", fort_level: int = 0) -> int:
    """Column shift for terrain/fortification on barrage (Case 12.3).

    Negative shifts reduce effective barrage points (defender benefit).
    Case 12.31 — Fortifications provide column shifts.
    Case 12.32 — Certain terrain reduces barrage effectiveness.
    """
    from cna.engine.game_state import TerrainType
    shift = 0
    # Fortification shifts (Case 25.22).
    shift -= fort_level
    # Terrain shifts.
    if terrain == TerrainType.ROUGH:
        shift -= 1
    elif terrain == TerrainType.MOUNTAIN:
        shift -= 2
    elif terrain == TerrainType.CITY:
        shift -= 1
    return shift


# ---------------------------------------------------------------------------
# Barrage against facilities (Case 12.5)
# ---------------------------------------------------------------------------


def barrage_facility_effectiveness(barrage_points: int, *, is_port: bool = False,
                                   is_airfield: bool = False) -> int:
    """Effective barrage points against a facility (Case 12.5).

    Case 12.51 — Barrage against airfields and ports is less effective
    than against units. Halve the barrage points (rounded down).
    """
    if is_port or is_airfield:
        return barrage_points // 2
    return barrage_points
