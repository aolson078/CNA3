"""Section 22.0 — Repair.

Implements Cases 22.1-22.8: field repair, facility repair, destroyed
tank repair, and the Broken Down Vehicle Repair Table.

Repair occurs in the Repair Phase (Case 5.2 III.K). Only the phasing
player may repair. Field repair uses dice rolls per vehicle type;
facility repair has better odds and handles destroyed tanks.

Key rules:
  - Case 22.11: Repair in Repair Phase only, phasing player only.
  - Case 22.13: Cannot repair in enemy ZoC, without supplies, during
    sandstorm/rainstorm, or if towed that phase.
  - Case 22.21: Field repair — trucks: roll 1-2 = repaired.
  - Case 22.26: Tank field repair costs 1 Fuel per TOE attempted.
  - Case 22.31: Facility repair — better odds at Major/Temporary facilities.
  - Case 22.35: Facility repair costs 1 Store + 1 Fuel per TOE attempted.
  - Case 22.42: Destroyed tank facility repair costs 2 Stores + 2 Fuel.
  - Case 22.61: Tank Delivery Squadron aids repair.

Cross-references:
  - Case 5.2 III.K: Repair Phase.
  - Case 21.0: Breakdown creates the need for repair.
  - Case 24.8: Construction of repair facilities.
"""

from __future__ import annotations

from dataclasses import dataclass

from cna.engine.dice import DiceRoller
from cna.engine.game_state import Unit, UnitType


# ---------------------------------------------------------------------------
# Repair eligibility (Case 22.1)
# ---------------------------------------------------------------------------


def can_field_repair(unit: Unit) -> bool:
    """Case 22.11 — Unit must be broken down to repair."""
    return unit.broken_down


# ---------------------------------------------------------------------------
# Field repair (Case 22.2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RepairResult:
    """Outcome of a repair attempt.

    Case 22.2 — Dice roll determines success.
    """
    unit_id: str
    repaired_toe: int
    dice_roll: int
    repair_type: str  # "field" or "facility"


def attempt_field_repair(
    unit: Unit,
    dice: DiceRoller,
) -> RepairResult:
    """Attempt field repair on a broken down unit (Case 22.21).

    Simplified: roll 1d6. Trucks: 1-2 = repair 1 TOE.
    Tanks/vehicles: 1 = repair 1 TOE.
    TODO-22.21: implement full Broken Down Vehicle Repair Table.
    """
    roll = dice.roll()
    repaired = 0

    if unit.unit_type == UnitType.TRUCK:
        if roll <= 2:
            repaired = 1
    else:
        if roll <= 1:
            repaired = 1

    if repaired > 0:
        unit.current_toe = min(unit.current_toe + repaired, unit.stats.max_toe_strength)
        if unit.current_toe > 0:
            unit.broken_down = False

    return RepairResult(
        unit_id=unit.id,
        repaired_toe=repaired,
        dice_roll=roll,
        repair_type="field",
    )


# ---------------------------------------------------------------------------
# Facility repair (Case 22.3)
# ---------------------------------------------------------------------------


def attempt_facility_repair(
    unit: Unit,
    dice: DiceRoller,
    *,
    is_major_facility: bool = False,
) -> RepairResult:
    """Attempt facility repair (Case 22.31).

    Better odds than field repair. Major facilities (Tripoli, Alexandria)
    give the best results.
    Simplified: roll 1d6. Major: 1-3 = repair 1 TOE. Temporary: 1-2.
    TODO-22.31: implement full facility repair table.
    """
    roll = dice.roll()
    threshold = 3 if is_major_facility else 2
    repaired = 1 if roll <= threshold else 0

    if repaired > 0:
        unit.current_toe = min(unit.current_toe + repaired, unit.stats.max_toe_strength)
        if unit.current_toe > 0:
            unit.broken_down = False

    return RepairResult(
        unit_id=unit.id,
        repaired_toe=repaired,
        dice_roll=roll,
        repair_type="facility_major" if is_major_facility else "facility_temp",
    )
