"""Section 17.0 — Morale.

Implements Cases 17.1-17.6: Basic Morale Ratings, adjustments from
Cohesion and combat, Training, and the Morale Modification Table.

Morale affects Close Assault via column shifts on the CRT. A unit's
current morale can diverge from its Basic Morale Rating through combat
success/failure and training.

Key rules:
  - Case 17.1: Each combat unit has a Basic Morale Rating (-3 to +3).
  - Case 17.2: Adjustments from Cohesion Level (Case 6.25).
    Positive cohesion may increase effective morale; negative decreases.
  - Case 17.3: Training — CW units may train to reach Basic Morale.
    Training takes 1 full Game-Turn per +1 morale increase.
    Training unit must remain stationary (0 CP spent).
  - Case 17.4: Morale Modification Table — dice-based adjustments
    after combat. Winners gain morale; losers may lose it.
  - Case 17.5: Voluntary Surrender — units with morale -3 or worse
    may surrender under certain conditions.
  - Case 17.6: Training Chart — schedule for CW unit training.

Cross-references:
  - Case 6.25: Cohesion affects Morale in combat.
  - Case 15.6: Morale modifies Close Assault differential.
  - Case 3.5: Basic Morale Rating definition.
"""

from __future__ import annotations

from dataclasses import dataclass

from cna.engine.dice import DiceRoller
from cna.engine.game_state import Unit
from cna.rules.capability_points import cohesion_value


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MORALE_MAX = 3       # Case 17.1 — highest Basic Morale Rating.
MORALE_MIN = -3      # Case 17.1 — lowest Basic Morale Rating.
SURRENDER_THRESHOLD = -3  # Case 17.5 — voluntary surrender threshold.

# Cohesion-to-morale conversion bands (Case 17.2).
# Every 3 points of cohesion (positive or negative) shifts morale by 1.
COHESION_MORALE_DIVISOR = 3


# ---------------------------------------------------------------------------
# Effective morale (Case 17.2)
# ---------------------------------------------------------------------------


def effective_morale(unit: Unit) -> int:
    """Current effective morale for *unit* including Cohesion effects.

    Case 17.2, 6.25 — Basic Morale adjusted by Cohesion Level.
    Positive cohesion may increase morale (for combat resolution);
    negative cohesion decreases it.
    """
    coh = cohesion_value(unit)
    morale_adj = coh // COHESION_MORALE_DIVISOR
    return unit.current_morale + morale_adj


def morale_differential(attacker: list[Unit], defender: list[Unit]) -> int:
    """Net morale differential for Close Assault column shift.

    Case 15.6 — Attacker adjusted morale minus Defender adjusted morale.
    Uses the average effective morale of each side.
    """
    if not attacker or not defender:
        return 0
    att_avg = sum(effective_morale(u) for u in attacker) / len(attacker)
    def_avg = sum(effective_morale(u) for u in defender) / len(defender)
    return round(att_avg - def_avg)


# ---------------------------------------------------------------------------
# Morale changes (Case 17.4)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MoraleChangeResult:
    """Outcome of a morale modification check.

    Case 17.4 — After combat, winners may gain morale, losers may lose.
    """
    unit_id: str
    old_morale: int
    new_morale: int
    dice_roll: int


def check_morale_after_combat(
    unit: Unit,
    *,
    won_assault: bool,
    dice: DiceRoller,
) -> MoraleChangeResult:
    """Check for morale change after combat (Case 17.4).

    Simplified Morale Modification Table:
    - Winner: roll 5-6 → +1 morale (capped at Basic +3).
    - Loser: roll 1-2 → -1 morale (no floor).
    TODO-17.4: replace with full Morale Modification Table.
    """
    old = unit.current_morale
    roll = dice.roll()

    if won_assault and roll >= 5:
        unit.current_morale = min(old + 1, unit.stats.basic_morale + 3)
    elif not won_assault and roll <= 2:
        unit.current_morale = old - 1

    return MoraleChangeResult(
        unit_id=unit.id,
        old_morale=old,
        new_morale=unit.current_morale,
        dice_roll=roll,
    )


# ---------------------------------------------------------------------------
# Voluntary Surrender (Case 17.5)
# ---------------------------------------------------------------------------


def can_voluntarily_surrender(unit: Unit) -> bool:
    """Case 17.5 — Units with effective morale -3 or worse may surrender."""
    return effective_morale(unit) <= SURRENDER_THRESHOLD


# ---------------------------------------------------------------------------
# Training (Case 17.3)
# ---------------------------------------------------------------------------


def can_train(unit: Unit) -> bool:
    """Case 17.3 — Unit can train if current morale < Basic Morale.

    Training is available primarily to Commonwealth units arriving with
    morale below their Basic rating.
    """
    return unit.current_morale < unit.stats.basic_morale


def apply_training_completion(unit: Unit) -> int:
    """Apply one level of training completion (Case 17.3).

    Increases current morale by 1, up to Basic Morale Rating.
    Returns the new morale value.
    """
    if unit.current_morale < unit.stats.basic_morale:
        unit.current_morale += 1
    return unit.current_morale
