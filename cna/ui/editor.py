"""Section 4.0 — Scenario Editor

Interactive terminal editor for creating and modifying CNA scenarios.
Allows placing/removing units, cycling terrain and hex ownership,
and importing/exporting GameState JSON files.

Implements Case 4.0 scenario editing utilities.
"""

from __future__ import annotations

import sys
import tty
import termios
from pathlib import Path

from rich.console import Console

from cna.engine.game_state import (
    GameState,
    HexCoord,
    MapHex,
    Side,
    TerrainType,
    Unit,
    UnitType,
)
from cna.engine.saves import from_json, to_json
from cna.ui.dashboard import render_dashboard

# Ordered terrain cycle for the 't' command.
_TERRAIN_CYCLE: list[TerrainType] = [
    TerrainType.DESERT,
    TerrainType.ROUGH,
    TerrainType.MOUNTAIN,
    TerrainType.TOWN,
    TerrainType.CITY,
    TerrainType.PORT,
]

# Ordered controller cycle for the 'o' command.
_CONTROLLER_CYCLE: list[Side | None] = [
    Side.AXIS,
    Side.COMMONWEALTH,
    None,
]


class EditorKey:
    """Case 4.0 — Recognised editor keyboard inputs."""

    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    ADD_UNIT = "a"
    DELETE_UNIT = "d"
    CYCLE_TERRAIN = "t"
    CYCLE_OWNER = "o"
    EXPORT = "e"
    IMPORT = "i"
    QUIT = "q"
    UNKNOWN = "unknown"


def _read_editor_key() -> str:
    """Case 4.0 — Read a single keypress from stdin (raw mode).

    Returns one of the EditorKey constants.
    """
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            ch2 = sys.stdin.read(1)
            if ch2 == "[":
                ch3 = sys.stdin.read(1)
                return {
                    "A": EditorKey.UP,
                    "B": EditorKey.DOWN,
                    "C": EditorKey.RIGHT,
                    "D": EditorKey.LEFT,
                }.get(ch3, EditorKey.UNKNOWN)
            return EditorKey.UNKNOWN
        return {
            "a": EditorKey.ADD_UNIT,
            "d": EditorKey.DELETE_UNIT,
            "t": EditorKey.CYCLE_TERRAIN,
            "o": EditorKey.CYCLE_OWNER,
            "e": EditorKey.EXPORT,
            "i": EditorKey.IMPORT,
            "q": EditorKey.QUIT,
        }.get(ch, EditorKey.UNKNOWN)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def _prompt(console: Console, label: str) -> str:
    """Case 4.0 — Prompt the user for a text value (cooked mode)."""
    # Temporarily leave raw mode so input() works normally.
    console.print(f"[yellow]{label}[/yellow]: ", end="")
    return input()


class Editor:
    """Case 4.0 — Scenario editor for CNA.

    Provides an interactive loop over a GameState, letting the user
    add/remove units, change terrain, toggle hex ownership, and
    import/export scenario files.
    """

    def __init__(self, state: GameState | None = None) -> None:
        self.state: GameState = state or GameState()
        self.console: Console = Console()
        self.cursor: HexCoord = HexCoord(col=0, row=0)
        self.running: bool = False
        self.status_message: str = ""
        # For testing: allow injecting a key-reader callable.
        self._read_key = _read_editor_key

    # ------------------------------------------------------------------
    # Cursor movement
    # ------------------------------------------------------------------

    def move_cursor(self, direction: str) -> None:
        """Case 4.0 — Move the map cursor one hex in *direction*."""
        match direction:
            case EditorKey.UP:
                self.cursor = HexCoord(self.cursor.col, max(0, self.cursor.row - 1))
            case EditorKey.DOWN:
                self.cursor = HexCoord(self.cursor.col, self.cursor.row + 1)
            case EditorKey.LEFT:
                self.cursor = HexCoord(max(0, self.cursor.col - 1), self.cursor.row)
            case EditorKey.RIGHT:
                self.cursor = HexCoord(self.cursor.col + 1, self.cursor.row)

    # ------------------------------------------------------------------
    # Unit editing
    # ------------------------------------------------------------------

    def add_unit(
        self,
        side: Side | None = None,
        unit_type: UnitType | None = None,
        name: str | None = None,
    ) -> Unit:
        """Case 4.0 — Add a new unit at the cursor hex.

        When called interactively (all args None) prompts the user.
        When called programmatically, uses the supplied values.
        """
        if side is None:
            side_str = _prompt(self.console, "Side (axis/cw)")
            try:
                side = Side(side_str.strip().lower())
            except ValueError:
                side = Side.AXIS
                self.status_message = f"Unknown side '{side_str}', defaulting to Axis"

        if unit_type is None:
            type_str = _prompt(self.console, "Type (infantry/armor/artillery/recon/engineer/hq/supply/air/naval)")
            try:
                unit_type = UnitType(type_str.strip().lower())
            except ValueError:
                unit_type = UnitType.INFANTRY
                self.status_message = f"Unknown type '{type_str}', defaulting to infantry"

        if name is None:
            name = _prompt(self.console, "Unit name")

        unit = Unit(
            name=name.strip(),
            side=side,
            unit_type=unit_type,
            position=HexCoord(self.cursor.col, self.cursor.row),
        )
        self.state.add_unit(unit)
        self.status_message = f"Added {side.value} {unit_type.value} '{unit.name}'"
        return unit

    def delete_unit(self) -> Unit | None:
        """Case 4.0 — Delete the first unit at the cursor hex.

        Returns the removed unit, or None if there were no units.
        """
        mh = self.state.get_hex(self.cursor)
        if mh and mh.units:
            unit = mh.units[0]
            self.state.remove_unit(unit)
            self.status_message = f"Deleted '{unit.name}'"
            return unit
        self.status_message = "No unit to delete"
        return None

    # ------------------------------------------------------------------
    # Terrain / ownership
    # ------------------------------------------------------------------

    def cycle_terrain(self) -> TerrainType:
        """Case 4.0 — Cycle the terrain type at the cursor hex.

        Cycles: Desert -> Rough -> Mountain -> Town -> City -> Port -> Desert.
        Returns the new terrain type.
        """
        mh = self.state.ensure_hex(self.cursor)
        idx = _TERRAIN_CYCLE.index(mh.terrain)
        mh.terrain = _TERRAIN_CYCLE[(idx + 1) % len(_TERRAIN_CYCLE)]
        self.status_message = f"Terrain -> {mh.terrain.value}"
        return mh.terrain

    def cycle_owner(self) -> Side | None:
        """Case 4.0 — Cycle the hex controller at the cursor.

        Cycles: Axis -> CW -> None -> Axis.
        Returns the new controller value.
        """
        mh = self.state.ensure_hex(self.cursor)
        idx = _CONTROLLER_CYCLE.index(mh.controller)
        mh.controller = _CONTROLLER_CYCLE[(idx + 1) % len(_CONTROLLER_CYCLE)]
        ctrl_str = mh.controller.value if mh.controller else "none"
        self.status_message = f"Controller -> {ctrl_str}"
        return mh.controller

    # ------------------------------------------------------------------
    # Import / Export
    # ------------------------------------------------------------------

    def export_scenario(self, path: str | None = None) -> str:
        """Case 4.0 — Export the current state as a JSON file.

        If *path* is None, prompts the user.  Returns the JSON string.
        """
        if path is None:
            path = _prompt(self.console, "Export file path")
        json_str = to_json(self.state)
        p = Path(path.strip())
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json_str, encoding="utf-8")
        self.status_message = f"Exported to {p}"
        return json_str

    def import_scenario(self, path: str | None = None) -> GameState:
        """Case 4.0 — Import a GameState from a JSON file.

        Replaces the current state.  Returns the loaded GameState.
        """
        if path is None:
            path = _prompt(self.console, "Import file path")
        p = Path(path.strip())
        json_str = p.read_text(encoding="utf-8")
        self.state = from_json(json_str)
        self.status_message = f"Imported from {p}"
        return self.state

    # ------------------------------------------------------------------
    # Key dispatch and main loop
    # ------------------------------------------------------------------

    def handle_key(self, key: str) -> None:
        """Case 4.0 — Dispatch a single editor keypress."""
        match key:
            case EditorKey.UP | EditorKey.DOWN | EditorKey.LEFT | EditorKey.RIGHT:
                self.move_cursor(key)
            case EditorKey.ADD_UNIT:
                self.add_unit()
            case EditorKey.DELETE_UNIT:
                self.delete_unit()
            case EditorKey.CYCLE_TERRAIN:
                self.cycle_terrain()
            case EditorKey.CYCLE_OWNER:
                self.cycle_owner()
            case EditorKey.EXPORT:
                self.export_scenario()
            case EditorKey.IMPORT:
                self.import_scenario()
            case EditorKey.QUIT:
                self.running = False
            case _:
                pass  # Unknown keys are no-ops

    def render(self) -> None:
        """Case 4.0 — Render the editor dashboard."""
        render_dashboard(
            self.console,
            self.state,
            self.cursor,
            header="EDITOR",
        )
        if self.status_message:
            self.console.print(f"[green]> {self.status_message}[/green]")

    def run(self) -> None:
        """Case 4.0 — Main editor event loop."""
        self.running = True
        while self.running:
            self.render()
            key = self._read_key()
            self.handle_key(key)
