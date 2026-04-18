"""Tests for cna.rules.initiative (Section 7.0)."""

from __future__ import annotations

import pytest

from cna.engine.dice import DiceRoller
from cna.engine.errors import RuleViolationError
from cna.engine.game_state import (
    GameState,
    OperationsStage,
    Phase,
    Player,
    Side,
)
from cna.engine.sequence_of_play import PhaseDriver
from cna.rules.initiative import (
    InitiativeRatings,
    current_ratings,
    declare_player_a,
    determine_initiative,
    handle_initiative_declaration_phase,
    handle_initiative_determination_phase,
    initiative_holder,
    initiative_rating_for_side,
    player_a_for_stage,
    set_initiative_ratings,
)


# ---------------------------------------------------------------------------
# Scripted dice — deterministic roll sequences for rulebook examples.
# ---------------------------------------------------------------------------


class ScriptedDice(DiceRoller):
    """DiceRoller variant that replays a fixed queue of roll() values.

    Only roll() is overridden; roll_concat / roll_sum still use the seeded
    RNG. Suffices for initiative tests which only use single rolls.
    """

    def __init__(self, rolls):
        super().__init__(seed=0)
        self._queue = list(rolls)

    def roll(self) -> int:
        val = self._queue.pop(0)
        self._rng_log("single", val)
        return val


def _mk_state(*, ratings: InitiativeRatings | None = None, dice: DiceRoller | None = None):
    gs = GameState()
    gs.players = {
        Side.AXIS: Player(side=Side.AXIS),
        Side.COMMONWEALTH: Player(side=Side.COMMONWEALTH),
    }
    if dice is not None:
        gs.dice = dice
    if ratings is not None:
        set_initiative_ratings(gs, ratings)
    return gs


# ---------------------------------------------------------------------------
# Ratings (Case 7.13, 7.2)
# ---------------------------------------------------------------------------


def test_default_ratings_match_case_714_example():
    # The Case 7.14 example documents: Axis (no Germans) = 1, CW turns 1-42 = 3.
    gs = _mk_state()
    r = current_ratings(gs)
    assert r.axis == 1
    assert r.commonwealth == 3


def test_set_initiative_ratings_round_trip():
    gs = _mk_state()
    set_initiative_ratings(gs, InitiativeRatings(axis=4, commonwealth=2))
    r = current_ratings(gs)
    assert r.axis == 4
    assert r.commonwealth == 2
    assert initiative_rating_for_side(gs, Side.AXIS) == 4
    assert initiative_rating_for_side(gs, Side.COMMONWEALTH) == 2


# ---------------------------------------------------------------------------
# Determination (Case 7.14)
# ---------------------------------------------------------------------------


def test_rulebook_example_axis_wins():
    # Verbatim Case 7.14: Axis rating 1 rolls 4 → total 5;
    # CW rating 3 rolls 1 → total 4. Axis wins.
    gs = _mk_state(
        ratings=InitiativeRatings(axis=1, commonwealth=3),
        dice=ScriptedDice([4, 1]),
    )
    result = determine_initiative(gs)
    assert result.winner == Side.AXIS
    assert result.axis_roll == 4
    assert result.axis_total == 5
    assert result.commonwealth_roll == 1
    assert result.commonwealth_total == 4
    assert result.rerolls == 0


def test_higher_total_wins_with_commonwealth_winner():
    gs = _mk_state(
        ratings=InitiativeRatings(axis=1, commonwealth=3),
        dice=ScriptedDice([1, 2]),
    )
    result = determine_initiative(gs)
    assert result.winner == Side.COMMONWEALTH
    assert gs.players[Side.COMMONWEALTH].has_initiative is True
    assert gs.players[Side.AXIS].has_initiative is False


def test_ties_force_reroll():
    # Tie on first pair (Axis 3+1=4, CW 1+3=4), Axis wins second (Axis 5+1=6, CW 2+3=5).
    gs = _mk_state(
        ratings=InitiativeRatings(axis=1, commonwealth=3),
        dice=ScriptedDice([3, 1, 5, 2]),
    )
    result = determine_initiative(gs)
    assert result.winner == Side.AXIS
    assert result.rerolls == 1
    # Final rolls recorded, not the tied ones.
    assert result.axis_roll == 5
    assert result.commonwealth_roll == 2


def test_reroll_cap_raises():
    # With rating difference of +2 favoring CW, Axis rolls 1 vs CW rolls 3 ties forever.
    # Build a script that always ties (short so we exhaust it quickly).
    gs = _mk_state(
        ratings=InitiativeRatings(axis=3, commonwealth=3),
        dice=ScriptedDice([4, 4] * 10),
    )
    with pytest.raises(RuleViolationError) as exc:
        determine_initiative(gs, max_rerolls=3)
    assert exc.value.case_number == "7.14"


def test_determine_requires_both_players_configured():
    gs = GameState()
    gs.players = {Side.AXIS: Player(side=Side.AXIS)}
    with pytest.raises(RuleViolationError) as exc:
        determine_initiative(gs)
    assert exc.value.case_number == "7.14"


def test_determination_logs_structured_entry():
    gs = _mk_state(
        ratings=InitiativeRatings(axis=1, commonwealth=3),
        dice=ScriptedDice([4, 1]),
    )
    determine_initiative(gs)
    assert len(gs.turn_log) == 1
    entry = gs.turn_log[0]
    assert entry.category == "initiative"
    assert entry.side is None  # Side-agnostic event.
    assert entry.data["winner"] == "axis"
    assert entry.data["axis_total"] == 5
    assert entry.data["cw_total"] == 4


def test_predetermined_winner_bypasses_roll():
    # Case 7.15 — scenario sets turn-1 initiative without rolling.
    gs = _mk_state(
        ratings=InitiativeRatings(axis=1, commonwealth=3),
        dice=ScriptedDice([]),  # No rolls available — forces bypass path.
    )
    result = determine_initiative(gs, predetermined_winner=Side.COMMONWEALTH)
    assert result.winner == Side.COMMONWEALTH
    assert result.rerolls == 0
    assert gs.players[Side.COMMONWEALTH].has_initiative is True
    # The log entry flags predetermined=True.
    entry = gs.turn_log[-1]
    assert entry.data.get("predetermined") is True


def test_initiative_holder_helper():
    gs = _mk_state(
        ratings=InitiativeRatings(axis=1, commonwealth=3),
        dice=ScriptedDice([4, 1]),
    )
    assert initiative_holder(gs) is None
    determine_initiative(gs)
    assert initiative_holder(gs) == Side.AXIS


# ---------------------------------------------------------------------------
# Declaration (Case 7.11, 7.16)
# ---------------------------------------------------------------------------


def test_declare_player_a_first_sets_holder_as_a():
    gs = _mk_state()
    gs.players[Side.AXIS].has_initiative = True

    a = declare_player_a(gs, OperationsStage.FIRST, first=True)
    assert a == Side.AXIS
    assert gs.players[Side.AXIS].is_player_a is True
    assert gs.players[Side.COMMONWEALTH].is_player_a is False
    assert player_a_for_stage(gs, OperationsStage.FIRST) == Side.AXIS


def test_declare_player_a_cede_makes_opponent_a():
    gs = _mk_state()
    gs.players[Side.AXIS].has_initiative = True

    a = declare_player_a(gs, OperationsStage.SECOND, first=False)
    assert a == Side.COMMONWEALTH
    assert gs.players[Side.COMMONWEALTH].is_player_a is True
    assert gs.players[Side.AXIS].is_player_a is False
    assert player_a_for_stage(gs, OperationsStage.SECOND) == Side.COMMONWEALTH


def test_declare_without_initiative_holder_raises():
    gs = _mk_state()
    # Neither side has initiative.
    with pytest.raises(RuleViolationError) as exc:
        declare_player_a(gs, OperationsStage.FIRST, first=True)
    assert exc.value.case_number == "7.11"


def test_player_a_tracked_per_stage():
    # Case 7.12 — Initiative-holder may choose differently each Stage.
    gs = _mk_state()
    gs.players[Side.AXIS].has_initiative = True

    declare_player_a(gs, OperationsStage.FIRST, first=True)
    declare_player_a(gs, OperationsStage.SECOND, first=False)
    declare_player_a(gs, OperationsStage.THIRD, first=True)

    assert player_a_for_stage(gs, OperationsStage.FIRST) == Side.AXIS
    assert player_a_for_stage(gs, OperationsStage.SECOND) == Side.COMMONWEALTH
    assert player_a_for_stage(gs, OperationsStage.THIRD) == Side.AXIS


def test_player_a_for_stage_unset_returns_none():
    gs = _mk_state()
    assert player_a_for_stage(gs, OperationsStage.FIRST) is None


# ---------------------------------------------------------------------------
# PhaseDriver integration
# ---------------------------------------------------------------------------


def test_handler_runs_when_phase_matches():
    gs = _mk_state(
        ratings=InitiativeRatings(axis=1, commonwealth=3),
        dice=ScriptedDice([4, 1]),
    )
    gs.phase = Phase.INITIATIVE_DETERMINATION

    handle_initiative_determination_phase(gs, None)
    assert gs.players[Side.AXIS].has_initiative is True


def test_handler_respects_scenario_turn1_override():
    gs = _mk_state(dice=ScriptedDice([]))
    gs.game_turn = 1
    gs.phase = Phase.INITIATIVE_DETERMINATION
    gs.extras["scenario_turn1_initiative"] = "commonwealth"

    handle_initiative_determination_phase(gs, None)
    assert initiative_holder(gs) == Side.COMMONWEALTH


def test_handler_ignores_override_after_turn1():
    gs = _mk_state(
        ratings=InitiativeRatings(axis=1, commonwealth=3),
        dice=ScriptedDice([4, 1]),
    )
    gs.game_turn = 2
    gs.phase = Phase.INITIATIVE_DETERMINATION
    gs.extras["scenario_turn1_initiative"] = "commonwealth"

    handle_initiative_determination_phase(gs, None)
    # Roll proceeds normally on turn 2: Axis 4+1=5 > CW 1+3=4.
    assert initiative_holder(gs) == Side.AXIS


def test_declaration_handler_sets_player_a():
    gs = _mk_state()
    gs.players[Side.AXIS].has_initiative = True
    gs.phase = Phase.INITIATIVE_DECLARATION
    gs.operations_stage = OperationsStage.FIRST

    handle_initiative_declaration_phase(gs, None)
    assert gs.players[Side.AXIS].is_player_a is True


def test_phase_driver_runs_initiative_handlers():
    gs = _mk_state(
        ratings=InitiativeRatings(axis=1, commonwealth=3),
        dice=ScriptedDice([4, 1] + [1] * 200),  # plenty of padding for later phases.
    )
    gs.players[Side.AXIS].has_initiative = True  # provides initial holder for phases_this_turn
    gs.active_side = Side.AXIS
    gs.phase = Phase.INITIATIVE_DETERMINATION

    driver = PhaseDriver(gs)
    driver.register(
        Phase.INITIATIVE_DETERMINATION, handle_initiative_determination_phase
    )
    driver.register(
        Phase.INITIATIVE_DECLARATION, handle_initiative_declaration_phase
    )
    driver.run_turn()

    # Initiative was recorded and all three stages' Player A declarations
    # were made (keyed against turn 1 in extras; the turn has since wrapped).
    recorded = gs.extras["player_a_by_stage"]
    assert recorded == {"1.1": "axis", "1.2": "axis", "1.3": "axis"}
    # The log captured four initiative events: one determination + three declarations.
    init_entries = [e for e in gs.turn_log if e.category == "initiative"]
    assert len(init_entries) == 4
