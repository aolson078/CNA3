"""Section 19.0 — Organization and Reorganization.

Implements Cases 19.1-19.9: assigned vs attached units, attachment
restrictions, formation organization charts, shell unit detection,
Axis battle groups, Commonwealth AT augmentation, and rebuilding
depleted units.

Key rules:
  - Case 19.11: Assigned = structural relationship. Attached = same hex,
    represented by parent counter.
  - Case 19.2-19.3: Assignment limits per Formation Organization Chart.
  - Case 19.41: Attach/detach costs 1 CP to parent and child.
  - Case 19.42: Attaching unassigned unit costs 2 CP.
  - Case 19.5: Maximum Attachment Chart limits.
  - Case 19.68: Rebuilding costs 1 CP per 2 TOE points absorbed.
  - Case 19.7: Axis Battle Groups (Kampfgruppen).
  - Case 19.9: Commonwealth battalion AT augmentation.

Cross-references:
  - Case 3.3: HQ semantics.
  - Case 5.2 III.C: Organization Phase.
  - Case 6.12: All organization actions cost CP.
  - Case 9.2: Unit equivalents affected by composition.
  - Case 9.26-9.28: Shell unit determination and org-size reduction.
"""

from __future__ import annotations

import math
from typing import Optional

from cna.engine.errors import RuleViolationError
from cna.engine.game_state import (
    GameState,
    Nationality,
    OrgSize,
    Side,
    Unit,
    UnitType,
)
from cna.rules.capability_points import spend_cp


# ---------------------------------------------------------------------------
# CP costs
# ---------------------------------------------------------------------------

ATTACH_ASSIGNED_CP = 1    # Case 19.41
DETACH_CP = 1             # Case 19.41
ATTACH_UNASSIGNED_CP = 2  # Case 19.42
REBUILD_CP_PER_2_TOE = 1  # Case 19.68


# ---------------------------------------------------------------------------
# Attach / Detach (Cases 19.41-19.45)
# ---------------------------------------------------------------------------


def attach_unit(state: GameState, parent_id: str, child_id: str,
                *, is_assigned: bool = True) -> int:
    """Attach *child* to *parent* (Case 19.41/19.42).

    Both units must be in the same hex. Costs 1 CP each (assigned) or
    2 CP each (unassigned).

    Returns total DP earned by both units.

    Raises:
        RuleViolationError (19.41): if units not in same hex.
    """
    parent = state.units.get(parent_id)
    child = state.units.get(child_id)
    if parent is None or child is None:
        raise RuleViolationError("19.41", "Unit not found")
    if parent.position != child.position:
        raise RuleViolationError("19.41", "Units must be in the same hex to attach")

    cost = ATTACH_ASSIGNED_CP if is_assigned else ATTACH_UNASSIGNED_CP
    dp = spend_cp(parent, cost) + spend_cp(child, cost)

    if child_id not in parent.attached_unit_ids:
        parent.attached_unit_ids.append(child_id)
    child.parent_id = parent_id

    return dp


def detach_unit(state: GameState, parent_id: str, child_id: str) -> int:
    """Detach *child* from *parent* (Case 19.41).

    Costs 1 CP to each unit. Returns total DP earned.

    Raises:
        RuleViolationError (19.41): if child not attached to parent.
    """
    parent = state.units.get(parent_id)
    child = state.units.get(child_id)
    if parent is None or child is None:
        raise RuleViolationError("19.41", "Unit not found")
    if child_id not in parent.attached_unit_ids:
        raise RuleViolationError("19.41", f"{child_id} not attached to {parent_id}")

    dp = spend_cp(parent, DETACH_CP) + spend_cp(child, DETACH_CP)

    parent.attached_unit_ids.remove(child_id)
    child.parent_id = None

    return dp


# ---------------------------------------------------------------------------
# Rebuild (Case 19.68)
# ---------------------------------------------------------------------------


def absorb_replacements(unit: Unit, toe_points: int) -> int:
    """Absorb replacement TOE points into *unit* (Case 19.68).

    Costs 1 CP per 2 TOE points absorbed (rounded up).
    Cannot exceed max TOE strength.

    Returns DP earned.
    """
    actual = min(toe_points, unit.stats.max_toe_strength - unit.current_toe)
    if actual <= 0:
        return 0
    cost = (actual + 1) // 2  # 1 CP per 2 TOE, rounded up.
    dp = spend_cp(unit, cost)
    unit.current_toe += actual
    return dp


# ---------------------------------------------------------------------------
# Shell unit detection (Cases 9.26-9.28, cross-ref Section 19)
# ---------------------------------------------------------------------------

# Maximum assigned brigades for a division and battalions for a brigade
# vary by nationality/type. These are the "normal" maximums from the
# Formation Organization Chart (19.3). Specific units with singular
# org structures override via their OA Chart entries.
_DEFAULT_MAX_BRIGADES: dict[Nationality, int] = {
    Nationality.COMMONWEALTH: 3,
    Nationality.GERMAN: 3,
    Nationality.ITALIAN: 3,
}

_DEFAULT_MAX_BATTALIONS: dict[Nationality, int] = {
    Nationality.COMMONWEALTH: 3,
    Nationality.GERMAN: 4,
    Nationality.ITALIAN: 3,
}


def _count_assigned_by_size(unit: Unit, state: GameState,
                            target_size: OrgSize) -> int:
    """Count how many of *unit*'s assigned units have *target_size*."""
    count = 0
    for uid in unit.assigned_unit_ids:
        child = state.units.get(uid)
        if child is not None and child.org_size == target_size:
            count += 1
    return count


def max_brigades_for(unit: Unit) -> int:
    """Return the maximum number of brigades assignable to *unit*.

    Case 19.3 — Formation Organization Chart default.
    """
    return _DEFAULT_MAX_BRIGADES.get(unit.nationality, 3)


def max_battalions_for(unit: Unit) -> int:
    """Return the maximum number of battalions assignable to *unit*.

    Case 19.3 — Formation Organization Chart default.
    """
    return _DEFAULT_MAX_BATTALIONS.get(unit.nationality, 3)


def is_shell_division(unit: Unit, state: GameState) -> bool:
    """Case 9.26 — A division is a Shell if 50% or fewer of its maximum
    brigades are currently assigned.

    A shell division's org size is treated as one level lower for
    stacking purposes (Case 9.28).
    """
    if unit.org_size != OrgSize.DIVISION:
        return False
    max_bdes = max_brigades_for(unit)
    if max_bdes <= 0:
        return False
    current_bdes = _count_assigned_by_size(unit, state, OrgSize.BRIGADE)
    return current_bdes <= max_bdes * 0.5


def is_shell_brigade(unit: Unit, state: GameState) -> bool:
    """Case 9.26 — A brigade is a Shell if fewer than 2/3 of its maximum
    battalions are currently assigned.

    A shell brigade's org size is treated as one level lower for
    stacking purposes (Case 9.28).
    """
    if unit.org_size != OrgSize.BRIGADE:
        return False
    max_bns = max_battalions_for(unit)
    if max_bns <= 0:
        return False
    current_bns = _count_assigned_by_size(unit, state, OrgSize.BATTALION)
    return current_bns < math.ceil(max_bns * 2 / 3)


def is_shell_battalion(unit: Unit) -> bool:
    """Case 9.26 — A battalion is a Shell if it has fewer than 50% of its
    maximum TOE Strength Points. For artillery units, the threshold
    is 25% (they deplete faster from combat losses).
    """
    if unit.org_size != OrgSize.BATTALION:
        return False
    max_toe = unit.stats.max_toe_strength
    if max_toe <= 0:
        return False
    if unit.unit_type == UnitType.ARTILLERY:
        return unit.current_toe < max_toe * 0.25
    return unit.current_toe < max_toe * 0.5


_ORG_SIZE_REDUCTION: dict[OrgSize, OrgSize] = {
    OrgSize.DIVISION: OrgSize.BRIGADE,
    OrgSize.BRIGADE: OrgSize.BATTALION,
    OrgSize.BATTALION: OrgSize.COMPANY,
}


def effective_org_size(unit: Unit, state: GameState) -> OrgSize:
    """Case 9.28 — If a unit is a Shell, its effective org size is
    reduced by one level for stacking and other purposes.

    Non-shell units return their actual org_size unchanged. Company-
    sized units cannot be reduced further.
    """
    is_shell = False
    match unit.org_size:
        case OrgSize.DIVISION:
            is_shell = is_shell_division(unit, state)
        case OrgSize.BRIGADE:
            is_shell = is_shell_brigade(unit, state)
        case OrgSize.BATTALION:
            is_shell = is_shell_battalion(unit)
    if is_shell:
        return _ORG_SIZE_REDUCTION.get(unit.org_size, unit.org_size)
    return unit.org_size


# ---------------------------------------------------------------------------
# Maximum Attachments Chart (Case 19.5) and Assignment limits (19.2-19.3)
# ---------------------------------------------------------------------------

# Each entry: (max_units, max_tank, max_infantry, notes)
# max_tank / max_infantry = -1 means "no limit on that type"
# See the Maximum Attachment Chart in Section 19.5 for source data.

_AttachLimit = tuple[int, int, int]  # (max_units, max_tank_bns, max_infantry_bns)


MAX_ATTACHMENTS: dict[tuple[Nationality, OrgSize, Optional[UnitType]], _AttachLimit] = {
    # -----------------------------------------------------------------------
    # Commonwealth (Allied)
    # -----------------------------------------------------------------------
    # Armor Division (GT 68+; GT 1-67 differs but we use the later default)
    (Nationality.COMMONWEALTH, OrgSize.DIVISION, UnitType.TANK): (3, 1, 1),
    # Infantry Division
    (Nationality.COMMONWEALTH, OrgSize.DIVISION, UnitType.INFANTRY): (2, 0, 1),
    # Infantry Division (generic, also covers HQ-typed divisions)
    (Nationality.COMMONWEALTH, OrgSize.DIVISION, None): (2, 0, 1),
    # Tank Brigade (GT 68+)
    (Nationality.COMMONWEALTH, OrgSize.BRIGADE, UnitType.TANK): (1, 0, -1),
    # Other Brigade
    (Nationality.COMMONWEALTH, OrgSize.BRIGADE, None): (1, -1, -1),
    # Any battalion
    (Nationality.COMMONWEALTH, OrgSize.BATTALION, None): (1, -1, -1),

    # -----------------------------------------------------------------------
    # German
    # -----------------------------------------------------------------------
    # Armor Division: "1 Brigade and 1 unit or 4 units. No Tank."
    (Nationality.GERMAN, OrgSize.DIVISION, UnitType.TANK): (4, 0, -1),
    # Infantry Division: "1 Brigade or 3 units. No Tank."
    (Nationality.GERMAN, OrgSize.DIVISION, UnitType.INFANTRY): (3, 0, -1),
    (Nationality.GERMAN, OrgSize.DIVISION, None): (4, 0, -1),
    # Infantry or Armor Regiment: 1 unit
    (Nationality.GERMAN, OrgSize.BRIGADE, None): (1, -1, -1),
    # Any battalion: 1 Company
    (Nationality.GERMAN, OrgSize.BATTALION, None): (1, -1, -1),

    # -----------------------------------------------------------------------
    # Italian
    # -----------------------------------------------------------------------
    # Armor Division / Tank Group: 2 units
    (Nationality.ITALIAN, OrgSize.DIVISION, UnitType.TANK): (2, -1, -1),
    # Infantry Division: "2 units. 1 Infantry or 1 Tank."
    (Nationality.ITALIAN, OrgSize.DIVISION, UnitType.INFANTRY): (2, 1, 1),
    (Nationality.ITALIAN, OrgSize.DIVISION, None): (2, 1, 1),
    # Brigade/Regiment: 1 unit
    (Nationality.ITALIAN, OrgSize.BRIGADE, None): (1, -1, -1),
    # Any battalion: No units (Italian battalions get no attachments)
    (Nationality.ITALIAN, OrgSize.BATTALION, None): (0, -1, -1),
}


def _lookup_attachment_limit(
    parent: Unit,
) -> Optional[_AttachLimit]:
    """Look up the maximum attachment limits for *parent* from the chart.

    Tries (nationality, org_size, unit_type) first, then falls back
    to (nationality, org_size, None) for the generic entry.
    """
    key = (parent.nationality, parent.org_size, parent.unit_type)
    limit = MAX_ATTACHMENTS.get(key)
    if limit is not None:
        return limit
    generic_key = (parent.nationality, parent.org_size, None)
    return MAX_ATTACHMENTS.get(generic_key)


def _count_non_assigned_attached(parent: Unit, state: GameState) -> int:
    """Count units attached to *parent* that are NOT in its assigned list."""
    assigned_set = set(parent.assigned_unit_ids)
    count = 0
    for uid in parent.attached_unit_ids:
        if uid not in assigned_set:
            count += 1
    return count


def _count_attached_by_type(parent: Unit, state: GameState,
                            utype: UnitType) -> int:
    """Count non-assigned attached units of a given type."""
    assigned_set = set(parent.assigned_unit_ids)
    count = 0
    for uid in parent.attached_unit_ids:
        if uid in assigned_set:
            continue
        child = state.units.get(uid)
        if child is not None and child.unit_type == utype:
            count += 1
    return count


def can_assign(parent: Unit, child: Unit, state: GameState) -> bool:
    """Case 19.2, 19.3 — Check whether *child* can be assigned to *parent*.

    Returns True if *parent* has not reached its maximum assignment
    limit for units of *child*'s org_size, and *child* is currently
    independent (no existing assignment per Case 19.28). The child
    must currently be attached to the parent (Case 19.21).

    See Case 19.3 and the Formation Organization Chart for limits.
    """
    # Case 19.28: only independent units may be assigned
    if child.parent_id is not None:
        return False
    # Case 19.21: must be currently attached
    if child.id not in parent.attached_unit_ids:
        return False
    # Check assignment capacity based on org size
    if parent.org_size == OrgSize.DIVISION:
        max_count = max_brigades_for(parent)
        current = _count_assigned_by_size(parent, state, OrgSize.BRIGADE)
        if child.org_size == OrgSize.BRIGADE:
            return current < max_count
    elif parent.org_size == OrgSize.BRIGADE:
        max_count = max_battalions_for(parent)
        current = _count_assigned_by_size(parent, state, OrgSize.BATTALION)
        if child.org_size == OrgSize.BATTALION:
            return current < max_count
    return False


def validate_attachment(parent: Unit, child: Unit) -> None:
    """Case 19.41, 19.42 — Validate that *child* may be attached to *parent*.

    Checks:
      - Units are in the same hex (Case 19.41).
      - Compatible org sizes (child must be smaller than parent).

    Raises:
        RuleViolationError (19.41): if units are not in the same hex.
        RuleViolationError (19.4): if org sizes are incompatible.
    """
    if parent.position != child.position:
        raise RuleViolationError(
            "19.41", "Units must be in the same hex to attach"
        )
    # A unit cannot attach to something of equal or smaller org size
    _SIZE_ORDER = {
        OrgSize.DIVISION: 3,
        OrgSize.BRIGADE: 2,
        OrgSize.BATTALION: 1,
        OrgSize.COMPANY: 0,
    }
    parent_rank = _SIZE_ORDER.get(parent.org_size, 0)
    child_rank = _SIZE_ORDER.get(child.org_size, 0)
    if child_rank >= parent_rank:
        raise RuleViolationError(
            "19.4",
            f"Cannot attach {child.org_size.value} to {parent.org_size.value}: "
            "child must be smaller than parent",
        )


def can_attach(parent: Unit, child: Unit, state: GameState) -> bool:
    """Case 19.4, 19.5 — Check whether *child* can be attached to *parent*
    within the Maximum Attachment Chart limits.

    Returns True if the attachment would not exceed the chart limits.
    Does NOT check hex co-location (use validate_attachment for that).
    """
    limit = _lookup_attachment_limit(parent)
    if limit is None:
        # No entry in chart → no attachments allowed
        return False
    max_units, max_tank, max_infantry = limit
    current_extra = _count_non_assigned_attached(parent, state)
    if current_extra >= max_units:
        return False
    # Check type restrictions
    if max_tank == 0 and child.unit_type == UnitType.TANK:
        return False
    if max_infantry == 0 and child.unit_type == UnitType.INFANTRY:
        return False
    if max_tank > 0 and child.unit_type == UnitType.TANK:
        if _count_attached_by_type(parent, state, UnitType.TANK) >= max_tank:
            return False
    if max_infantry > 0 and child.unit_type == UnitType.INFANTRY:
        if _count_attached_by_type(parent, state, UnitType.INFANTRY) >= max_infantry:
            return False
    return True


# ---------------------------------------------------------------------------
# Axis Battle Groups (Case 19.7)
# ---------------------------------------------------------------------------

# Case 19.72: German — max 4 battalion-sized, no more than 1 tank bn,
#   no more than 2 infantry bns, up to 2 additional companies.
# Case 19.73: Italian — max 3 battalion-sized, max 2 infantry, max 1 armor,
#   1 company. Max 2 Italian BGs in existence at once.

GERMAN_BG_MAX_BNS = 4
GERMAN_BG_MAX_TANK_BNS = 1
GERMAN_BG_MAX_INF_BNS = 2
GERMAN_BG_MAX_COYS = 2

ITALIAN_BG_MAX_BNS = 3
ITALIAN_BG_MAX_TANK_BNS = 1
ITALIAN_BG_MAX_INF_BNS = 2
ITALIAN_BG_MAX_COYS = 1
ITALIAN_BG_MAX_ACTIVE = 2


def can_form_battle_group(units: list[Unit],
                          state: Optional[GameState] = None) -> bool:
    """Case 19.71-19.73 — Check whether the given *units* can form a
    valid Axis Battle Group.

    Requirements:
      - All units must be Axis side (Case 19.71).
      - All units must be in the same hex (Case 19.71).
      - All units must be the same nationality (German or Italian).
      - Must conform to composition limits for that nationality.

    If *state* is provided and the units are Italian, also checks that
    no more than two Italian battle groups exist (Case 19.73).

    Returns True if valid, False otherwise.
    """
    if not units:
        return False

    # Must all be Axis
    if any(u.side != Side.AXIS for u in units):
        return False

    # Must all share a nationality
    nationalities = {u.nationality for u in units}
    if len(nationalities) != 1:
        return False
    nat = nationalities.pop()
    if nat not in (Nationality.GERMAN, Nationality.ITALIAN):
        return False

    # Must all be in the same hex
    positions = {u.position for u in units}
    if len(positions) != 1 or None in positions:
        return False

    bns = [u for u in units if u.org_size == OrgSize.BATTALION]
    coys = [u for u in units if u.org_size == OrgSize.COMPANY]
    tank_bns = [u for u in bns if u.unit_type == UnitType.TANK]
    inf_bns = [u for u in bns if u.unit_type == UnitType.INFANTRY]

    # Reject units that are neither battalion nor company
    if len(bns) + len(coys) != len(units):
        return False

    if nat == Nationality.GERMAN:
        if len(bns) > GERMAN_BG_MAX_BNS:
            return False
        if len(tank_bns) > GERMAN_BG_MAX_TANK_BNS:
            return False
        if len(inf_bns) > GERMAN_BG_MAX_INF_BNS:
            return False
        if len(coys) > GERMAN_BG_MAX_COYS:
            return False
    else:  # Italian
        if len(bns) > ITALIAN_BG_MAX_BNS:
            return False
        if len(tank_bns) > ITALIAN_BG_MAX_TANK_BNS:
            return False
        if len(inf_bns) > ITALIAN_BG_MAX_INF_BNS:
            return False
        if len(coys) > ITALIAN_BG_MAX_COYS:
            return False
        # Case 19.73: max 2 Italian BGs active at once
        if state is not None:
            existing_bgs = sum(
                1 for u in state.units.values()
                if (u.unit_type == UnitType.HEADQUARTERS
                    and u.nationality == Nationality.ITALIAN
                    and "battle_group" in u.id)
            )
            if existing_bgs >= ITALIAN_BG_MAX_ACTIVE:
                return False

    return True


# ---------------------------------------------------------------------------
# Commonwealth battalion AT augmentation (Case 19.9)
# ---------------------------------------------------------------------------

CW_AT_AUGMENT_START_GT = 75  # Case 19.91: available from GT 75 onward
CW_AT_MAX_MOTORIZED = 2      # Case 19.94: motorized infantry → 2 AT TOE
CW_AT_MAX_NON_MOTORIZED = 1  # Case 19.94: non-motorized → 1 AT TOE


def _is_eligible_for_at_augment(battalion: Unit) -> bool:
    """Case 19.92 — Check if a CW infantry battalion is eligible for AT
    augmentation.

    Must have CPA of 10 (with or without motorized '+') and
    offensive/defensive close assault ratings of 1/2 or 2/2.
    """
    if battalion.nationality != Nationality.COMMONWEALTH:
        return False
    if battalion.org_size != OrgSize.BATTALION:
        return False
    if battalion.unit_type != UnitType.INFANTRY:
        return False
    cpa = battalion.stats.capability_point_allowance
    if cpa < 10:
        return False
    off = battalion.stats.offensive_close_assault
    dfn = battalion.stats.defensive_close_assault
    if (off, dfn) not in ((1, 2), (2, 2)):
        return False
    return True


def augment_with_at(battalion: Unit, at_unit: Unit,
                    state: Optional[GameState] = None) -> None:
    """Case 19.91-19.98 — Attach Anti-Tank TOE Strength Points to a
    Commonwealth infantry battalion.

    The *at_unit* contributes its current_toe as AT augmentation to
    the *battalion*. The AT points are limited per Case 19.94:
      - Motorized infantry (CPA 10+): max 2 AT TOE points.
      - Non-motorized infantry (CPA 10): max 1 AT TOE point.

    Case 19.96: No AT may be assigned if any AT regiment in the
    battalion's parent unit(s) is below maximum TOE strength.

    Case 19.98: AT TOE points do not affect shell determinations.

    Raises:
        RuleViolationError (19.91): if game turn is before GT 75 and
            state is provided.
        RuleViolationError (19.92): if battalion is ineligible.
        RuleViolationError (19.94): if AT would exceed allowed max.
        RuleViolationError (19.96): if parent's AT regiment is
            below max TOE.
    """
    # Check game turn
    if state is not None and state.game_turn < CW_AT_AUGMENT_START_GT:
        raise RuleViolationError(
            "19.91",
            "Commonwealth AT augmentation not available before Game-Turn 75",
        )

    # Check eligibility
    if not _is_eligible_for_at_augment(battalion):
        raise RuleViolationError(
            "19.92",
            f"Battalion {battalion.id} does not meet AT augmentation criteria "
            "(CPA 10, close assault 1/2 or 2/2, CW infantry battalion)",
        )

    # Determine max AT points
    if battalion.is_motorized or battalion.stats.capability_point_allowance > 10:
        max_at = CW_AT_MAX_MOTORIZED
    else:
        max_at = CW_AT_MAX_NON_MOTORIZED

    # Check AT unit type
    if at_unit.unit_type != UnitType.ANTI_TANK:
        raise RuleViolationError(
            "19.93",
            f"Unit {at_unit.id} is not an anti-tank unit",
        )

    # Check capacity — use the battalion's anti_armor_strength as
    # a proxy for currently-assigned AT TOE points.
    current_at_toe = getattr(battalion, "_at_augment_toe", 0)
    at_points = at_unit.current_toe
    if current_at_toe + at_points > max_at:
        raise RuleViolationError(
            "19.94",
            f"Would exceed maximum AT augmentation of {max_at} for "
            f"battalion {battalion.id} (current: {current_at_toe}, "
            f"adding: {at_points})",
        )

    # Case 19.96: check parent's AT regiment is at max TOE
    if state is not None and battalion.parent_id is not None:
        parent = state.units.get(battalion.parent_id)
        if parent is not None:
            for uid in parent.assigned_unit_ids:
                sibling = state.units.get(uid)
                if (sibling is not None
                        and sibling.unit_type == UnitType.ANTI_TANK
                        and sibling.current_toe < sibling.stats.max_toe_strength):
                    raise RuleViolationError(
                        "19.96",
                        f"AT regiment {sibling.id} in parent {parent.id} is "
                        f"below max TOE ({sibling.current_toe}/"
                        f"{sibling.stats.max_toe_strength}); AT augmentation "
                        "not permitted",
                    )

    # Apply augmentation
    battalion._at_augment_toe = current_at_toe + at_points  # type: ignore[attr-defined]
    battalion.stats.anti_armor_strength += at_points
