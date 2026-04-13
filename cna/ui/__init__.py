"""CNA terminal UI package.

Layer 1 uses Rich for static dashboards. Layer 2 will introduce Textual
for interactive TUI (deferred; see CLAUDE.md).

Modules:
  - views: Limited-intelligence view model (Case 3.6).
  - dashboard: Rich renderers for the game overview.
"""

from cna.ui.dashboard import (
    build_layout,
    render_commands,
    render_dashboard,
    render_header,
    render_hex_panel,
    render_log,
    render_map,
    render_oob,
)
from cna.ui.views import GameView, HexView, UnitView, build_view, project_unit

__all__ = [
    "GameView",
    "HexView",
    "UnitView",
    "build_layout",
    "build_view",
    "project_unit",
    "render_commands",
    "render_dashboard",
    "render_header",
    "render_hex_panel",
    "render_log",
    "render_map",
    "render_oob",
]
