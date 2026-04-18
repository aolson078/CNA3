"""Section 14.0 — Anti-Armor Combat.

Implements Cases 14.1-14.6: which units participate, restrictions,
terrain effects, damage assessment, and the Anti-Armor CRT.

Anti-Armor fire is simultaneous between both sides. Damage Points from
the CRT are absorbed by the target's Armor Protection Rating; excess
points destroy TOE Strength Points.

Key rules:
  - Case 14.1: Units with Anti-Armor rating participate.
  - Case 14.2: Back-position guns cannot fire Anti-Armor.
  - Case 14.3: Terrain column shifts (left = defender benefit).
  - Case 14.4: Damage Points vs. Armor Protection Rating.
    Each TOE SP can absorb damage equal to its Armor Protection Rating.
    Excess damage destroys that SP.
  - Case 14.5: Destroyed tank markers placed on destroyed armor.
  - Case 14.6: Anti-Armor CRT — sequential dice (11-66) indexed by
    Actual Anti-Armor Points. Phasing player decreases dice by one
    row. Terrain shifts columns left.

Cross-references:
  - Case 11.32: Actual Points formula.
  - Case 12.1: Forward/Back position affects eligibility.
"""

from __future__ import annotations

from dataclasses import dataclass

from cna.engine.dice import DiceRoller
from cna.rules.combat.common import actual_points, raw_points


# ---------------------------------------------------------------------------
# Anti-Armor CRT (Case 14.6)
# ---------------------------------------------------------------------------

# The AA-CRT uses sequential dice (11-66) and is indexed by Actual
# Anti-Armor Points. Results are Damage Points.
#
# Design principles for these values:
#   - Low dice (11-22): generally misses or minimal damage.
#   - Mid dice (33-44): moderate damage at higher AA points.
#   - High dice (55-66): heavy damage, especially at high AA points.
#   - More AA points shifts the damage curve left (earlier hits).
#   - At 0 AA points (only if 1-4 raw), only a 66 can score damage.
#   - Damage scales roughly linearly with AA points at high dice,
#     but the low-dice floor ensures even strong AT fire can miss.
#
# Format: (min_aa, max_aa) → tuple of (dice_max, damage_points).
# First matching threshold for the dice roll wins.

_AA_CRT: list[tuple[tuple[int, int], tuple[tuple[int, int], ...]]] = [
    # 0 AA points — only if 1-4 raw (Case 14.6 footnote).
    ((0, 0),   ((65, 0), (66, 1))),

    # 1-2 AA points — light AT fire. Only high dice score.
    ((1, 2),   ((44, 0), (54, 1), (64, 2), (66, 3))),

    # 3-4 AA points — standard AT battery.
    ((3, 4),   ((33, 0), (44, 1), (54, 3), (64, 5), (66, 7))),

    # 5-6 AA points — reinforced AT or light tank fire.
    ((5, 6),   ((22, 0), (34, 1), (44, 3), (54, 5), (63, 8), (66, 10))),

    # 7-8 AA points — strong AT concentration.
    ((7, 8),   ((16, 0), (26, 1), (36, 3), (46, 5), (55, 8), (63, 12), (66, 15))),

    # 9-10 AA points — massed AT fire.
    ((9, 10),  ((14, 0), (24, 2), (34, 4), (44, 7), (54, 10), (63, 14), (66, 17))),

    # 11-12 AA points — heavy AT with tank support.
    ((11, 12), ((13, 0), (23, 2), (33, 5), (43, 8), (53, 12), (62, 16), (66, 20))),

    # 13-14 AA points — concentrated armor + AT.
    ((13, 14), ((12, 0), (22, 3), (33, 6), (43, 10), (53, 14), (62, 19), (66, 23))),

    # 15-16 AA points — overwhelming AT concentration.
    ((15, 16), ((12, 1), (22, 4), (32, 7), (42, 11), (52, 16), (62, 22), (66, 27))),

    # 16+ AA points — maximum fire concentration.
    ((17, 99), ((11, 2), (22, 5), (32, 9), (42, 13), (52, 18), (61, 24), (66, 30))),
]


@dataclass(frozen=True)
class AntiArmorResult:
    """Outcome of anti-armor fire resolution.

    Case 14.4 — Damage Points are compared against Armor Protection to
    determine TOE losses.
    """
    damage_points: int = 0
    dice_roll: int = 0
    aa_points: int = 0


def resolve_anti_armor(
    aa_actual_points: int,
    dice: DiceRoller,
    *,
    column_shifts: int = 0,
    is_phasing: bool = False,
) -> AntiArmorResult:
    """Resolve anti-armor fire.

    Case 14.6 — Roll sequential dice on the Anti-Armor CRT.

    Args:
        aa_actual_points: Total Actual Anti-Armor Points firing.
        dice: DiceRoller for the sequential roll.
        column_shifts: Terrain/fortification shifts. Negative shifts
            reduce effective AA points (left on table = defender benefit).
        is_phasing: If True, the phasing player decreases dice by one
            row (Case 14.6 modifier — effectively improves the roll).

    Returns:
        AntiArmorResult with Damage Points to apply.
    """
    if aa_actual_points <= 0:
        return AntiArmorResult()

    # Apply column shifts to effective AA points.
    effective_aa = max(0, aa_actual_points + column_shifts)
    if effective_aa <= 0:
        return AntiArmorResult()

    roll = dice.roll_concat()

    # Case 14.6 modifier: phasing player decreases dice by one row.
    # In sequential dice, "one row" means subtracting from the tens digit.
    # Simplified: subtract 10 from the roll (min 11).
    if is_phasing:
        roll = max(11, roll - 10)

    damage = _lookup_aa(effective_aa, roll)

    return AntiArmorResult(
        damage_points=damage,
        dice_roll=roll,
        aa_points=aa_actual_points,
    )


def _lookup_aa(aa_points: int, dice_roll: int) -> int:
    """Look up Damage Points in the Anti-Armor CRT (Case 14.6)."""
    for (lo, hi), bands in _AA_CRT:
        if lo <= aa_points <= hi:
            for dice_max, dp in bands:
                if dice_roll <= dice_max:
                    return dp
            return bands[-1][1] if bands else 0
    # Above max row → use last.
    last = _AA_CRT[-1][1]
    for dice_max, dp in last:
        if dice_roll <= dice_max:
            return dp
    return last[-1][1] if last else 0


def apply_armor_damage(
    damage_points: int,
    armor_protection: int,
    current_toe: int,
) -> int:
    """Calculate TOE losses from Damage Points vs. Armor Protection.

    Case 14.4 — Each Armor Protection Rating point absorbs one Damage
    Point per TOE Strength Point. When accumulated damage on a TOE SP
    meets or exceeds its Armor Protection, that SP is destroyed.

    Returns:
        Number of TOE Strength Points destroyed.
    """
    if damage_points <= 0 or current_toe <= 0:
        return 0
    if armor_protection <= 0:
        return min(damage_points, current_toe)
    toe_lost = 0
    remaining_dp = damage_points
    for _ in range(current_toe):
        if remaining_dp <= 0:
            break
        if remaining_dp >= armor_protection:
            toe_lost += 1
            remaining_dp -= armor_protection
        else:
            break
    return toe_lost


# ---------------------------------------------------------------------------
# Terrain shifts (Case 14.3)
# ---------------------------------------------------------------------------


def terrain_aa_shift(terrain: "TerrainType", fort_level: int = 0,
                     *, through_slope: bool = False,
                     through_ridge: bool = False,
                     through_escarpment: bool = False) -> int:
    """Column shift for terrain on Anti-Armor fire (Case 14.3).

    Case 14.3 — Negative shifts reduce effective AA points (defender benefit).
    Shift left one column for Level 1 Fort/Rough/Heavy Vegetation.
    Shift left two columns for Level 2-3 Fort/Mountain.
    Shift left one column for slope hexside.
    Shift left two columns for ridge or escarpment hexside.
    """
    from cna.engine.game_state import TerrainType
    shift = 0
    if fort_level >= 2:
        shift -= 2
    elif fort_level == 1:
        shift -= 1
    if terrain == TerrainType.ROUGH:
        shift -= 1
    elif terrain == TerrainType.MOUNTAIN:
        shift -= 2
    if through_slope:
        shift -= 1
    if through_ridge:
        shift -= 2
    if through_escarpment:
        shift -= 2
    return shift


# ---------------------------------------------------------------------------
# Reassignment to Close Assault (Case 14.26)
# ---------------------------------------------------------------------------


def reassignable_to_assault(aa_actual_points: int, target_has_armor: bool) -> int:
    """Anti-Armor points reassignable to Close Assault (Case 14.26).

    Case 14.26 — If no armor in target hex, up to half of Anti-Armor
    points (rounded down) may be reassigned to Close Assault instead.
    """
    if target_has_armor:
        return 0
    return aa_actual_points // 2
