"""Interactive CNA terminal application.

Wires the Rich dashboard (cna/ui/dashboard.py) with keyboard input and
the PhaseDriver (cna/engine/sequence_of_play.py) into a live game loop.

The app uses Rich Live for continuous screen refresh and Unix tty raw-mode
for single-keypress input (no Enter required). On platforms without tty
support or when stdin is not a terminal, a fallback line-input mode is
used instead.

Usage:
    from cna.data.scenarios.operation_compass import build_grazianis_offensive
    from cna.ui.app import App

    state = build_grazianis_offensive()
    app = App(state, viewer=Side.AXIS)
    app.run()

Or from the command line:
    python -m cna.ui.app
"""

from __future__ import annotations

import copy
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from rich.console import Console
from rich.live import Live

from cna.engine.game_state import (
    GameState,
    HexCoord,
    Phase,
    Side,
)
from cna.engine.saves import save, load
from cna.engine.sequence_of_play import PhaseDriver, PhaseStep, next_phase
from cna.rules.initiative import (
    handle_initiative_declaration_phase,
    handle_initiative_determination_phase,
)
from cna.ui.dashboard import build_layout, render_commands
from cna.ui.views import build_view


# ---------------------------------------------------------------------------
# Key input abstraction
# ---------------------------------------------------------------------------


class Key(str, Enum):
    """Named keys the app recognizes."""
    NEXT = "n"
    SAVE = "s"
    LOAD = "l"
    QUIT = "q"
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    TAB = "tab"
    UNDO = "u"
    VIEWER = "v"
    HELP = "?"
    UNKNOWN = ""


def _read_key_raw() -> str:
    """Read a single keypress from stdin in raw mode (Unix).

    Returns the key character, or an escape-sequence tag for arrow keys.
    """
    import tty
    import termios
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            seq = sys.stdin.read(2)
            arrow_map = {"[A": "up", "[B": "down", "[C": "right", "[D": "left"}
            return arrow_map.get(seq, "")
        if ch == "\t":
            return "tab"
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _read_key_line() -> str:
    """Fallback: read a line from stdin (for non-tty / piped input)."""
    try:
        line = input("> ").strip().lower()
    except EOFError:
        return "q"
    return line or ""


def _parse_key(raw: str) -> Key:
    """Map a raw key string to a Key enum."""
    try:
        return Key(raw)
    except ValueError:
        return Key.UNKNOWN


def _can_use_raw_input() -> bool:
    """True if we can use tty raw-mode input."""
    if not sys.stdin.isatty():
        return False
    try:
        import tty  # noqa: F401
        import termios  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Command hint sets
# ---------------------------------------------------------------------------


_HINTS_NORMAL: list[tuple[str, str]] = [
    ("n", "next phase"),
    ("arrows", "select hex"),
    ("tab", "cycle hexes"),
    ("v", "swap viewer"),
    ("u", "undo"),
    ("s", "save"),
    ("l", "load"),
    ("q", "quit"),
]


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


@dataclass
class App:
    """Interactive CNA game application.

    Drives a GameState through the sequence of play with keyboard input,
    rendering the dashboard after each action.

    Attributes:
        state: The game state being played.
        viewer: Which side's perspective the dashboard shows.
        selected: Currently selected hex coordinate (for hex detail panel).
        console: Rich Console for output.
        save_dir: Directory for save files.
        _driver: PhaseDriver with rule handlers registered.
        _undo_stack: Snapshots for undo (deepcopy before each phase advance).
        _hex_list: Sorted list of hex coords for tab-cycling.
        _hex_index: Current index into _hex_list.
        _running: False to exit the main loop.
    """

    state: GameState
    viewer: Side = Side.AXIS
    selected: Optional[HexCoord] = None
    console: Console = field(default_factory=lambda: Console())
    save_dir: Path = field(default_factory=lambda: Path("saves"))

    _driver: PhaseDriver = field(init=False)
    _undo_stack: list[GameState] = field(default_factory=list, init=False)
    _hex_list: list[HexCoord] = field(default_factory=list, init=False)
    _hex_index: int = field(default=0, init=False)
    _running: bool = field(default=True, init=False)
    _read_key: Callable[[], str] = field(init=False)

    MAX_UNDO = 20

    def __post_init__(self):
        self._driver = PhaseDriver(self.state)
        self._register_handlers()
        self._rebuild_hex_list()
        if self._hex_list and self.selected is None:
            self.selected = self._hex_list[0]
        self._read_key = _read_key_raw if _can_use_raw_input() else _read_key_line

    def _register_handlers(self):
        """Register rule-module phase handlers with the driver."""
        self._driver.register(
            Phase.INITIATIVE_DETERMINATION,
            handle_initiative_determination_phase,
        )
        self._driver.register(
            Phase.INITIATIVE_DECLARATION,
            handle_initiative_declaration_phase,
        )

    def _rebuild_hex_list(self):
        """Build a sorted list of hex coords for tab-cycling."""
        self._hex_list = sorted(self.state.map.keys(), key=lambda c: (c.r, c.q))
        self._hex_index = 0
        if self.selected in self._hex_list:
            self._hex_index = self._hex_list.index(self.selected)

    # -- rendering -------------------------------------------------------

    def _render(self) -> None:
        """Build and return the dashboard layout for the current state."""
        view = build_view(self.state, self.viewer)
        return build_layout(view, selected=self.selected)

    # -- commands --------------------------------------------------------

    def _do_next_phase(self) -> None:
        """Advance to the next phase via the PhaseDriver."""
        self._push_undo()
        self._driver.step()

    def _do_undo(self) -> None:
        """Pop the last undo snapshot."""
        if not self._undo_stack:
            self.state.log("Nothing to undo", side=None, category="system")
            return
        self.state = self._undo_stack.pop()
        self._driver = PhaseDriver(self.state)
        self._register_handlers()
        self._rebuild_hex_list()

    def _push_undo(self) -> None:
        snapshot = copy.deepcopy(self.state)
        self._undo_stack.append(snapshot)
        if len(self._undo_stack) > self.MAX_UNDO:
            self._undo_stack.pop(0)

    def _do_save(self) -> None:
        self.save_dir.mkdir(parents=True, exist_ok=True)
        filename = f"cna_t{self.state.game_turn}_{self.state.scenario_id}.json"
        path = self.save_dir / filename
        try:
            save(self.state, path)
            self.state.log(
                f"Game saved to {path}",
                side=None,
                category="system",
            )
        except Exception as exc:
            self.state.log(
                f"Save failed: {exc}",
                side=None,
                category="system",
            )

    def _do_load(self) -> None:
        self.save_dir.mkdir(parents=True, exist_ok=True)
        saves = sorted(self.save_dir.glob("cna_*.json"), reverse=True)
        if not saves:
            self.state.log("No save files found", side=None, category="system")
            return
        path = saves[0]
        try:
            self.state = load(path)
            self._driver = PhaseDriver(self.state)
            self._register_handlers()
            self._rebuild_hex_list()
            self._undo_stack.clear()
            self.state.log(
                f"Game loaded from {path.name}",
                side=None,
                category="system",
            )
        except Exception as exc:
            self.state.log(
                f"Load failed: {exc}",
                side=None,
                category="system",
            )

    def _do_select_direction(self, key: Key) -> None:
        """Move the hex selection cursor in a direction."""
        if self.selected is None:
            if self._hex_list:
                self.selected = self._hex_list[0]
            return
        dq, dr = {
            Key.UP: (0, -1),
            Key.DOWN: (0, 1),
            Key.LEFT: (-1, 0),
            Key.RIGHT: (1, 0),
        }.get(key, (0, 0))
        candidate = HexCoord(self.selected.q + dq, self.selected.r + dr)
        if candidate in self.state.map:
            self.selected = candidate
            if candidate in self._hex_list:
                self._hex_index = self._hex_list.index(candidate)

    def _do_tab_cycle(self) -> None:
        """Cycle hex selection to the next hex with units."""
        if not self._hex_list:
            return
        occupied = [c for c in self._hex_list if self.state.units_at(c)]
        if not occupied:
            occupied = self._hex_list
        if self.selected in occupied:
            idx = occupied.index(self.selected)
            self.selected = occupied[(idx + 1) % len(occupied)]
        else:
            self.selected = occupied[0]

    def _do_swap_viewer(self) -> None:
        """Toggle the dashboard between Axis and Commonwealth POV."""
        self.viewer = self.state.enemy(self.viewer)

    # -- dispatch --------------------------------------------------------

    def _handle_key(self, key: Key) -> None:
        """Dispatch a key to the appropriate command."""
        match key:
            case Key.NEXT:
                self._do_next_phase()
            case Key.SAVE:
                self._do_save()
            case Key.LOAD:
                self._do_load()
            case Key.UNDO:
                self._do_undo()
            case Key.UP | Key.DOWN | Key.LEFT | Key.RIGHT:
                self._do_select_direction(key)
            case Key.TAB:
                self._do_tab_cycle()
            case Key.VIEWER:
                self._do_swap_viewer()
            case Key.QUIT:
                self._running = False
            case _:
                pass

    # -- main loop -------------------------------------------------------

    def run(self) -> None:
        """Run the interactive game loop.

        Uses Rich Live for continuous screen refresh. Each keypress
        triggers a command, re-renders the dashboard, and updates the
        Live display.
        """
        self._running = True
        with Live(
            self._render(),
            console=self.console,
            screen=True,
            refresh_per_second=4,
        ) as live:
            while self._running:
                try:
                    raw = self._read_key()
                except KeyboardInterrupt:
                    self._running = False
                    break
                key = _parse_key(raw)
                self._handle_key(key)
                if self._running:
                    live.update(self._render())

    def step(self, key: Key) -> None:
        """Process a single key without running the live loop.

        Useful for testing and scripted replay.
        """
        self._handle_key(key)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main():
    """Launch CNA with the Graziani's Offensive scenario."""
    from cna.data.scenarios.operation_compass import build_grazianis_offensive

    state = build_grazianis_offensive()
    app = App(state=state, viewer=Side.AXIS)

    console = Console()
    console.print("[bold green]The Campaign for North Africa[/bold green]")
    console.print(f"Scenario: {state.extras.get('scenario_name', state.scenario_id)}")
    console.print("Press any key to start...")

    if _can_use_raw_input():
        _read_key_raw()
    else:
        input()

    app.run()


if __name__ == "__main__":
    main()
