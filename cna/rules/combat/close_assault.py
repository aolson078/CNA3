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


# The CRT maps (final differential, sequential dice roll) to loss
# percentages for attacker and defender separately. Each column has dice
# thresholds that determine which loss band applies.
#
# Extracted from Case 15.79 OCR (references/section_15.md lines 1346-1780).
# Format: (min_diff, max_diff) → list of (dice_max, loss_pct) bands.
# The dice roll is sequential (11-66); the first band whose dice_max >=
# the roll determines the loss percentage. Higher roll = lighter losses.
#
# Engaged range and Retreat hexes are per-column.

@dataclass(frozen=True)
class _CRTColumn:
    """One column of the Close Assault CRT (Case 15.79)."""
    min_diff: int
    max_diff: int
    # Attacker loss bands: list of (dice_max, loss_pct). Ordered low→high.
    att_bands: tuple[tuple[int, int], ...]
    # Defender loss bands.
    def_bands: tuple[tuple[int, int], ...]
    retreat_hexes: int = 0
    engaged_range: tuple[int, int] | None = None  # (min_sum, max_sum) on 2d6 sum
    captured_range: tuple[int, int] | None = None


# Close Assault CRT extracted from Case 15.79 OCR.
# Attacker rows: 50%, 40%, 30%, 25%, 20%, 15%, 10%, 5%.
# Defender rows: same structure, with Retreat and Captured ranges.
_CRT_COLUMNS: tuple[_CRTColumn, ...] = (
    _CRTColumn(-99, -11,
        att_bands=((15, 50), (24, 40), (33, 30), (36, 25), (46, 20), (56, 15), (63, 10), (66, 5)),
        def_bands=((66, 5),),
        engaged_range=(10, 12)),
    _CRTColumn(-10, -8,
        att_bands=((12, 50), (16, 40), (26, 30), (34, 25), (43, 20), (53, 15), (62, 10), (65, 5)),
        def_bands=((13, 10), (26, 5)),
        engaged_range=(10, 12)),
    _CRTColumn(-7, -5,
        att_bands=((12, 40), (23, 30), (32, 25), (41, 20), (51, 15), (56, 10), (63, 5)),
        def_bands=((15, 10), (31, 5)),
        engaged_range=(11, 12)),
    _CRTColumn(-4, -3,
        att_bands=((15, 30), (33, 25), (44, 20), (54, 15), (66, 10)),
        def_bands=((13, 10), (23, 5)),
        engaged_range=(10, 12)),
    _CRTColumn(-2, -1,
        att_bands=((12, 30), (26, 25), (42, 20), (52, 15), (66, 10)),
        def_bands=((13, 10), (22, 5)),
        engaged_range=(10, 12)),
    _CRTColumn(0, 0,
        att_bands=((12, 25), (24, 20), (36, 15), (51, 10), (66, 5)),
        def_bands=((12, 15), (21, 10), (33, 5)),
        retreat_hexes=0),
    _CRTColumn(1, 2,
        att_bands=((12, 20), (16, 15), (31, 10), (66, 5)),
        def_bands=((12, 20), (22, 15), (42, 10), (66, 5)),
        retreat_hexes=1, captured_range=(2, 3)),
    _CRTColumn(3, 4,
        att_bands=((13, 15), (26, 10), (66, 5)),
        def_bands=((14, 25), (25, 20), (42, 15), (54, 10), (66, 5)),
        retreat_hexes=2, captured_range=(2, 4)),
    _CRTColumn(5, 7,
        att_bands=((12, 10), (66, 5)),
        def_bands=((14, 30), (33, 25), (45, 20), (56, 15), (66, 10)),
        retreat_hexes=2, captured_range=(2, 4)),
    _CRTColumn(8, 10,
        att_bands=((66, 5),),
        def_bands=((12, 40), (22, 30), (36, 25), (46, 20), (56, 15), (66, 10)),
        retreat_hexes=3, captured_range=(2, 4)),
    _CRTColumn(11, 13,
        att_bands=((66, 5),),
        def_bands=((13, 40), (26, 30), (41, 25), (56, 20), (66, 15)),
        retreat_hexes=3, captured_range=(2, 3)),
    _CRTColumn(14, 16,
        att_bands=((66, 5),),
        def_bands=((12, 40), (22, 30), (35, 25), (54, 20), (66, 15)),
        retreat_hexes=3, captured_range=(2, 3)),
    _CRTColumn(17, 99,
        att_bands=((66, 5),),
        def_bands=((13, 50), (26, 40), (36, 30), (46, 25), (56, 20), (66, 15)),
        retreat_hexes=3, captured_range=(2, 3)),
)


def _lookup_loss_pct(bands: tuple[tuple[int, int], ...], dice_roll: int) -> int:
    """Find the loss percentage for a sequential dice roll in a band list."""
    for dice_max, pct in bands:
        if dice_roll <= dice_max:
            return pct
    return bands[-1][1] if bands else 0


def _find_crt_column(differential: int) -> _CRTColumn:
    for col in _CRT_COLUMNS:
        if col.min_diff <= differential <= col.max_diff:
            return col
    if differential < _CRT_COLUMNS[0].min_diff:
        return _CRT_COLUMNS[0]
    return _CRT_COLUMNS[-1]


def resolve_close_assault(
    differential: AssaultDifferential,
    attacker_raw_total: int,
    defender_raw_total: int,
    dice: DiceRoller,
) -> CloseAssaultResult:
    """Resolve a Close Assault on the CRT.

    Case 15.7, 15.8 — Each side rolls sequential dice to determine
    their loss percentage from their respective CRT column. Then a
    2d6 sum determines Engaged/Retreat/Captured outcomes.

    Args:
        differential: Pre-computed AssaultDifferential.
        attacker_raw_total: Sum of all attacker Raw Close Assault Points.
        defender_raw_total: Sum of all defender Raw Close Assault Points.
        dice: DiceRoller for all rolls.

    Returns:
        CloseAssaultResult with loss amounts and outcome.
    """
    final = differential.final_differential
    col = _find_crt_column(final)

    # Each side rolls sequential dice for their loss percentage.
    att_roll = dice.roll_concat()
    def_roll = dice.roll_concat()

    att_pct = _lookup_loss_pct(col.att_bands, att_roll)
    def_pct = _lookup_loss_pct(col.def_bands, def_roll)

    # Case 15.8: Attacker rounds UP, Defender rounds DOWN.
    # Exception: Overrun (≥+11) → Defender rounds UP.
    att_losses = math.ceil(attacker_raw_total * att_pct / 100)
    if final >= 11:
        def_losses = math.ceil(defender_raw_total * def_pct / 100)
    else:
        def_losses = int(defender_raw_total * def_pct / 100)

    # Roll for outcome — summed dice (2d6).
    outcome_roll = dice.roll_sum(2)
    outcome = AssaultOutcome.NO_EFFECT
    retreat = 0

    if col.retreat_hexes > 0:
        retreat = col.retreat_hexes
        outcome = AssaultOutcome.RETREAT

    if col.engaged_range:
        lo, hi = col.engaged_range
        if lo <= outcome_roll <= hi:
            outcome = AssaultOutcome.ENGAGED

    if col.captured_range:
        lo, hi = col.captured_range
        if lo <= outcome_roll <= hi:
            outcome = AssaultOutcome.CAPTURED

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
        dice_loss_roll=att_roll,
        dice_outcome_roll=outcome_roll,
        differential=final,
    )


# ---------------------------------------------------------------------------
# Overrun effects (Case 15.77)
# ---------------------------------------------------------------------------


def apply_overrun_vulnerability(
    defender_units: list["Unit"],
    defender_raw_losses: int,
) -> int:
    """Apply vulnerability losses to Forward guns during Overrun (Case 15.77).

    Case 15.77 — In the +11 to +17 Overrun columns, Forward guns are
    subject to vulnerability losses. At minimum 50% of raw points lost
    are taken as vulnerability points against Forward gun TOE.

    Returns additional TOE lost from vulnerability.
    """
    from cna.engine.game_state import UnitType
    vuln_losses = 0
    vuln_raw = max(1, defender_raw_losses // 2)
    for u in defender_units:
        if u.unit_type in {UnitType.ARTILLERY, UnitType.ANTI_TANK}:
            if u.stats.vulnerability > 0 and u.current_toe > 0:
                lost = min(u.current_toe, vuln_raw // max(1, u.stats.vulnerability))
                if lost > 0:
                    u.current_toe -= lost
                    vuln_losses += lost
    return vuln_losses


# ---------------------------------------------------------------------------
# Recce probe bonus (Case 15.9)
# ---------------------------------------------------------------------------


def recce_probe_loss_reduction(
    units: list["Unit"],
    raw_losses: int,
) -> int:
    """Reduce probe losses for Recce-type units (Case 15.9).

    Case 15.9 — Recce probes get a 10% loss reduction.

    Returns the adjusted raw losses.
    """
    from cna.engine.game_state import UnitType
    has_recce = any(u.unit_type == UnitType.RECCE for u in units)
    if has_recce:
        reduction = max(1, raw_losses // 10)
        return max(0, raw_losses - reduction)
    return raw_losses


# ---------------------------------------------------------------------------
# Terrain effects on Close Assault (Case 15.3)
# ---------------------------------------------------------------------------


def terrain_assault_shift(
    terrain: "TerrainType",
    fort_level: int = 0,
    *,
    defender_in_minefield: bool = False,
    attacker_has_engineer: bool = False,
) -> int:
    """Column shift for terrain on Close Assault (Case 15.3).

    Case 15.3 — Terrain shifts favor the defender (negative = left).
    Case 25.22 — Fortification shifts.
    Case 26.26 — Minefield defender bonus.
    Case 23.24 — Engineer bonus vs fortifications.
    """
    from cna.engine.game_state import TerrainType
    shift = 0
    if terrain == TerrainType.ROUGH:
        shift -= 1
    elif terrain == TerrainType.MOUNTAIN:
        shift -= 2
    elif terrain == TerrainType.CITY:
        shift -= 1
    elif terrain == TerrainType.SALT_MARSH:
        shift -= 1
    shift -= fort_level
    if defender_in_minefield:
        shift -= 1
    if attacker_has_engineer and fort_level > 0:
        shift += 1  # Case 23.24: engineer bonus vs forts.
    return shift
