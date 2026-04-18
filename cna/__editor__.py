"""Entry point for the CNA scenario editor.

Usage:
    python -m cna.editor

Creates an Editor with the operational map and runs the interactive loop.

Implements Case 4.0 editor bootstrap.
"""

from cna.data.maps.map_builder import build_operational_map
from cna.ui.editor import Editor


def main() -> None:
    """Case 4.0 — Launch the scenario editor."""
    state = build_operational_map()
    editor = Editor(state=state)
    editor.run()


if __name__ == "__main__":
    main()
