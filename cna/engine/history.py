"""Turn history and replay system for CNA.

Provides GameHistory for capturing and restoring game state snapshots,
enabling undo, replay, and turn-by-turn review. Snapshots are deep
copies of GameState taken at meaningful points (phase transitions,
player actions, etc.).

Per CLAUDE.md: mutation is in-place within a phase, copy.deepcopy()
snapshots between phases for undo. This module extends that pattern
to support full turn history with configurable depth.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from cna.engine.game_state import GameState, OperationsStage


@dataclass
class _Snapshot:
    """Internal storage for a single history snapshot.

    Attributes:
        state: Deep copy of the game state at capture time.
        label: Human-readable label describing this snapshot.
    """

    state: GameState
    label: str


@dataclass
class GameHistory:
    """Maintains a bounded list of game state snapshots for history and replay.

    Snapshots are independent deep copies; mutating the original GameState
    after a snapshot has no effect on stored history.

    Attributes:
        max_snapshots: Maximum number of snapshots to retain. When exceeded,
            the oldest snapshot is dropped. Defaults to 100.
    """

    max_snapshots: int = 100
    _snapshots: list[_Snapshot] = field(default_factory=list)

    def add_snapshot(self, state: GameState, label: str) -> None:
        """Store a deep copy of the given game state with a descriptive label.

        If the history has reached max_snapshots, the oldest snapshot is
        dropped before the new one is added.

        Args:
            state: The game state to snapshot. A deep copy is stored so
                subsequent mutations to the original do not affect history.
            label: A human-readable label for this snapshot (e.g.,
                "Turn 2.II.MOV" or "Axis barrage on hex 1412").
        """
        snapshot = _Snapshot(state=copy.deepcopy(state), label=label)
        self._snapshots.append(snapshot)
        if len(self._snapshots) > self.max_snapshots:
            self._snapshots.pop(0)

    def get_snapshot(self, index: int) -> GameState:
        """Retrieve a deep copy of the game state at the given index.

        Args:
            index: Zero-based snapshot index. Negative indices are supported
                (e.g., -1 for the most recent snapshot).

        Returns:
            An independent deep copy of the stored GameState.

        Raises:
            IndexError: If the index is out of range.
        """
        return copy.deepcopy(self._snapshots[index].state)

    def latest(self) -> GameState:
        """Return a deep copy of the most recent snapshot.

        Returns:
            An independent deep copy of the most recent GameState.

        Raises:
            IndexError: If no snapshots have been added.
        """
        if not self._snapshots:
            raise IndexError("No snapshots in history")
        return self.get_snapshot(-1)

    def count(self) -> int:
        """Return the number of snapshots currently stored."""
        return len(self._snapshots)

    def labels(self) -> list[str]:
        """Return the labels of all stored snapshots, in chronological order."""
        return [s.label for s in self._snapshots]


def format_history_entry(index: int, label: str, state: GameState) -> str:
    """Format a single history entry as a one-line summary.

    Produces a string like:
        "[3] Turn 2.II.MOV -- 85 units, Axis 3000 ammo"

    The turn/stage/phase information is extracted from the GameState,
    and the label provides additional context.

    Args:
        index: The zero-based snapshot index.
        label: The snapshot label.
        state: The game state at the time of the snapshot.

    Returns:
        A formatted one-line summary string.
    """
    stage_numerals = {
        OperationsStage.FIRST: "I",
        OperationsStage.SECOND: "II",
        OperationsStage.THIRD: "III",
    }
    stage_str = stage_numerals.get(state.operations_stage, "?")

    # Abbreviate the phase name: MOVEMENT_AND_COMBAT -> MOV, etc.
    phase_abbrev = _abbreviate_phase(state.phase.name)

    turn_label = f"Turn {state.turn}.{stage_str}.{phase_abbrev}"
    unit_count = state.unit_count()
    axis_ammo = state.axis_ammo

    return f"[{index}] {turn_label} \u2014 {unit_count} units, Axis {axis_ammo} ammo"


def _abbreviate_phase(phase_name: str) -> str:
    """Produce a short abbreviation from a Phase enum name.

    Maps known phase names to concise abbreviations for display.
    Falls back to the first three characters of the name.

    Args:
        phase_name: The Phase enum member name (e.g., "MOVEMENT_AND_COMBAT").

    Returns:
        A short abbreviation string (e.g., "MOV").
    """
    abbreviations = {
        "INITIATIVE_DETERMINATION": "INIT",
        "NAVAL_CONVOY": "NAV",
        "INITIATIVE_DECLARATION": "DECL",
        "WEATHER_DETERMINATION": "WX",
        "ORGANIZATION": "ORG",
        "NAVAL_CONVOY_ARRIVAL": "ARR",
        "COMMONWEALTH_FLEET": "FLT",
        "RESERVE_DESIGNATION": "RSV",
        "MOVEMENT_AND_COMBAT": "MOV",
        "TRUCK_CONVOY_MOVEMENT": "TRK",
        "COMMONWEALTH_RAIL_MOVEMENT": "RAIL",
        "REPAIR": "REP",
        "PATROL": "PAT",
        "END_OF_TURN": "END",
    }
    return abbreviations.get(phase_name, phase_name[:3])
