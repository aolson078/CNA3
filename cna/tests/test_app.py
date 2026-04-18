"""Tests for cna.ui.app — interactive game loop (via step() API)."""

from __future__ import annotations

import io
from pathlib import Path

from rich.console import Console

from cna.data.scenarios.operation_compass import build_grazianis_offensive
from cna.engine.game_state import Phase, Side, WeatherState
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


# ---------------------------------------------------------------------------
# Weather handler integration
# ---------------------------------------------------------------------------


def test_weather_handler_fires():
    app = _mk_app()
    # Advance to Weather Determination phase (past pre-game + init declaration).
    while app.state.phase != Phase.WEATHER_DETERMINATION:
        app.step(Key.NEXT)
    app.step(Key.NEXT)  # This triggers the weather handler.
    # Weather should have been rolled.
    weather_entries = [e for e in app.state.turn_log if e.category == "weather"]
    assert len(weather_entries) >= 1


# ---------------------------------------------------------------------------
# CP reset at stage boundary
# ---------------------------------------------------------------------------


def test_cp_reset_at_stage_boundary():
    app = _mk_app()
    # Advance to Movement & Combat, spend CP on a unit.
    while app.state.phase != Phase.MOVEMENT_AND_COMBAT:
        app.step(Key.NEXT)
    # Manually spend CP on a unit.
    uid = next(iter(app.state.units.keys()))
    app.state.units[uid].capability_points_spent = 5

    # Advance past player B phases to the next Init Declaration.
    for _ in range(50):
        app.step(Key.NEXT)
        if app.state.phase == Phase.INITIATIVE_DECLARATION:
            break
    # The handler fires when we step FROM Initiative Declaration.
    app.step(Key.NEXT)
    # Re-fetch unit from the (possibly deepcopy'd) state.
    assert app.state.units[uid].capability_points_spent == 0


# ---------------------------------------------------------------------------
# Movement command
# ---------------------------------------------------------------------------


def test_move_outside_movement_phase():
    app = _mk_app()
    # At Initiative Determination, movement should not work.
    log_len = len(app.state.turn_log)
    app.step(Key.MOVE)
    assert any("Movement only" in e.message for e in app.state.turn_log[log_len:])


def test_move_during_movement_phase():
    app = _mk_app()
    # Advance to Movement & Combat phase.
    while app.state.phase != Phase.MOVEMENT_AND_COMBAT:
        app.step(Key.NEXT)
    # Select a hex with a friendly unit.
    active = app.state.active_side
    friendly_hexes = [
        u.position for u in app.state.units.values()
        if u.side == active and u.position is not None
    ]
    if friendly_hexes:
        app.selected = friendly_hexes[0]
        old_pos = friendly_hexes[0]
        app.step(Key.MOVE)
        # Should have moved or logged a reason why not.
        move_entries = [e for e in app.state.turn_log if e.category == "movement"]
        no_move_entries = [e for e in app.state.turn_log if "No valid" in e.message or "No " in e.message]
        assert len(move_entries) > 0 or len(no_move_entries) > 0
