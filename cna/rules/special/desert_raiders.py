"""Section 27.0 — Desert Raiders and Commandos.

Implements Cases 27.1-27.9: LRDG, Sonderkommando Almasy, raider
movement, spotting, raids, and the Raid Tables.

Key rules:
  - Case 27.11: LRDG (max 2 Commonwealth): CPA 50, no combat, no ZoC.
  - Case 27.12: Formed from trained Recce units.
  - Case 27.32: Movement secret from opponent.
  - Case 27.41: Spot check: roll 6 = spotted (eliminated).
  - Case 27.52: Raid types: pipeline, airfield, planes, dump, convoy.
  - Case 27.61: Raid on Rommel (Case 31 cross-ref).

Cross-references:
  - Case 16.0: Patrols reveal raiders.
  - Case 31.0: Rommel counter interactions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from cna.engine.dice import DiceRoller


LRDG_CPA = 50
MAX_LRDG_UNITS = 2
LRDG_REFORM_DELAY_TURNS = 4  # Case 27.16: reformed 4 turns after elimination.
SPOT_ROLL_THRESHOLD = 6       # Case 27.41: roll 6 = spotted.
RAID_ON_ROMMEL_CP = 10        # Case 27.61: costs 10 CP.


class RaidType(str, Enum):
    """Case 27.52 — Types of raider attacks."""
    PIPELINE = "pipeline"
    AIRFIELD = "airfield"
    PLANES = "planes"
    SUPPLY_DUMP = "dump"
    CONVOY = "convoy"
    ROMMEL = "rommel"


@dataclass(frozen=True)
class RaidResult:
    """Outcome of a desert raider raid.

    Case 27.5 — Dice determine success and damage.
    """
    raid_type: RaidType
    success: bool
    damage: int  # Quantity destroyed (hexes, planes, trucks, etc.)
    dice_roll: int


def attempt_spot(dice: DiceRoller) -> bool:
    """Roll to spot a desert raider (Case 27.41).

    Returns True if spotted (raider is eliminated).
    """
    return dice.roll() >= SPOT_ROLL_THRESHOLD


def resolve_raid(raid_type: RaidType, dice: DiceRoller) -> RaidResult:
    """Resolve a desert raid (Case 27.52).

    Simplified: roll 1d6. 1-2 = success (damage varies by type).
    TODO-27.9: implement full Raid Tables.
    """
    roll = dice.roll()
    success = roll <= 2
    damage = 0
    if success:
        if raid_type == RaidType.PIPELINE:
            damage = roll  # 1-2 hexes destroyed.
        elif raid_type == RaidType.AIRFIELD:
            damage = 1     # 1 level reduction.
        elif raid_type == RaidType.PLANES:
            damage = 1     # ~10% destroyed.
        elif raid_type == RaidType.SUPPLY_DUMP:
            damage = 1     # ~10% destroyed.
        elif raid_type == RaidType.CONVOY:
            damage = 1     # 1 truck destroyed.
        elif raid_type == RaidType.ROMMEL:
            damage = 1     # Rommel effect.

    return RaidResult(
        raid_type=raid_type,
        success=success,
        damage=damage,
        dice_roll=roll,
    )
