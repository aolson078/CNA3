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
    OperationsStage,
    Phase,
    Side,
)
from cna.engine.saves import save, load
from cna.engine.sequence_of_play import PhaseDriver, PhaseStep, next_phase
from cna.rules.capability_points import reset_stage_cp, award_idle_rp
from cna.rules.initiative import (
    handle_initiative_declaration_phase,
    handle_initiative_determination_phase,
)
from cna.rules.combat.resolver import CombatReport, resolve_combat
from cna.rules.land_movement import move_unit, validate_move, MoveResult
from cna.rules.reserves import handle_reserve_release
from cna.rules.special.weather import handle_weather_phase
from cna.ui.dashboard import build_layout, render_commands
from cna.ui.views import build_view


# ---------------------------------------------------------------------------
# Key input abstraction
# ---------------------------------------------------------------------------


class Key(str, Enum):
    """Named keys the app recognizes."""
    NEXT = "n"
    MOVE = "m"
    COMBAT = "c"
    PROBE = "p"
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
    ("m", "move unit"),
    ("c", "combat"),
    ("p", "probe"),
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
            self._handle_initiative_declaration_with_stage_reset,
        )
        self._driver.register(
            Phase.WEATHER_DETERMINATION,
            handle_weather_phase,
        )
        self._driver.register(
            Phase.PATROL,
            self._handle_end_of_player_turn,
        )

    def _handle_initiative_declaration_with_stage_reset(
        self, state: GameState, step: PhaseStep,
    ) -> None:
        """Reset CP at stage start, then declare initiative.

        Case 6.16 — CP reset at the start of each Operations Stage.
        This handler fires on Initiative Declaration (first phase of
        each stage), ensuring CP are cleared before any actions.
        """
        reset_stage_cp(state)
        handle_initiative_declaration_phase(state, step)

    def _handle_end_of_player_turn(
        self, state: GameState, step: PhaseStep,
    ) -> None:
        """End-of-player-turn bookkeeping.

        Case 6.24 — Award idle RP to units that spent 0 CP.
        Case 18.2 — Auto-release reserves (simplified).
        Fires at the Patrol Phase (last phase before player switch).
        """
        awarded = award_idle_rp(state, state.operations_stage)
        if awarded:
            state.log(
                f"{len(awarded)} unit(s) earned idle reorganization",
                category="cohesion",
            )
        handle_reserve_release(state, step)

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

    def _do_move(self) -> None:
        """Move a friendly unit from the selected hex toward an adjacent hex.

        In Layer 1, this implements a simple "pick first friendly unit,
        move one hex toward the cursor direction" workflow. The full UI
        would allow selecting specific units and multi-hex paths.

        Movement is only allowed during Movement and Combat phase for the
        active side. The unit moves toward the next occupied hex in the
        tab-cycle direction (or stays if no valid move).
        """
        if self.selected is None:
            self.state.log("No hex selected for movement", side=None, category="system")
            return

        if self.state.phase != Phase.MOVEMENT_AND_COMBAT:
            self.state.log(
                "Movement only during Movement & Combat phase",
                side=None, category="system",
            )
            return

        # Find a friendly unit at the selected hex.
        active = self.state.active_side
        friendly = [u for u in self.state.units_at(self.selected) if u.side == active]
        if not friendly:
            self.state.log(
                f"No {active.value} units at selected hex",
                category="system",
            )
            return

        unit = friendly[0]

        # Find the best adjacent hex to move into (first valid neighbor).
        from cna.engine.hex_map import HexMap
        hex_map = HexMap(self.state.map)
        candidates = hex_map.neighbors_in_bounds(self.selected)
        if not candidates:
            self.state.log("No adjacent hexes to move to", category="system")
            return

        # Try each neighbor; pick the first valid move.
        for target in candidates:
            path = [self.selected, target]
            errors = validate_move(self.state, unit, path)
            if not errors:
                self._push_undo()
                try:
                    result = move_unit(self.state, unit.id, path)
                    self.selected = target
                    cp_msg = f"{result.cp_spent} CP"
                    if result.dp_earned:
                        cp_msg += f", {result.dp_earned} DP"
                    if result.stopped_by_zoc:
                        cp_msg += " (stopped by ZoC)"
                    self.state.log(
                        f"{unit.name} → {target} ({cp_msg})",
                        category="movement",
                    )
                except Exception as exc:
                    self.state.log(f"Move failed: {exc}", side=None, category="system")
                return

        self.state.log(
            f"No valid move for {unit.name} from {self.selected}",
            category="system",
        )

    def _do_combat(self, *, is_probe: bool = False) -> None:
        """Resolve combat from the selected hex against an adjacent enemy.

        Case 11.0 — Finds the first adjacent hex containing enemy units
        and runs the full combat sequence (barrage → anti-armor → close
        assault). Only available during the Movement & Combat phase.

        In the full interactive UI, the player would select which hex to
        attack, assign forces, and choose targets. Layer 1 automates
        these choices: all units at the selected hex attack the first
        adjacent enemy hex.
        """
        if self.selected is None:
            self.state.log("No hex selected for combat", side=None, category="system")
            return
        if self.state.phase != Phase.MOVEMENT_AND_COMBAT:
            self.state.log(
                "Combat only during Movement & Combat phase",
                side=None, category="system",
            )
            return

        active = self.state.active_side
        friendly = [u for u in self.state.units_at(self.selected) if u.side == active]
        if not friendly:
            self.state.log(
                f"No {active.value} units at selected hex", category="system",
            )
            return

        # Find the first adjacent hex with enemy units.
        from cna.engine.hex_map import HexMap
        hex_map = HexMap(self.state.map)
        enemy_side = self.state.enemy(active)
        target_hex = None
        for nb in hex_map.neighbors_in_bounds(self.selected):
            enemy_here = [u for u in self.state.units_at(nb) if u.side == enemy_side]
            if enemy_here:
                target_hex = nb
                break

        if target_hex is None:
            self.state.log("No adjacent enemy units to attack", category="system")
            return

        self._push_undo()
        try:
            report = resolve_combat(
                self.state, self.selected, target_hex, is_probe=is_probe,
            )
            label = "Probe" if is_probe else "Assault"
            self.state.log(
                f"{label} {self.selected}→{target_hex}: {report.summary}",
                category="combat",
                data={
                    "attacker_hex": str(self.selected),
                    "defender_hex": str(target_hex),
                    "att_toe_lost": report.attacker_toe_lost,
                    "def_toe_lost": report.defender_toe_lost,
                    "att_cp": report.attacker_cp_spent,
                    "def_cp": report.defender_cp_spent,
                    "is_probe": is_probe,
                },
            )
        except Exception as exc:
            self.state.log(f"Combat failed: {exc}", side=None, category="system")

    # -- dispatch --------------------------------------------------------

    def _handle_key(self, key: Key) -> None:
        """Dispatch a key to the appropriate command."""
        match key:
            case Key.NEXT:
                self._do_next_phase()
            case Key.MOVE:
                self._do_move()
            case Key.COMBAT:
                self._do_combat(is_probe=False)
            case Key.PROBE:
                self._do_combat(is_probe=True)
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
