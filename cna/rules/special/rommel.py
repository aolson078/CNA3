"""Section 31.0 — Rommel.

Implements the Rommel counter rules.

Rommel is a special Axis unit representing Erwin Rommel's personal
presence on the battlefield. He has no combat value but provides
morale and CPA bonuses to units he accompanies.

Key rules:
  - Rommel counter: CPA 60 (vehicle), no combat value.
  - Can react/retreat through enemy ZoC.
  - Units in same hex during combat: morale +1.
  - Stays entire ops stage with unit(s): CPA +5 for those units.
  - Game-Turn test: roll 12 = Rommel recalled to Germany (Axis
    Initiative drops to 3). Returns next turn on roll ≤ 10.
  - Affects Axis Initiative Rating when on map (Case 7.2).

Cross-references:
  - Case 7.2: Axis Initiative Rating depends on Rommel's presence.
  - Case 17.28: Rommel +1 to adjusted morale.
  - Case 27.6: Raid on Rommel (LRDG special mission).
"""

from __future__ import annotations

from dataclasses import dataclass

from cna.engine.dice import DiceRoller
from cna.engine.game_state import GameState, Side
from cna.rules.initiative import InitiativeRatings, set_initiative_ratings


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ROMMEL_CPA = 60
ROMMEL_MORALE_BONUS = 1       # Case 17.28: +1 morale to co-located units.
ROMMEL_CPA_BONUS = 5          # +5 CPA if Rommel stays entire ops stage.
ROMMEL_RECALL_ROLL = 12       # Two-dice sum; 12 = recalled.
ROMMEL_RETURN_THRESHOLD = 10  # Roll ≤ 10 = returns next turn.

# Initiative ratings when Rommel is present vs absent (Case 7.2).
AXIS_INITIATIVE_WITH_ROMMEL = 3
AXIS_INITIATIVE_WITHOUT_ROMMEL = 2
AXIS_INITIATIVE_NO_GERMANS = 1


# ---------------------------------------------------------------------------
# Rommel status
# ---------------------------------------------------------------------------


@dataclass
class RommelStatus:
    """Tracks Rommel's current state (Case 31.0).

    Stored in GameState.extras["rommel_status"].
    """
    on_map: bool = False
    in_germany: bool = False
    arrival_turn: int = 0  # Turn Rommel first appears.

    def update_initiative(self, state: GameState) -> None:
        """Update Axis Initiative Rating based on Rommel's presence.

        Case 7.2 — Axis rating depends on whether Rommel/Germans are present.
        """
        if self.on_map:
            axis_rating = AXIS_INITIATIVE_WITH_ROMMEL
        else:
            axis_rating = AXIS_INITIATIVE_WITHOUT_ROMMEL
        # CW rating stays the same (scenario-specific).
        from cna.rules.initiative import current_ratings
        current = current_ratings(state)
        set_initiative_ratings(state, InitiativeRatings(
            axis=axis_rating, commonwealth=current.commonwealth,
        ))


def check_rommel_recall(dice: DiceRoller) -> bool:
    """Roll to see if Rommel is recalled to Germany.

    Case 31.0 — Roll 2d6 sum each Game-Turn. 12 = recalled.
    """
    return dice.roll_sum(2) >= ROMMEL_RECALL_ROLL


def check_rommel_return(dice: DiceRoller) -> bool:
    """Roll to see if recalled Rommel returns.

    Case 31.0 — Roll 2d6 sum. ≤ 10 = returns.
    """
    return dice.roll_sum(2) <= ROMMEL_RETURN_THRESHOLD
