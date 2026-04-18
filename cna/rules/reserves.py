"""Section 18.0 — Reserve Status.

Implements Cases 18.1-18.2: which units may be placed in Reserve,
effects of Reserve Status, and Reserve release.

Reserve Status allows a unit to move again after combat ends within
the same Movement/Combat Phase, bypassing the Case 8.23 restriction
(units >2 hexes from enemy cannot continue moving). Reserve units
are marked with Reserve I or Reserve II markers.

Key rules:
  - Case 18.1: Which units may be placed in Reserve. Only motorized
    combat units may be designated Reserve. Placing in Reserve costs
    2 CP. Units in Reserve may not voluntarily move or attack until
    released.
  - Case 18.2: Effects of Reserve Status.
    Reserve I: released during Reserve Release Segment (Case 5.2 III.G.4).
    Reserve II: released in a subsequent Movement Segment when an enemy
    unit moves within 2 hexes.
    Released units may then move and fight normally.

Cross-references:
  - Case 5.2 III.F: Reserve Designation Phase.
  - Case 5.2 III.G.4: Reserve Release Segment.
  - Case 8.23: Non-reserve units >2 hexes from enemy cannot continue.
  - Case 6.12: Placing in Reserve costs CP.
"""

from __future__ import annotations

from cna.engine.errors import RuleViolationError
from cna.engine.game_state import (
    GameState,
    ReserveStatus,
    Side,
    Unit,
    UnitType,
)
from cna.rules.capability_points import can_spend, spend_cp
from cna.rules.land_movement import is_motorized


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RESERVE_CP_COST = 2  # Case 18.1: placing in Reserve costs 2 CP.


# ---------------------------------------------------------------------------
# Eligibility (Case 18.1)
# ---------------------------------------------------------------------------


def can_designate_reserve(unit: Unit) -> bool:
    """Whether *unit* may be placed in Reserve (Case 18.1).

    Case 18.1 — Only motorized combat units may be designated Reserve.
    Unit must not already be in Reserve or pinned.
    """
    if not unit.is_combat_unit():
        return False
    if not is_motorized(unit):
        return False
    if unit.reserve_status != ReserveStatus.NONE:
        return False
    if unit.pinned:
        return False
    return True


# ---------------------------------------------------------------------------
# Designation
# ---------------------------------------------------------------------------


def designate_reserve(
    unit: Unit,
    level: ReserveStatus = ReserveStatus.RESERVE_I,
) -> int:
    """Place *unit* in Reserve Status (Case 18.1).

    Costs 2 CP. Returns DP earned (if any, from exceeding CPA).

    Raises:
        RuleViolationError (18.1): if unit is not eligible.
    """
    if not can_designate_reserve(unit):
        raise RuleViolationError(
            "18.1",
            f"Unit {unit.id} cannot be designated Reserve "
            f"(must be motorized combat unit, not pinned)",
        )
    dp = spend_cp(unit, RESERVE_CP_COST)
    unit.reserve_status = level
    return dp


# ---------------------------------------------------------------------------
# Release (Case 18.2)
# ---------------------------------------------------------------------------


def release_reserve(unit: Unit) -> None:
    """Release *unit* from Reserve Status (Case 18.2).

    Case 5.2 III.G.4 — Reserve Release Segment. Released units may then
    move and fight normally for the remainder of the Movement/Combat Phase.
    """
    unit.reserve_status = ReserveStatus.NONE


def release_all_reserves(state: GameState, side: Side) -> list[str]:
    """Release all Reserve units belonging to *side* (Case 18.2).

    Returns list of released unit IDs.
    """
    released: list[str] = []
    for unit in state.units.values():
        if unit.side == side and unit.reserve_status != ReserveStatus.NONE:
            release_reserve(unit)
            released.append(unit.id)
    return released


# ---------------------------------------------------------------------------
# Phase handler
# ---------------------------------------------------------------------------


def handle_reserve_release(state: GameState, step) -> None:
    """PhaseDriver handler for the Reserve Release Segment.

    Case 5.2 III.G.4 — Auto-releases all reserves for the active side.
    In a full interactive implementation, the player would choose which
    reserves to release; for Layer 1 we release all.
    """
    from cna.engine.game_state import Phase
    if state.phase != Phase.MOVEMENT_AND_COMBAT:
        return
    released = release_all_reserves(state, state.active_side)
    if released:
        state.log(
            f"Released {len(released)} reserve unit(s)",
            category="reserves",
        )
