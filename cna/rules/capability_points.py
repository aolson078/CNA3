"""Section 6.0 — The Capability Point System.

Implements Cases 6.11-6.29 and the 6.3 CP Cost Summary.

The CPA system controls all aspects of a unit's activity within an
Operations Stage. Every action costs Capability Points; exceeding the
unit's CPA earns Disorganization Points that lower its Cohesion Level.
CP allocations reset at the start of each Operations Stage (Case 6.16).

Key rules:
  - Case 6.11: Guns with CPA 0 have effective CPA 10 (combat only).
  - Case 6.13: CPA governs one Operations Stage.
  - Case 6.14: CP spent in both Player-A and Player-B portions count.
  - Case 6.15: Parent Formation CPA = lowest of constituent units.
  - Case 6.16: Unused CP don't carry over; not transferrable.
  - Case 6.17: Infantry motorized by trucks assumes truck CPA.
  - Case 6.21: 1 DP per CP spent over CPA, applied immediately.
  - Case 6.22: DP decreases Cohesion Level immediately.
  - Case 6.23: RP increases Cohesion, cap at +10.
  - Case 6.24: Idle stage → 5 RP (capped at Cohesion 0); successful
    assault → 3 RP.
  - Case 6.26: Cohesion ≤ -26 → unit may not move, attack, or defend.
  - Case 6.27-6.28: Multi-unit cohesion averaging for combat.

Cross-references:
  - Case 3.32: HQ CPA = lowest attached unit's CPA.
  - Case 8.17: Non-motorized unit voluntary CP cap = 150% of CPA.
  - Case 17.0: Morale modifications from Cohesion (Case 6.25).
"""

from __future__ import annotations

from cna.engine.errors import RuleViolationError
from cna.engine.game_state import (
    GameState,
    OperationsStage,
    Side,
    Unit,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COHESION_MAX = 10       # Case 6.23 — RP cannot raise Cohesion above +10.
COHESION_SHATTERED = -26  # Case 6.26 — unit cannot act at this level.
IDLE_RP_AWARD = 5       # Case 6.24.1 — RP for idle stage.
ASSAULT_RP_AWARD = 3    # Case 6.24.2 — RP for successful assault.
GUN_EFFECTIVE_CPA = 10  # Case 6.11 — guns with CPA 0 use 10 for combat.


# ---------------------------------------------------------------------------
# Effective CPA
# ---------------------------------------------------------------------------


def effective_cpa(unit: Unit) -> int:
    """Return the effective CPA for *unit* this Operations Stage.

    Case 6.11 — Guns with printed CPA 0 use CPA 10 for all purposes
    except movement.
    Case 6.17 — Motorized infantry uses the truck CPA (stored in
    unit.stats.capability_point_allowance when motorized; the scenario
    or organization module updates the stat on motorization).
    Case 3.32 — HQ CPA equals the slowest attached unit's CPA; this
    is handled during the Organization Phase (Section 19.0) and
    reflected in unit.stats.capability_point_allowance at runtime.
    """
    cpa = unit.stats.capability_point_allowance
    if cpa == 0:
        return GUN_EFFECTIVE_CPA
    return cpa


def voluntary_cp_cap(unit: Unit) -> int:
    """Maximum CP a unit may *voluntarily* spend during its portion of a stage.

    Case 8.17 (correction) — Non-motorized units (CPA ≤ 10) may not
    voluntarily spend more than 150% of their base CPA. Motorized
    units have no voluntary cap beyond their willingness to earn DP.
    """
    cpa = effective_cpa(unit)
    if cpa <= 10:
        return cpa + cpa // 2  # 150% rounded down
    return 9999  # No practical cap for motorized units.


# ---------------------------------------------------------------------------
# CP spending
# ---------------------------------------------------------------------------


def spend_cp(unit: Unit, amount: int) -> int:
    """Spend *amount* CP on *unit*, returning DP earned.

    Cases 6.12, 6.21, 6.22 — Tracks CP spent on the unit. If spending
    pushes the unit past its CPA, Disorganization Points are earned
    and applied to the unit's cohesion_value immediately.

    Returns:
        Number of Disorganization Points earned (0 if still within CPA).

    Raises:
        RuleViolationError (6.26): if unit Cohesion ≤ -26 and it attempts
            to spend CP (unit cannot act).
    """
    if amount <= 0:
        return 0
    _check_shattered(unit)
    unit.capability_points_spent += amount
    overspend = unit.capability_points_spent - effective_cpa(unit)
    if overspend > 0:
        # Only the new overspend portion earns DP, not previously counted.
        prior_overspend = max(0, (unit.capability_points_spent - amount) - effective_cpa(unit))
        new_dp = overspend - prior_overspend
        if new_dp > 0:
            apply_disorganization(unit, new_dp)
            return new_dp
    return 0


def can_spend(unit: Unit, amount: int, *, voluntary: bool = True) -> bool:
    """Check whether *unit* can spend *amount* more CP.

    Case 6.26 — Shattered units cannot act.
    Case 8.17 — Non-motorized units have a voluntary cap.
    Involuntary actions (retreats, reactions during enemy turn) bypass
    the voluntary cap but still cost CP and earn DP.
    """
    if _is_shattered(unit):
        return False
    if voluntary:
        cap = voluntary_cp_cap(unit)
        if unit.capability_points_spent + amount > cap:
            return False
    return True


# ---------------------------------------------------------------------------
# Cohesion / Disorganization / Reorganization
# ---------------------------------------------------------------------------


def cohesion_value(unit: Unit) -> int:
    """Return the numeric Cohesion Level for *unit* (Case 6.22).

    Zero is normal; negative is Disorganized; positive is Reorganized.
    """
    return _get_cohesion_int(unit)


def apply_disorganization(unit: Unit, dp: int) -> None:
    """Apply *dp* Disorganization Points to *unit* immediately.

    Case 6.22 — DP decrease the Cohesion Level. Applied immediately,
    not deferred to end of stage.
    """
    if dp <= 0:
        return
    current = _get_cohesion_int(unit)
    _set_cohesion_int(unit, current - dp)


def apply_reorganization(unit: Unit, rp: int, *, cap_at_zero: bool = False) -> None:
    """Apply *rp* Reorganization Points to *unit* immediately.

    Case 6.23 — RP increase the Cohesion Level, capped at +10.
    Case 6.24.1 — The idle-stage RP award caps Cohesion at 0 (not +10);
    pass cap_at_zero=True for that case.
    """
    if rp <= 0:
        return
    current = _get_cohesion_int(unit)
    new = current + rp
    ceiling = 0 if cap_at_zero else COHESION_MAX
    new = min(new, ceiling)
    _set_cohesion_int(unit, new)


def is_shattered(unit: Unit) -> bool:
    """Case 6.26 — True if Cohesion ≤ -26 (cannot move/attack/defend)."""
    return _is_shattered(unit)


# ---------------------------------------------------------------------------
# Stage-boundary hooks
# ---------------------------------------------------------------------------


def reset_stage_cp(state: GameState) -> None:
    """Reset all units' CP spent to zero at the start of an Operations Stage.

    Case 6.16 — Unused CP don't carry over between stages.
    Called from the sequence-of-play driver at each stage transition.
    """
    for unit in state.units.values():
        unit.capability_points_spent = 0


def award_idle_rp(state: GameState, stage: OperationsStage) -> list[str]:
    """Award 5 RP to units that spent zero CP in the completed stage.

    Case 6.24.1 — "For each Operations Stage in which a unit uses
    absolutely no CP's ... that unit earns five RP's. However, no
    unit may ever increase his Cohesion Level above '0' by this method."

    Returns a list of unit IDs that received the award (for logging).
    """
    awarded: list[str] = []
    for unit in state.units.values():
        if unit.capability_points_spent == 0 and unit.position is not None:
            current = _get_cohesion_int(unit)
            if current < 0:
                apply_reorganization(unit, IDLE_RP_AWARD, cap_at_zero=True)
                awarded.append(unit.id)
    return awarded


# ---------------------------------------------------------------------------
# Multi-unit cohesion averaging (Case 6.27 / 6.28)
# ---------------------------------------------------------------------------


def averaged_cohesion(units: list[Unit]) -> int:
    """Compute the combined Cohesion Level for a group of units in combat.

    Case 6.27 — If units in a Close Assault have different Cohesion
    Levels, the level of the largest unit (by org size / stacking points)
    prevails. If multiple units tie for largest, their Cohesion Levels
    are averaged.

    For Layer 1, we simplify to: average the Cohesion Levels of all
    units, rounded toward zero.
    """
    if not units:
        return 0
    total = sum(_get_cohesion_int(u) for u in units)
    avg = total / len(units)
    return int(avg)  # truncates toward zero


# ---------------------------------------------------------------------------
# Internal cohesion storage
# ---------------------------------------------------------------------------

_COHESION_KEY = "cohesion_value"


def _get_cohesion_int(unit: Unit) -> int:
    """Read the numeric cohesion from unit extras, defaulting to 0."""
    # We don't want to add a field to Unit just for this; it's a detail
    # that only Section 6 cares about. We piggyback on the existing
    # CohesionLevel enum for display (organized/disorganized/shattered)
    # but store the actual integer here.
    # Check extras first; if not present, infer from the enum.
    val = getattr(unit, "_cohesion_int", None)
    if val is not None:
        return val
    return 0


def _set_cohesion_int(unit: Unit, value: int) -> None:
    """Write the numeric cohesion to unit and sync the display enum."""
    from cna.engine.game_state import CohesionLevel
    unit._cohesion_int = value  # type: ignore[attr-defined]
    if value <= COHESION_SHATTERED:
        unit.cohesion = CohesionLevel.SHATTERED
    elif value < 0:
        unit.cohesion = CohesionLevel.DISORGANIZED
    else:
        unit.cohesion = CohesionLevel.ORGANIZED


def _is_shattered(unit: Unit) -> bool:
    return _get_cohesion_int(unit) <= COHESION_SHATTERED


def _check_shattered(unit: Unit) -> None:
    if _is_shattered(unit):
        raise RuleViolationError(
            "6.26",
            f"Unit {unit.id} (Cohesion {_get_cohesion_int(unit)}) cannot act",
        )
