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
  - Case 14.5: Destroyed tank markers.
  - Case 14.6: Anti-Armor CRT.

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

# The AA-CRT is indexed by anti-armor points band and sequential dice roll.
# Results are Damage Points applied against target armor.
# OCR is garbled; these are simplified placeholders.
# TODO-14.6: replace with manually verified CRT.

_DICE_BANDS: list[tuple[int, int]] = [
    (11, 21), (22, 32), (33, 43), (44, 54), (55, 65), (66, 66),
]

# (min_aa, max_aa) → damage per dice band.
_AA_CRT: list[tuple[tuple[int, int], list[int]]] = [
    ((0, 0),   [0, 0, 0, 0, 0, 0]),
    ((1, 2),   [0, 0, 0, 0, 1, 2]),
    ((3, 4),   [0, 0, 0, 1, 2, 3]),
    ((5, 6),   [0, 0, 1, 2, 3, 4]),
    ((7, 8),   [0, 1, 2, 3, 4, 6]),
    ((9, 10),  [0, 1, 2, 4, 5, 8]),
    ((11, 12), [1, 2, 3, 5, 7, 10]),
    ((13, 14), [1, 2, 4, 6, 8, 12]),
    ((15, 99), [2, 3, 5, 7, 10, 15]),
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
) -> AntiArmorResult:
    """Resolve anti-armor fire.

    Case 14.6 — Roll on the Anti-Armor CRT.

    Args:
        aa_actual_points: Total Actual Anti-Armor Points firing.
        dice: DiceRoller for the sequential roll.
        column_shifts: Terrain/fortification shifts (negative = left/defender).

    Returns:
        AntiArmorResult with Damage Points to apply.
    """
    if aa_actual_points <= 0:
        return AntiArmorResult()

    roll = dice.roll_concat()
    band = _dice_band_index(roll)
    band = max(0, min(band + column_shifts, len(_DICE_BANDS) - 1))

    damage = 0
    for (lo, hi), results in _AA_CRT:
        if lo <= aa_actual_points <= hi:
            damage = results[band]
            break
    else:
        damage = _AA_CRT[-1][1][band]

    return AntiArmorResult(
        damage_points=damage,
        dice_roll=roll,
        aa_points=aa_actual_points,
    )


def _dice_band_index(roll: int) -> int:
    for i, (lo, hi) in enumerate(_DICE_BANDS):
        if lo <= roll <= hi:
            return i
    return len(_DICE_BANDS) - 1


def apply_armor_damage(
    damage_points: int,
    armor_protection: int,
    current_toe: int,
) -> int:
    """Calculate TOE losses from Damage Points vs. Armor Protection.

    Case 14.4 — Each Armor Protection point absorbs one Damage Point
    per TOE Strength Point. Excess damage destroys TOE.

    Returns:
        Number of TOE Strength Points destroyed.
    """
    if damage_points <= 0 or current_toe <= 0:
        return 0
    if armor_protection <= 0:
        return min(damage_points, current_toe)
    # Each TOE point can absorb `armor_protection` damage.
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
