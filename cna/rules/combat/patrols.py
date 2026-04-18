"""Section 16.0 — Patrols and Reconnaissance.

Implements Cases 16.1-16.8: patrol eligibility, restrictions, losses,
dummy tank formations, patrol results, and the Patrol Survival /
Reconnaissance / Objective Loss tables.

Patrols gather intelligence on enemy units in adjacent hexes. Only
Recce-type, Armored Car, and certain other units may patrol. Patrols
risk losses (Patrol Survival Table) and reveal limited information
about enemy composition (Reconnaissance Table).

Key rules:
  - Case 16.1: Recce-type and Armored Car units may patrol.
  - Case 16.2: Patrol restrictions (must not be in ZoC, can't patrol
    same hex twice per stage, costs 2 CP).
  - Case 16.3: Patrol losses — Patrol Survival Table.
  - Case 16.4: Dummy Tank Formations can deceive patrols.
  - Case 16.5: Results reveal unit types/counts (limited per Case 3.6).
  - Case 16.6: Patrol Survival Table (dice-based).
  - Case 16.7: Reconnaissance Table (what information is revealed).
  - Case 16.8: Objective Loss Table.

Cross-references:
  - Case 3.6: Limited intelligence governs what patrols reveal.
  - Case 5.2 III.L: Patrol Phase occurs after Repair Phase.
  - Case 8.14: Units in ZoC cannot patrol.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from cna.engine.dice import DiceRoller
from cna.engine.game_state import (
    GameState,
    HexCoord,
    Side,
    Unit,
    UnitType,
)


# ---------------------------------------------------------------------------
# Patrol eligibility (Case 16.1)
# ---------------------------------------------------------------------------

_PATROL_CAPABLE_TYPES: frozenset[UnitType] = frozenset({
    UnitType.RECCE,
})


def can_patrol(unit: Unit) -> bool:
    """Whether *unit* may conduct a patrol (Case 16.1).

    Case 16.1 — Recce-type and Armored Car units may patrol. HQ with
    Recce attached may also patrol via the attached unit.
    """
    if unit.unit_type in _PATROL_CAPABLE_TYPES:
        return True
    return False


PATROL_CP_COST = 2  # Case 16.2: patrol costs 2 CP.


# ---------------------------------------------------------------------------
# Patrol Survival Table (Case 16.6)
# ---------------------------------------------------------------------------


class PatrolSurvival(str, Enum):
    """Case 16.6 — Outcomes of the Patrol Survival Table."""
    SAFE = "safe"
    LOSSES = "losses"
    DESTROYED = "destroyed"


@dataclass(frozen=True)
class PatrolResult:
    """Outcome of a patrol action.

    Case 16.5 — What the patrol revealed, and what it cost.
    """
    survival: PatrolSurvival
    toe_losses: int = 0
    info_revealed: list[str] | None = None
    dice_roll: int = 0


def resolve_patrol(
    patrolling_unit: Unit,
    target_hex: HexCoord,
    target_units: list[Unit],
    dice: DiceRoller,
) -> PatrolResult:
    """Resolve a patrol action.

    Cases 16.3, 16.5, 16.6 — Roll for survival, then determine what
    information is revealed.

    Args:
        patrolling_unit: The Recce unit conducting the patrol.
        target_hex: The enemy-occupied hex being patrolled.
        target_units: Enemy units in the target hex (full data; the
            function decides what to reveal per Case 3.6).
        dice: DiceRoller for survival roll.
    """
    roll = dice.roll()

    # Simplified Patrol Survival Table (Case 16.6).
    # TODO-16.6: replace with full table.
    if roll <= 2:
        survival = PatrolSurvival.DESTROYED
        toe_losses = patrolling_unit.current_toe
    elif roll <= 4:
        survival = PatrolSurvival.LOSSES
        toe_losses = 1
    else:
        survival = PatrolSurvival.SAFE
        toe_losses = 0

    # Case 16.5 / 16.7: what is revealed.
    # Simplified: reveal unit types and count (not strength or morale).
    info: list[str] = []
    if survival != PatrolSurvival.DESTROYED:
        for u in target_units:
            info.append(f"{u.unit_type.value} ({u.org_size.value})")

    return PatrolResult(
        survival=survival,
        toe_losses=toe_losses,
        info_revealed=info if info else None,
        dice_roll=roll,
    )
