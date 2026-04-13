"""Section 5.0 — Sequence of Play (Land Game) phase machine.

Implements Cases 5.1-5.2: the Game-Turn is divided into three Operations
Stages, each stepping through a fixed phase list. The phase list differs
between Player A and Player B (Player B repeats Phases F-L after Player A
finishes; see Case 5.2).

This module is intentionally *only* a phase driver. Rule enforcement for
what happens *within* a phase lives in the corresponding cna/rules/
module; the driver merely advances the state machine and records
transitions. Phases that a module has not yet been written for are
"no-op" transitions (they just advance the pointer).

Public API:
  - next_phase(state): advance state.phase / stage / turn in-place.
  - phases_this_turn(): yields the full ordered list of (stage, phase,
    active_side) triples for one Game-Turn.
  - PhaseDriver: convenience wrapper that can drive a full turn and call
    hook callbacks per phase (useful for UI and tests).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterator

from cna.engine.errors import RuleViolationError
from cna.engine.game_state import (
    GameState,
    OperationsStage,
    Phase,
    Side,
)


# ---------------------------------------------------------------------------
# Phase tables
# ---------------------------------------------------------------------------


# Stage I-II: once per Game-Turn, before the three Operations Stages.
# Case 5.2 I, II.
PREGAME_PHASES: tuple[Phase, ...] = (
    Phase.INITIATIVE_DETERMINATION,
    Phase.NAVAL_CONVOY_SCHEDULE,
    Phase.TACTICAL_SHIPPING,
)


# Within each Operations Stage, Player A executes Phases A-L in order,
# then Player B repeats Phases F-L (per Case 5.2 III, the note after L).
# Phases A-E are executed once per stage (shared/joint phases that only
# run for the Initiative-holder / by both players by arrangement).
#
# Case 5.2 III — Phase letters map as:
#   A  Initiative Declaration
#   B  Weather Determination
#   C  Organization
#   D  Naval Convoy Arrival
#   E  Commonwealth Fleet
#   F  Reserve Designation
#   G  Movement and Combat
#   H  Truck Convoy Movement
#   J  Commonwealth Rail Movement
#   K  Repair
#   L  Patrol
PLAYER_A_STAGE_PHASES: tuple[Phase, ...] = (
    Phase.INITIATIVE_DECLARATION,
    Phase.WEATHER_DETERMINATION,
    Phase.ORGANIZATION,
    Phase.NAVAL_CONVOY_ARRIVAL,
    Phase.COMMONWEALTH_FLEET,
    Phase.RESERVE_DESIGNATION,
    Phase.MOVEMENT_AND_COMBAT,
    Phase.TRUCK_CONVOY,
    Phase.RAIL_MOVEMENT,
    Phase.REPAIR,
    Phase.PATROL,
)

# Player B repeats only F-L.
PLAYER_B_STAGE_PHASES: tuple[Phase, ...] = (
    Phase.RESERVE_DESIGNATION,
    Phase.MOVEMENT_AND_COMBAT,
    Phase.TRUCK_CONVOY,
    Phase.RAIL_MOVEMENT,
    Phase.REPAIR,
    Phase.PATROL,
)

OPERATIONS_STAGES: tuple[OperationsStage, ...] = (
    OperationsStage.FIRST,
    OperationsStage.SECOND,
    OperationsStage.THIRD,
)


# ---------------------------------------------------------------------------
# Turn plan
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PhaseStep:
    """One step in the sequence of play.

    Attributes:
        stage: Which Operations Stage (or None for pre-game stage-level
            phases).
        phase: The Phase enum value.
        active_side: Which side is "active" for this phase (Player A vs
            Player B). For pre-game / shared phases, this is the
            Initiative-holder's side by convention.
    """

    stage: OperationsStage | None
    phase: Phase
    active_side: Side


def phases_this_turn(
    initiative_side: Side,
    player_a_by_stage: tuple[Side, Side, Side] | None = None,
) -> Iterator[PhaseStep]:
    """Yield every PhaseStep for one Game-Turn, in canonical order.

    Args:
        initiative_side: The side holding the Initiative this turn.
            Used for all pre-game / stage-level phases where there's no
            per-stage A/B split.
        player_a_by_stage: Optional override for which side is "A" in
            each of the three Operations Stages. If None, defaults to
            the initiative_side for all three (most common case before
            the Initiative-holder declares A/B in Case 5.2 III.A).

    Case 5.2 — Generates pre-game phases once, then the three Operations
    Stages, each with Player-A phases followed by Player-B phases.
    """
    if player_a_by_stage is None:
        player_a_by_stage = (initiative_side, initiative_side, initiative_side)
    if len(player_a_by_stage) != 3:
        raise ValueError("player_a_by_stage must be length 3")

    # Pre-game: Stage I-II.
    for phase in PREGAME_PHASES:
        yield PhaseStep(stage=None, phase=phase, active_side=initiative_side)

    # Three Operations Stages.
    for stage, player_a in zip(OPERATIONS_STAGES, player_a_by_stage):
        player_b = _enemy(player_a)
        for phase in PLAYER_A_STAGE_PHASES:
            yield PhaseStep(stage=stage, phase=phase, active_side=player_a)
        for phase in PLAYER_B_STAGE_PHASES:
            yield PhaseStep(stage=stage, phase=phase, active_side=player_b)

    # End of turn marker.
    yield PhaseStep(stage=None, phase=Phase.END_OF_TURN, active_side=initiative_side)


def _enemy(side: Side) -> Side:
    return Side.COMMONWEALTH if side == Side.AXIS else Side.AXIS


# ---------------------------------------------------------------------------
# In-place advancement
# ---------------------------------------------------------------------------


def next_phase(state: GameState) -> PhaseStep:
    """Advance *state* to the next phase, mutating in place.

    Case 5.2 — Moves the state pointer one step through the sequence of
    play. On END_OF_TURN, this increments state.game_turn, resets to
    Stage I Initiative Determination, and returns that step.

    Returns:
        The PhaseStep that *state* is now in after advancement.

    Raises:
        RuleViolationError: if state.phase is not a recognized value.
    """
    initiative_side = _current_initiative_side(state)
    steps = list(phases_this_turn(initiative_side))

    # Find current step and go to the next one.
    current_idx = _find_step_index(state, steps)
    if current_idx is None:
        raise RuleViolationError(
            "5.2", f"Current phase {state.phase} is not valid in stage {state.operations_stage}"
        )

    if current_idx + 1 >= len(steps):
        # Wrap to next Game-Turn.
        state.game_turn += 1
        state.operations_stage = OperationsStage.FIRST
        state.phase = Phase.INITIATIVE_DETERMINATION
        state.active_side = initiative_side
        return PhaseStep(None, Phase.INITIATIVE_DETERMINATION, initiative_side)

    nxt = steps[current_idx + 1]
    state.phase = nxt.phase
    if nxt.stage is not None:
        state.operations_stage = nxt.stage
    state.active_side = nxt.active_side
    return nxt


def _current_initiative_side(state: GameState) -> Side:
    """Return whichever side currently holds the Initiative.

    Defaults to state.active_side if no player flagged (game just started).
    """
    for side, player in state.players.items():
        if player.has_initiative:
            return side
    return state.active_side


def _find_step_index(state: GameState, steps: list[PhaseStep]) -> int | None:
    """Locate the index in *steps* that matches *state*'s current phase."""
    for i, step in enumerate(steps):
        if step.phase != state.phase:
            continue
        # Pre-game / end-of-turn steps have stage=None: match on phase alone.
        if step.stage is None:
            return i
        if step.stage == state.operations_stage and step.active_side == state.active_side:
            return i
    # Fallback: match on phase alone (useful when caller hasn't synced side).
    for i, step in enumerate(steps):
        if step.phase == state.phase and step.stage == state.operations_stage:
            return i
    return None


# ---------------------------------------------------------------------------
# PhaseDriver
# ---------------------------------------------------------------------------


PhaseHandler = Callable[[GameState, PhaseStep], None]


@dataclass
class PhaseDriver:
    """Drives a GameState through phases, dispatching to per-phase handlers.

    This is a thin convenience wrapper around next_phase() that lets rule
    modules register handlers for specific phases. When advancing, the
    driver calls the registered handler (if any) *before* advancing the
    phase pointer.

    Usage:
        driver = PhaseDriver(state)
        driver.register(Phase.WEATHER_DETERMINATION, roll_weather)
        driver.run_turn()
    """

    state: GameState
    handlers: dict[Phase, PhaseHandler] = field(default_factory=dict)

    def register(self, phase: Phase, handler: PhaseHandler) -> None:
        """Register a handler callback for a given phase."""
        self.handlers[phase] = handler

    def step(self) -> PhaseStep:
        """Run the handler for the current phase, then advance.

        Returns the PhaseStep that state is in *after* advancement.
        """
        current_step = PhaseStep(
            stage=self.state.operations_stage,
            phase=self.state.phase,
            active_side=self.state.active_side,
        )
        handler = self.handlers.get(self.state.phase)
        if handler is not None:
            handler(self.state, current_step)
        return next_phase(self.state)

    def run_turn(self, max_steps: int = 500) -> int:
        """Step until END_OF_TURN wraps to a new Game-Turn.

        Returns:
            Number of steps executed.

        Raises:
            RuntimeError: if max_steps is exceeded (guard against infinite
                loops caused by a bad handler mutating state.phase).
        """
        start_turn = self.state.game_turn
        count = 0
        while count < max_steps:
            self.step()
            count += 1
            if self.state.game_turn != start_turn:
                return count
        raise RuntimeError(f"Turn did not complete within {max_steps} steps")
