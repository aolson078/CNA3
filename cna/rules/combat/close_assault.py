"""Section 15.0 — Close Assault.

Implements Cases 15.1-15.9: which units participate, assault differential
calculation, terrain/morale/org-size modifiers, combined arms, probes,
and the Close Assault CRT.

Close Assault is the decisive combat step. The Phasing Player attacks
with Offensive Close Assault points; the Defender uses Defensive points.
The Assault Differential (attacker - defender) indexes the CRT, modified
by terrain, morale, org-size difference, and 2:1 raw strength superiority.

Key rules:
  - Case 15.1: Combat units with Offensive/Defensive ratings participate.
  - Case 15.2: Assault differential = attacker actual - defender actual.
  - Case 15.3: Terrain column shifts.
  - Case 15.4: Combined Arms — unsupported tanks penalized.
  - Case 15.5: Org-size difference shifts.
  - Case 15.6: Morale modifies the differential.
  - Case 15.7: Close Assault CRT.
  - Case 15.8: Casualties — percentage of Raw Strength.
  - Case 15.9: Probes — limited-strength assault.

Close Assault CRT results:
  - Loss percentages (5%-50%) for attacker and defender.
  - Engaged/Retreat/Captured outcomes on a second dice roll.
  - Attacker rounds losses UP; Defender rounds DOWN.
  - Overrun (differential ≥ +11): Defender rounds UP.

Cross-references:
  - Case 6.21: Exceeding CPA from combat CP costs.
  - Case 6.24.2: Successful assault → 3 RP.
  - Case 10.3: ZoC combat requirements (mandatory assault).
  - Case 11.2: CP costs for combat.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from cna.engine.dice import DiceRoller
from cna.engine.game_state import OrgSize, Unit
from cna.rules.combat.common import actual_points, raw_points


# ---------------------------------------------------------------------------
# Org-size differential (Case 15.5)
# ---------------------------------------------------------------------------

_ORG_SIZE_ORDER: dict[OrgSize, int] = {
    OrgSize.COMPANY: 0,
    OrgSize.BATTALION: 1,
    OrgSize.BRIGADE: 2,
    OrgSize.DIVISION: 3,
}

# Case 15.53 — column shifts for org-size difference.
_ORG_SIZE_SHIFTS: dict[int, int] = {
    0: 0,
    1: 1,  # one level difference
    2: 2,  # two levels
    3: 4,  # three levels (division vs company)
}


def org_size_shift(larger: OrgSize, smaller: OrgSize) -> int:
    """Column shift for org-size difference (Case 15.53).

    Positive shift favors the larger side.
    """
    diff = abs(_ORG_SIZE_ORDER.get(larger, 0) - _ORG_SIZE_ORDER.get(smaller, 0))
    return _ORG_SIZE_SHIFTS.get(diff, diff)


# ---------------------------------------------------------------------------
# Combined Arms (Case 15.4)
# ---------------------------------------------------------------------------


def unsupported_tank_penalty(tank_toe: int, infantry_toe: int) -> int:
    """Actual Point penalty for unsupported tanks (Case 15.4).

    Tanks require equal infantry support. For every 1-3 unsupported
    tank TOE, reduce Actual Close Assault Strength by 1. Max penalty 4.
    """
    if tank_toe <= 0:
        return 0
    unsupported = max(0, tank_toe - infantry_toe)
    if unsupported <= 0:
        return 0
    penalty = math.ceil(unsupported / 3)
    return min(penalty, 4)


# ---------------------------------------------------------------------------
# Assault differential calculation
# ---------------------------------------------------------------------------


@dataclass
class AssaultDifferential:
    """Computed assault differential with all modifiers.

    Case 15.2 — Basic Differential = Attacker Actual - Defender Actual.
    Adjusted by terrain, morale, org-size, 2:1 raw superiority.
    """

    attacker_actual: int = 0
    defender_actual: int = 0
    basic_differential: int = 0
    terrain_shift: int = 0
    morale_shift: int = 0
    org_size_shift: int = 0
    raw_2to1_shift: int = 0
    combined_arms_penalty: int = 0
    final_differential: int = 0
    is_overrun: bool = False
    is_probe: bool = False


def compute_assault_differential(
    attacker_raw: int,
    defender_raw: int,
    *,
    terrain_shift: int = 0,
    morale_shift: int = 0,
    attacker_org: OrgSize = OrgSize.BATTALION,
    defender_org: OrgSize = OrgSize.BATTALION,
    attacker_tank_toe: int = 0,
    attacker_infantry_toe: int = 0,
    is_probe: bool = False,
) -> AssaultDifferential:
    """Compute the full assault differential.

    Case 15.2, 15.3, 15.4, 15.5, 15.51, 15.6 — Combines all modifiers.

    Args:
        attacker_raw: Total Raw Offensive Close Assault Points.
        defender_raw: Total Raw Defensive Close Assault Points.
        terrain_shift: Column shift from terrain (negative = defender benefit).
        morale_shift: Attacker adjusted morale - Defender adjusted morale.
        attacker_org: Largest org-size on attacking side.
        defender_org: Largest org-size on defending side.
        attacker_tank_toe: TOE points of tanks in assault.
        attacker_infantry_toe: TOE points of infantry supporting tanks.
        is_probe: True if this is a Probe (Case 15.9).
    """
    att_actual = actual_points(attacker_raw)
    def_actual = actual_points(defender_raw)

    # Case 15.4: combined arms penalty.
    ca_penalty = unsupported_tank_penalty(attacker_tank_toe, attacker_infantry_toe)
    att_actual = max(0, att_actual - ca_penalty)

    basic = att_actual - def_actual

    # Case 15.5: org-size shift.
    att_ord = _ORG_SIZE_ORDER.get(attacker_org, 1)
    def_ord = _ORG_SIZE_ORDER.get(defender_org, 1)
    if att_ord > def_ord:
        os_shift = org_size_shift(attacker_org, defender_org)
    elif def_ord > att_ord:
        os_shift = -org_size_shift(defender_org, attacker_org)
    else:
        os_shift = 0

    # Case 15.51: 2:1 raw strength superiority.
    raw_shift = 0
    if attacker_raw > 0 and defender_raw > 0:
        if attacker_raw >= 2 * defender_raw:
            raw_shift = 2
        elif defender_raw >= 2 * attacker_raw:
            raw_shift = -2

    final = basic + terrain_shift + morale_shift + os_shift + raw_shift

    return AssaultDifferential(
        attacker_actual=att_actual,
        defender_actual=def_actual,
        basic_differential=basic,
        terrain_shift=terrain_shift,
        morale_shift=morale_shift,
        org_size_shift=os_shift,
        raw_2to1_shift=raw_shift,
        combined_arms_penalty=ca_penalty,
        final_differential=final,
        is_overrun=final >= 11,
        is_probe=is_probe,
    )


# ---------------------------------------------------------------------------
# Close Assault CRT (Case 15.7)
# ---------------------------------------------------------------------------

class AssaultOutcome(str, Enum):
    """Possible Close Assault CRT outcomes (Case 15.7)."""
    NO_EFFECT = "no_effect"
    ENGAGED = "engaged"
    RETREAT = "retreat"
    CAPTURED = "captured"


@dataclass(frozen=True)
class CloseAssaultResult:
    """Full result of a Close Assault resolution.

    Case 15.7, 15.8 — Loss percentages, Engaged/Retreat/Captured outcomes.
    """
    attacker_loss_pct: int = 0
    defender_loss_pct: int = 0
    attacker_raw_losses: int = 0
    defender_raw_losses: int = 0
    outcome: AssaultOutcome = AssaultOutcome.NO_EFFECT
    retreat_hexes: int = 0
    dice_loss_roll: int = 0
    dice_outcome_roll: int = 0
    differential: int = 0


# The CRT maps final differential to (attacker_loss_pct, defender_loss_pct).
# OCR is too garbled for exact values; this is a simplified model.
# TODO-15.7: replace with manually verified CRT.
_CRT_TABLE: list[tuple[int, int, int, int, int]] = [
    # (min_diff, max_diff, att_loss_%, def_loss_%, retreat_hexes)
    (-99, -11, 50, 5,  0),
    (-10, -8,  40, 5,  0),
    (-7,  -5,  30, 10, 0),
    (-4,  -3,  25, 10, 0),
    (-2,  -1,  20, 15, 0),
    (0,    0,  15, 15, 0),
    (1,    2,  15, 20, 1),
    (3,    4,  10, 25, 2),
    (5,    7,  10, 30, 2),
    (8,   10,  5,  40, 3),
    (11,  17,  5,  50, 3),  # Overrun range.
    (18,  99,  5,  50, 3),
]


def _lookup_crt(differential: int) -> tuple[int, int, int]:
    """Return (att_loss_%, def_loss_%, retreat_hexes) for *differential*."""
    for min_d, max_d, att, def_, ret in _CRT_TABLE:
        if min_d <= differential <= max_d:
            return att, def_, ret
    return 15, 15, 0


def resolve_close_assault(
    differential: AssaultDifferential,
    attacker_raw_total: int,
    defender_raw_total: int,
    dice: DiceRoller,
) -> CloseAssaultResult:
    """Resolve a Close Assault on the CRT.

    Case 15.7, 15.8 — Roll for losses, then roll for outcome
    (Engaged / Retreat / Captured).

    Args:
        differential: Pre-computed AssaultDifferential.
        attacker_raw_total: Sum of all attacker Raw Close Assault Points.
        defender_raw_total: Sum of all defender Raw Close Assault Points.
        dice: DiceRoller for both rolls.

    Returns:
        CloseAssaultResult with loss amounts and outcome.
    """
    final = differential.final_differential
    att_pct, def_pct, retreat = _lookup_crt(final)

    # Roll for losses — sequential dice (Case 15.8).
    loss_roll = dice.roll_concat()

    # Apply loss percentages.
    # Case 15.8: Attacker rounds UP, Defender rounds DOWN.
    # Exception: Overrun → Defender rounds UP.
    att_losses = math.ceil(attacker_raw_total * att_pct / 100)
    if final >= 11:
        def_losses = math.ceil(defender_raw_total * def_pct / 100)
    else:
        def_losses = int(defender_raw_total * def_pct / 100)  # floor

    # Roll for outcome — summed dice.
    outcome_roll = dice.roll_sum(2)
    if final >= 1 and retreat > 0:
        outcome = AssaultOutcome.RETREAT
    elif final <= -1:
        outcome = AssaultOutcome.ENGAGED if outcome_roll >= 8 else AssaultOutcome.NO_EFFECT
    else:
        outcome = AssaultOutcome.NO_EFFECT

    # Case 15.9: Probes — Engaged results ignored.
    if differential.is_probe and outcome == AssaultOutcome.ENGAGED:
        outcome = AssaultOutcome.NO_EFFECT

    return CloseAssaultResult(
        attacker_loss_pct=att_pct,
        defender_loss_pct=def_pct,
        attacker_raw_losses=att_losses,
        defender_raw_losses=def_losses,
        outcome=outcome,
        retreat_hexes=retreat,
        dice_loss_roll=loss_roll,
        dice_outcome_roll=outcome_roll,
        differential=final,
    )
