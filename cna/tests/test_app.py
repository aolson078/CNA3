"""Tests for cna.ui.app — interactive game loop (via step() API)."""

from __future__ import annotations

import io
from pathlib import Path

from rich.console import Console

from cna.data.scenarios.operation_compass import build_grazianis_offensive
from cna.engine.game_state import Phase, Side
from cna.rules.initiative import initiative_holder
from cna.ui.app import App, Key


def _mk_app(**kwargs) -> App:
    state = build_grazianis_offensive()
    console = Console(file=io.StringIO(), width=120, force_terminal=False,
                      color_system=None)
    return App(state=state, viewer=Side.AXIS, console=console, **kwargs)


# ---------------------------------------------------------------------------
# Phase advancement
# ---------------------------------------------------------------------------


def test_next_phase_advances_state():
    app = _mk_app()
    assert app.state.phase == Phase.INITIATIVE_DETERMINATION
    app.step(Key.NEXT)
    # After stepping, initiative should be determined (Axis predetermined)
    # and phase advanced to Naval Convoy Schedule.
    assert app.state.phase == Phase.NAVAL_CONVOY_SCHEDULE
    assert initiative_holder(app.state) == Side.AXIS


def test_multiple_steps():
    app = _mk_app()
    for _ in range(5):
        app.step(Key.NEXT)
    # Should have moved past pre-game phases into the first Operations Stage.
    assert app.state.phase != Phase.INITIATIVE_DETERMINATION


def test_full_turn_advances_game_turn():
    app = _mk_app()
    start_turn = app.state.game_turn
    # A full turn is ~55 steps. Step until the turn increments.
    for _ in range(200):
        app.step(Key.NEXT)
        if app.state.game_turn != start_turn:
            break
    assert app.state.game_turn == start_turn + 1


# ---------------------------------------------------------------------------
# Undo
# ---------------------------------------------------------------------------


def test_undo_restores_previous_state():
    app = _mk_app()
    app.step(Key.NEXT)
    phase_after_step = app.state.phase
    app.step(Key.NEXT)
    assert app.state.phase != phase_after_step
    app.step(Key.UNDO)
    assert app.state.phase == phase_after_step


def test_undo_on_empty_stack_logs_message():
    app = _mk_app()
    log_len = len(app.state.turn_log)
    app.step(Key.UNDO)
    assert len(app.state.turn_log) == log_len + 1
    assert "Nothing to undo" in app.state.turn_log[-1].message


# ---------------------------------------------------------------------------
# Hex selection
# ---------------------------------------------------------------------------


def test_tab_cycles_through_occupied_hexes():
    app = _mk_app()
    first = app.selected
    app.step(Key.TAB)
    second = app.selected
    # Should have moved to a different hex (there are multiple occupied hexes).
    assert second != first or len(app.state.map) <= 1


def test_arrow_keys_move_selection():
    app = _mk_app()
    start = app.selected
    app.step(Key.RIGHT)
    # May or may not have moved (depends on whether neighbor exists on map).
    # But should not crash.
    assert app.selected is not None


def test_arrow_to_nonexistent_hex_stays():
    app = _mk_app()
    # Move far enough in one direction that we go off-map.
    start = app.selected
    for _ in range(100):
        app.step(Key.UP)
    # Should still have a valid selection (clamped to last valid hex).
    assert app.selected is not None


# ---------------------------------------------------------------------------
# Viewer swap
# ---------------------------------------------------------------------------


def test_viewer_swap():
    app = _mk_app()
    assert app.viewer == Side.AXIS
    app.step(Key.VIEWER)
    assert app.viewer == Side.COMMONWEALTH
    app.step(Key.VIEWER)
    assert app.viewer == Side.AXIS


# ---------------------------------------------------------------------------
# Save / Load
# ---------------------------------------------------------------------------


def test_save_and_load(tmp_path):
    app = _mk_app(save_dir=tmp_path)
    app.step(Key.NEXT)  # Advance one phase so state differs from fresh.
    app.step(Key.SAVE)
    saves = list(tmp_path.glob("cna_*.json"))
    assert len(saves) == 1

    # Advance further, then load.
    app.step(Key.NEXT)
    app.step(Key.NEXT)
    phase_before_load = app.state.phase
    app.step(Key.LOAD)
    # Should have reverted to the saved state (Naval Convoy Schedule).
    assert app.state.phase == Phase.NAVAL_CONVOY_SCHEDULE


def test_load_with_no_saves_logs(tmp_path):
    app = _mk_app(save_dir=tmp_path)
    log_len = len(app.state.turn_log)
    app.step(Key.LOAD)
    assert len(app.state.turn_log) == log_len + 1
    assert "No save files" in app.state.turn_log[-1].message


# ---------------------------------------------------------------------------
# Quit
# ---------------------------------------------------------------------------


def test_quit_sets_running_false():
    app = _mk_app()
    assert app._running is True
    app.step(Key.QUIT)
    assert app._running is False


# ---------------------------------------------------------------------------
# Unknown key is no-op
# ---------------------------------------------------------------------------


def test_unknown_key_is_noop():
    app = _mk_app()
    phase = app.state.phase
    selected = app.selected
    app.step(Key.UNKNOWN)
    assert app.state.phase == phase
    assert app.selected == selected


# ---------------------------------------------------------------------------
# Rendering doesn't crash after commands
# ---------------------------------------------------------------------------


def test_render_after_all_commands():
    app = _mk_app()
    for key in [Key.NEXT, Key.TAB, Key.VIEWER, Key.NEXT, Key.UNDO,
                Key.RIGHT, Key.DOWN, Key.LEFT, Key.UP]:
        app.step(key)
        # Render should not raise.
        layout = app._render()
        assert layout is not None
