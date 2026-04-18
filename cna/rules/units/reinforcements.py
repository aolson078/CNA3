"""Section 20.0 — Reinforcements, Replacements, and Withdrawals.

Implements Cases 20.1-20.9: reinforcement arrival, replacement points,
replacement conversion, replacement usage, upgrading, Axis planned
replacement, Commonwealth production, and mandatory withdrawals.

Key rules:
  - Case 20.11: Reinforcements arrive at Naval Convoy Arrival Phase.
  - Case 20.14: CW arrive at Cairo (some at Alexandria); Axis at Tripoli.
  - Case 20.21: Replacement Points arrive via convoy; Axis plans 2 turns
    ahead, CW 1 turn.
  - Case 20.41: Trained replacements in same hex as receiving unit.
  - Case 20.43: Training time: Gun=1 ops stage, Infantry=3, Tank=6.
  - Case 20.82: Mandatory CW withdrawals require 75% TOE at Cairo/Alex.

Cross-references:
  - Case 5.2 III.D: Naval Convoy Arrival Phase.
  - Case 17.3: Training affects replacement readiness.
  - Case 19.68: Absorbing replacements costs CP.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from cna.engine.game_state import (
    GameState,
    HexCoord,
    Side,
    Unit,
)


# ---------------------------------------------------------------------------
# Replacement training time (Case 20.43)
# ---------------------------------------------------------------------------


class ReplacementType(str, Enum):
    """Case 20.43 — Type determines training time."""
    GUN = "gun"           # 1 ops stage
    INFANTRY = "infantry"  # 3 ops stages
    TANK = "tank"          # 6 ops stages
    RECCE = "recce"        # 6 ops stages


TRAINING_OPS_STAGES: dict[ReplacementType, int] = {
    ReplacementType.GUN: 1,
    ReplacementType.INFANTRY: 3,
    ReplacementType.TANK: 6,
    ReplacementType.RECCE: 6,
}


# ---------------------------------------------------------------------------
# Reinforcement arrival (Case 20.1)
# ---------------------------------------------------------------------------

# Default arrival hexes by side (Case 20.14).
# These are scenario-dependent; the scenario setup overrides them.
DEFAULT_ARRIVAL_HEXES: dict[Side, str] = {
    Side.AXIS: "Tripoli",
    Side.COMMONWEALTH: "Cairo",
}


@dataclass
class ScheduledReinforcement:
    """A reinforcement scheduled to arrive at a specific turn.

    Case 20.11 — Placed during Naval Convoy Arrival Phase.
    """
    unit_id: str
    arrival_turn: int
    arrival_hex_name: str
    side: Side


def get_due_reinforcements(
    state: GameState,
) -> list[ScheduledReinforcement]:
    """Return reinforcements scheduled for the current Game-Turn.

    Case 20.11 — Reads from state.extras["reinforcement_schedule"].
    """
    schedule = state.extras.get("reinforcement_schedule", [])
    if not isinstance(schedule, list):
        return []
    due: list[ScheduledReinforcement] = []
    for entry in schedule:
        if isinstance(entry, dict) and entry.get("arrival_turn") == state.game_turn:
            due.append(ScheduledReinforcement(
                unit_id=entry["unit_id"],
                arrival_turn=entry["arrival_turn"],
                arrival_hex_name=entry.get("hex", ""),
                side=Side(entry["side"]),
            ))
    return due


# ---------------------------------------------------------------------------
# Withdrawal (Case 20.8)
# ---------------------------------------------------------------------------

WITHDRAWAL_TOE_THRESHOLD = 0.75  # Case 20.82: 75% TOE required.


def can_withdraw(unit: Unit) -> bool:
    """Whether *unit* meets the 75% TOE threshold for withdrawal (Case 20.82)."""
    if unit.stats.max_toe_strength <= 0:
        return False
    return unit.current_toe / unit.stats.max_toe_strength >= WITHDRAWAL_TOE_THRESHOLD
