"""Smoke tests for cna.engine.sequence_of_play phase machine."""

from __future__ import annotations

from collections import Counter

from cna.engine.game_state import (
    GameState,
    OperationsStage,
    Phase,
    Player,
    Side,
)
from cna.engine.sequence_of_play import (
    PLAYER_A_STAGE_PHASES,
    PLAYER_B_STAGE_PHASES,
    PREGAME_PHASES,
    PhaseDriver,
    PhaseStep,
    next_phase,
    phases_this_turn,
)


def test_phases_this_turn_total_count():
    steps = list(phases_this_turn(Side.AXIS))
    # 3 pre-game + 3 stages * (11 A + 6 B) + 1 end-of-turn
    expected = len(PREGAME_PHASES) + 3 * (len(PLAYER_A_STAGE_PHASES) + len(PLAYER_B_STAGE_PHASES)) + 1
    assert len(steps) == expected


def test_phases_this_turn_structure():
    steps = list(phases_this_turn(Side.AXIS))
    # First 3 are pre-game.
    assert [s.phase for s in steps[:3]] == list(PREGAME_PHASES)
    for s in steps[:3]:
        assert s.stage is None
        assert s.active_side == Side.AXIS

    # Last step is end-of-turn.
    assert steps[-1].phase == Phase.END_OF_TURN


def test_phases_alternate_sides_within_stage():
    steps = list(phases_this_turn(Side.AXIS))
    # Find the first operations stage's steps.
    stage_one = [s for s in steps if s.stage == OperationsStage.FIRST]
    # Player A phases come first.
    a_count = len(PLAYER_A_STAGE_PHASES)
    a_steps = stage_one[:a_count]
    b_steps = stage_one[a_count:]
    for s in a_steps:
        assert s.active_side == Side.AXIS
    for s in b_steps:
        assert s.active_side == Side.COMMONWEALTH


def test_phases_respects_player_a_by_stage_override():
    # Alternating A-holder across the three stages.
    override = (Side.AXIS, Side.COMMONWEALTH, Side.AXIS)
    steps = list(phases_this_turn(Side.AXIS, player_a_by_stage=override))
    stage_two = [s for s in steps if s.stage == OperationsStage.SECOND]
    # In stage 2, Player A is Commonwealth, so the first phases are CW.
    first_phase = stage_two[0]
    assert first_phase.active_side == Side.COMMONWEALTH


def test_next_phase_advances_pre_game():
    gs = GameState()
    gs.active_side = Side.AXIS
    gs.phase = Phase.INITIATIVE_DETERMINATION

    nxt = next_phase(gs)
    assert nxt.phase == Phase.NAVAL_CONVOY_SCHEDULE
    assert gs.phase == Phase.NAVAL_CONVOY_SCHEDULE


def test_next_phase_wraps_turn_at_end_of_turn():
    gs = GameState()
    gs.active_side = Side.AXIS
    gs.phase = Phase.END_OF_TURN
    start_turn = gs.game_turn

    nxt = next_phase(gs)
    assert gs.game_turn == start_turn + 1
    assert gs.phase == Phase.INITIATIVE_DETERMINATION
    assert gs.operations_stage == OperationsStage.FIRST
    assert nxt.phase == Phase.INITIATIVE_DETERMINATION


def test_phase_driver_runs_full_turn():
    gs = GameState()
    gs.players[Side.AXIS] = Player(side=Side.AXIS, has_initiative=True)
    gs.players[Side.COMMONWEALTH] = Player(side=Side.COMMONWEALTH)
    gs.active_side = Side.AXIS
    gs.phase = Phase.INITIATIVE_DETERMINATION

    driver = PhaseDriver(gs)
    steps = driver.run_turn()
    # Step count equals number of phases in one turn.
    expected = len(PREGAME_PHASES) + 3 * (len(PLAYER_A_STAGE_PHASES) + len(PLAYER_B_STAGE_PHASES)) + 1
    assert steps == expected
    # Should have wrapped to turn 2.
    assert gs.game_turn == 2


def test_phase_driver_calls_handlers():
    gs = GameState()
    gs.players[Side.AXIS] = Player(side=Side.AXIS, has_initiative=True)
    gs.players[Side.COMMONWEALTH] = Player(side=Side.COMMONWEALTH)
    gs.active_side = Side.AXIS
    gs.phase = Phase.INITIATIVE_DETERMINATION

    calls: list[PhaseStep] = []

    def record(state: GameState, step: PhaseStep) -> None:
        calls.append(step)

    driver = PhaseDriver(gs)
    driver.register(Phase.MOVEMENT_AND_COMBAT, record)
    driver.run_turn()

    # Movement and Combat fires 2x per stage (A then B), 3 stages => 6 times.
    assert len(calls) == 6
    counts = Counter((s.stage, s.active_side) for s in calls)
    for stage in OperationsStage:
        assert counts[(stage, Side.AXIS)] == 1
        assert counts[(stage, Side.COMMONWEALTH)] == 1
