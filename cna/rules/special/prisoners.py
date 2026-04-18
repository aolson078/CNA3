"""Section 28.0 — Prisoners.

Implements Cases 28.1-28.3: prisoner points, guards, captured
equipment, and prisoner movement.

Key rules:
  - Case 28.11: 1 Infantry TOE = 1 Prisoner Point. Tanks/guns create
    nothing.
  - Case 28.12: Prisoners move 3 hexes free on capture.
  - Case 28.13: Prisoner CPA = 8 (movement only); cannot exceed.
  - Case 28.14: Max 40 prisoner points per hex.
  - Case 28.15: 1 Store per 5 prisoner points per ops stage.
  - Case 28.17: 1 guard per prisoner point.
  - Case 28.23: Unguarded prisoners escape.

Cross-references:
  - Case 15.0: Close Assault creates prisoners (Captured result).
  - Case 20.0: Escaped prisoners may become replacements.
"""

from __future__ import annotations

from dataclasses import dataclass


PRISONER_CPA = 8            # Case 28.13
MAX_PRISONERS_PER_HEX = 40  # Case 28.14
STORES_PER_5_PRISONERS = 1  # Case 28.15
GUARDS_PER_PRISONER = 1     # Case 28.17
INITIAL_MOVE_HEXES = 3      # Case 28.12


@dataclass
class PrisonerGroup:
    """A group of prisoner points at a location.

    Case 28.0 — Tracks prisoner count, guard status, and supplies.
    """
    side_captured: str  # Which side these prisoners belong to.
    prisoner_points: int = 0
    guard_points: int = 0
    hex_id: str = ""

    @property
    def is_guarded(self) -> bool:
        """Case 28.17 — Enough guards assigned."""
        return self.guard_points >= self.prisoner_points

    @property
    def stores_required(self) -> int:
        """Case 28.15 — Stores needed per ops stage."""
        return (self.prisoner_points + 4) // 5  # Ceiling div.
