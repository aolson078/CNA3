"""Section 7.0 — Initiative.

Implements Cases 7.11-7.16 and the 7.2 Initiative Ratings lookup.

The Initiative-holding Player decides, *each* Operations Stage, whether
his side moves first (Player A) or last (Player B) within that Stage.
Initiative is determined *once per Game-Turn* in the Initiative
Determination Stage (Case 5.2 I) by both Players rolling 1d6 and adding
their side's Initiative Rating; highest total wins, ties reroll.

Layer 1 scope:
  - determine_initiative(state): rolls for both sides and flags the
    winner (Case 7.14).
  - declare_player_a(state, side, stage, first): records A/B for a
    specific Operations Stage (Case 5.2 III.A, Case 7.11, 7.16).
  - initiative_rating_for_side(state, side): returns the current rating
    (Case 7.13). Defaults read from state.extras["initiative_ratings"];
    scenario setup fills this, and Section 31 (Rommel) will mutate it.

Note on the 7.2 ratings chart:
  The OCR'd rulebook text for the 7.2 table is corrupt (see
  references/section_07.md). The only values we can cite with confidence
  are from the Case 7.14 example:
    - Axis, no Germans: 1
    - Commonwealth, Game-Turns 1-42: 3
  Other values are placeholders marked TODO pending manual rulebook
  transcription.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from cna.engine.errors import RuleViolationError
from cna.engine.game_state import (
    GameState,
    OperationsStage,
    Phase,
    Side,
)


# ---------------------------------------------------------------------------
# Initiative ratings (Case 7.2)
# ---------------------------------------------------------------------------


# Sentinel key in GameState.extras holding the current ratings dict.
RATINGS_EXTRAS_KEY = "initiative_ratings"

# Per-stage Player-A overrides set by the Initiative Declaration Phase.
# Keyed by (game_turn, stage) -> side that is Player A.
PLAYER_A_EXTRAS_KEY = "player_a_by_stage"


@dataclass(frozen=True)
class InitiativeRatings:
    """Current Initiative Ratings for both sides (Case 7.2).

    Scenario setup populates these; Section 31 (Rommel) may adjust the
    Axis rating when Rommel enters/leaves the map.
    """

    axis: int
    commonwealth: int

    def for_side(self, side: Side) -> int:
        """Return the rating for *side* (Case 7.13)."""
        return self.axis if side == Side.AXIS else self.commonwealth


# Default ratings known from the Case 7.14 example.
#   "Italian Player, with an Initiative Rating of '1'" (Axis, no Germans)
#   "Commonwealth Player, with an Initiative Rating of '3'" (turns 1-42)
# All other cells are TODO (OCR corrupt). Scenarios MUST set ratings
# explicitly when they require non-default values.
_DEFAULT_AXIS_RATING = 1
_DEFAULT_COMMONWEALTH_RATING = 3


# ---------------------------------------------------------------------------
# Setup / query
# ---------------------------------------------------------------------------


def set_initiative_ratings(state: GameState, ratings: InitiativeRatings) -> None:
    """Record the current Initiative Ratings on *state*.

    Case 7.13 — Rating depends on date (and for the Axis, on Rommel's
    presence). Scenario setup calls this at game start; Section 31 may
    overwrite the Axis rating during play.
    """
    state.extras[RATINGS_EXTRAS_KEY] = {
        "axis": ratings.axis,
        "commonwealth": ratings.commonwealth,
    }


def current_ratings(state: GameState) -> InitiativeRatings:
    """Return the Initiative Ratings currently recorded on *state*.

    Case 7.2 — Falls back to the documented Case 7.14 example values if
    the scenario hasn't set them (useful for tests and early development).
    """
    raw = state.extras.get(RATINGS_EXTRAS_KEY)
    if not isinstance(raw, dict):
        return InitiativeRatings(
            axis=_DEFAULT_AXIS_RATING,
            commonwealth=_DEFAULT_COMMONWEALTH_RATING,
        )
    return InitiativeRatings(
        axis=int(raw.get("axis", _DEFAULT_AXIS_RATING)),
        commonwealth=int(raw.get("commonwealth", _DEFAULT_COMMONWEALTH_RATING)),
    )


def initiative_rating_for_side(state: GameState, side: Side) -> int:
    """Return the current Initiative Rating for *side* (Case 7.13)."""
    return current_ratings(state).for_side(side)


def initiative_holder(state: GameState) -> Optional[Side]:
    """Return the side currently holding Initiative (Case 7.11), or None if unset."""
    for side, player in state.players.items():
        if player.has_initiative:
            return side
    return None


# ---------------------------------------------------------------------------
# Determination (Case 7.14)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InitiativeRollResult:
    """Outcome of a single Initiative Determination (Case 7.14)."""

    winner: Side
    axis_roll: int
    axis_rating: int
    axis_total: int
    commonwealth_roll: int
    commonwealth_rating: int
    commonwealth_total: int
    rerolls: int  # Number of ties that forced a reroll.


def determine_initiative(
    state: GameState,
    *,
    max_rerolls: int = 50,
    predetermined_winner: Optional[Side] = None,
) -> InitiativeRollResult:
    """Resolve the Initiative Determination Stage (Case 5.2 I / Case 7.14).

    Both sides roll 1d6 and add their Initiative Rating. Highest total
    wins; ties trigger a reroll (Case 7.14). Mutates *state*:
      - Sets state.players[winner].has_initiative = True.
      - Clears has_initiative on the loser.
      - Writes a structured log entry.

    Args:
        state: Game state to mutate.
        max_rerolls: Safety cap to prevent infinite loops in pathological
            dice sequences. Reaching this cap raises RuleViolationError.
        predetermined_winner: If set, forces the winner without rolling.
            Used by Case 7.15 for scenario turn-1 Initiative. A single
            roll-free record is still produced for audit.

    Returns:
        InitiativeRollResult describing the rolls and outcome.

    Raises:
        RuleViolationError (7.14): on roll/rating misconfiguration or if
            the reroll cap is exceeded.
    """
    if Side.AXIS not in state.players or Side.COMMONWEALTH not in state.players:
        raise RuleViolationError(
            "7.14", "Both players must be configured before determining initiative"
        )

    ratings = current_ratings(state)

    if predetermined_winner is not None:
        # Case 7.15 — scenario predetermines turn-1 Initiative.
        _set_initiative_flag(state, predetermined_winner)
        result = InitiativeRollResult(
            winner=predetermined_winner,
            axis_roll=0,
            axis_rating=ratings.axis,
            axis_total=0,
            commonwealth_roll=0,
            commonwealth_rating=ratings.commonwealth,
            commonwealth_total=0,
            rerolls=0,
        )
        state.log(
            f"Initiative predetermined (scenario): {predetermined_winner.value}",
            side=None,
            category="initiative",
            data={"predetermined": True, "winner": predetermined_winner.value},
        )
        return result

    rerolls = 0
    while True:
        axis_roll = state.dice.roll()
        cw_roll = state.dice.roll()
        axis_total = axis_roll + ratings.axis
        cw_total = cw_roll + ratings.commonwealth

        if axis_total > cw_total:
            winner = Side.AXIS
            break
        if cw_total > axis_total:
            winner = Side.COMMONWEALTH
            break

        rerolls += 1
        if rerolls > max_rerolls:
            raise RuleViolationError(
                "7.14",
                f"Initiative reroll cap ({max_rerolls}) exceeded — tie loop",
            )

    _set_initiative_flag(state, winner)

    result = InitiativeRollResult(
        winner=winner,
        axis_roll=axis_roll,
        axis_rating=ratings.axis,
        axis_total=axis_total,
        commonwealth_roll=cw_roll,
        commonwealth_rating=ratings.commonwealth,
        commonwealth_total=cw_total,
        rerolls=rerolls,
    )
    state.log(
        _format_roll_message(result),
        side=None,
        category="initiative",
        data={
            "winner": winner.value,
            "axis_roll": axis_roll,
            "axis_rating": ratings.axis,
            "axis_total": axis_total,
            "cw_roll": cw_roll,
            "cw_rating": ratings.commonwealth,
            "cw_total": cw_total,
            "rerolls": rerolls,
        },
    )
    return result


def _set_initiative_flag(state: GameState, winner: Side) -> None:
    for side, player in state.players.items():
        player.has_initiative = (side == winner)


def _format_roll_message(r: InitiativeRollResult) -> str:
    reroll_note = f" after {r.rerolls} tie reroll(s)" if r.rerolls else ""
    return (
        f"Initiative: {r.winner.value} wins{reroll_note} "
        f"(Axis {r.axis_roll}+{r.axis_rating}={r.axis_total} vs "
        f"CW {r.commonwealth_roll}+{r.commonwealth_rating}={r.commonwealth_total})"
    )


# ---------------------------------------------------------------------------
# Declaration (Case 7.11 / 7.16)
# ---------------------------------------------------------------------------


def declare_player_a(
    state: GameState,
    stage: OperationsStage,
    *,
    first: bool = True,
) -> Side:
    """The Initiative-holder declares whether to move first in this Stage.

    Case 5.2 III.A, Cases 7.11 and 7.16 — In each Operations Stage the
    Initiative-holder states whether he is Player A (moves first) or
    Player B (moves last).

    Args:
        state: Game state to mutate.
        stage: Which Operations Stage this declaration applies to.
        first: If True, the Initiative-holder moves first (is Player A).
            If False, the Initiative-holder cedes first move and is
            Player B.

    Returns:
        The side that will be Player A for *stage*.

    Raises:
        RuleViolationError (7.11): if no side currently holds Initiative.
    """
    holder = initiative_holder(state)
    if holder is None:
        raise RuleViolationError(
            "7.11", "Cannot declare Player A: no side currently holds Initiative"
        )

    player_a = holder if first else _enemy(holder)
    _record_player_a(state, stage, player_a)

    for side, player in state.players.items():
        player.is_player_a = (side == player_a)

    state.log(
        f"{holder.value} declares Player A = {player_a.value} for Stage {stage.name}",
        side=holder,
        category="initiative",
        data={"stage": stage.name, "player_a": player_a.value, "first": first},
    )
    return player_a


def player_a_for_stage(state: GameState, stage: OperationsStage) -> Optional[Side]:
    """Return the recorded Player A for *stage* this turn, or None if undeclared.

    Case 7.16 — Player A is the side moving first in an Operations Stage.
    """
    raw = state.extras.get(PLAYER_A_EXTRAS_KEY)
    if not isinstance(raw, dict):
        return None
    key = _player_a_key(state.game_turn, stage)
    val = raw.get(key)
    if val is None:
        return None
    try:
        return Side(val)
    except ValueError:
        return None


def _record_player_a(state: GameState, stage: OperationsStage, side: Side) -> None:
    raw = state.extras.setdefault(PLAYER_A_EXTRAS_KEY, {})
    if not isinstance(raw, dict):
        raw = {}
        state.extras[PLAYER_A_EXTRAS_KEY] = raw
    raw[_player_a_key(state.game_turn, stage)] = side.value


def _player_a_key(turn: int, stage: OperationsStage) -> str:
    return f"{turn}.{stage.value}"


def _enemy(side: Side) -> Side:
    return Side.COMMONWEALTH if side == Side.AXIS else Side.AXIS


# ---------------------------------------------------------------------------
# Phase handlers (for PhaseDriver wiring)
# ---------------------------------------------------------------------------


def handle_initiative_determination_phase(state: GameState, _step) -> None:
    """PhaseDriver handler for Phase.INITIATIVE_DETERMINATION.

    Case 5.2 I — Called once per Game-Turn. On turn 1, respects a
    scenario-predetermined winner stored in state.extras under the key
    "scenario_turn1_initiative" (Case 7.15). On subsequent turns, rolls
    normally.
    """
    if state.phase != Phase.INITIATIVE_DETERMINATION:
        return

    predetermined: Optional[Side] = None
    if state.game_turn == 1:
        raw = state.extras.get("scenario_turn1_initiative")
        if isinstance(raw, str):
            try:
                predetermined = Side(raw)
            except ValueError:
                predetermined = None

    determine_initiative(state, predetermined_winner=predetermined)


def handle_initiative_declaration_phase(state: GameState, _step) -> None:
    """PhaseDriver handler for Phase.INITIATIVE_DECLARATION.

    Case 5.2 III.A, Case 7.11 — Called at the start of each of the three
    Operations Stages. The default policy is "Initiative-holder moves
    first"; interactive UIs override this handler to ask the player.
    """
    if state.phase != Phase.INITIATIVE_DECLARATION:
        return
    declare_player_a(state, state.operations_stage, first=True)
