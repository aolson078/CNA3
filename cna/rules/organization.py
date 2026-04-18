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
