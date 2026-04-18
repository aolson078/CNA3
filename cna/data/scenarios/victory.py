"""Case 60.8 — Victory Conditions for Operation Compass scenarios.

Implements Cases 60.81 (Graziani's Offensive) and 60.82 (Italian
Campaign) victory determination.

Graziani's Offensive (Case 60.81):
  - Italian Strategic Victory: hold Alexandria or Cairo.
  - Italian Decisive Victory: hold Mersa Matruh AND Siwa.
  - Italian Tactical Victory: hold Sidi Barrani AND Sollum AND
    Fort Maddalena AND Giarabub.
  - CW Tactical Victory: hold Sollum AND Halfaya Pass AND Siwa.
  - CW Decisive Victory: hold Bardia, Ft. Maddalena, Sidi Omar,
    Sollum, AND Siwa.
  - CW Strategic Victory: hold Tobruk.

The Italian Campaign (Case 60.82):
  - Victory Points for holding named locations.
  - If no Italian combat units can trace supply → CW Strategic Victory.
  - Otherwise most VP wins.

Cross-references:
  - Case 60.7: Starting construction state.
  - Case 32.16: Supply line tracing for VP eligibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from cna.engine.game_state import GameState, Side
from cna.data.maps.hex_catalog import get_by_name


class VictoryLevel(str, Enum):
    """Case 60.8 — Victory levels."""
    STRATEGIC = "strategic"
    DECISIVE = "decisive"
    TACTICAL = "tactical"
    DRAW = "draw"


@dataclass(frozen=True)
class VictoryResult:
    """Outcome of a victory check.

    Case 60.8 — Who wins, at what level, and why.
    """
    winner: Side | None
    level: VictoryLevel
    reason: str


def _controls(state: GameState, place_name: str, side: Side) -> bool:
    """Check if *side* has a combat unit at *place_name*."""
    entry = get_by_name(place_name)
    if entry is None:
        return False
    units = [u for u in state.units_at(entry.coord)
             if u.side == side and u.is_combat_unit()]
    return len(units) > 0


def check_graziani_victory(state: GameState) -> VictoryResult:
    """Check victory conditions for Graziani's Offensive (Case 60.81).

    Called at the end of Game-Turn 6.
    """
    AX = Side.AXIS
    CW = Side.COMMONWEALTH

    # Italian Strategic: hold Alexandria or Cairo.
    if _controls(state, "Alexandria", AX) or _controls(state, "Cairo", AX):
        return VictoryResult(AX, VictoryLevel.STRATEGIC,
                           "Axis holds Alexandria or Cairo")

    # Italian Decisive: hold Mersa Matruh AND Siwa.
    if _controls(state, "Mersa Matruh", AX) and _controls(state, "Siwa", AX):
        return VictoryResult(AX, VictoryLevel.DECISIVE,
                           "Axis holds Mersa Matruh and Siwa")

    # Italian Tactical: hold Sidi Barrani + Sollum + Ft Maddalena + Giarabub.
    if (    _controls(state, "Sidi Barrani", AX)
        and _controls(state, "Sollum", AX)
        and _controls(state, "Fort Maddalena", AX)
        and _controls(state, "Giarabub", AX)):
        return VictoryResult(AX, VictoryLevel.TACTICAL,
                           "Axis holds Sidi Barrani, Sollum, Ft Maddalena, Giarabub")

    # CW Strategic: hold Tobruk.
    if _controls(state, "Tobruk", CW):
        return VictoryResult(CW, VictoryLevel.STRATEGIC,
                           "Commonwealth holds Tobruk")

    # CW Decisive: hold Bardia + Ft Maddalena + Sidi Omar + Sollum + Siwa.
    if (    _controls(state, "Bardia", CW)
        and _controls(state, "Fort Maddalena", CW)
        and _controls(state, "Sidi Omar", CW)
        and _controls(state, "Sollum", CW)
        and _controls(state, "Siwa", CW)):
        return VictoryResult(CW, VictoryLevel.DECISIVE,
                           "Commonwealth holds Bardia, Ft Maddalena, Sidi Omar, Sollum, Siwa")

    # CW Tactical: hold Sollum + Halfaya Pass + Siwa.
    if (    _controls(state, "Sollum", CW)
        and _controls(state, "Halfaya Pass", CW)
        and _controls(state, "Siwa", CW)):
        return VictoryResult(CW, VictoryLevel.TACTICAL,
                           "Commonwealth holds Sollum, Halfaya Pass, Siwa")

    return VictoryResult(None, VictoryLevel.DRAW, "No victory conditions met")


# ---------------------------------------------------------------------------
# Italian Campaign VP (Case 60.82)
# ---------------------------------------------------------------------------

# (place_name, Italian_VP, CW_VP)
_VP_LOCATIONS: tuple[tuple[str, int, int], ...] = (
    ("Mersa Matruh", 5, 2),
    ("Tobruk", 3, 5),
    ("Derna", 2, 3),
    ("Giarabub", 2, 2),
    ("Siwa", 2, 2),
    ("Benghazi", 1, 5),
    ("Agadabia", 1, 3),
    ("Mersa Brega", 1, 2),
)


def check_italian_campaign_victory(state: GameState) -> VictoryResult:
    """Check victory for The Italian Campaign (Case 60.82).

    Called at the end of Game-Turn 20.
    """
    AX = Side.AXIS
    CW = Side.COMMONWEALTH

    # If no Italian combat units can trace supply → CW Strategic.
    axis_combat = [u for u in state.units.values()
                   if u.side == AX and u.is_combat_unit() and u.position is not None]
    if not axis_combat:
        return VictoryResult(CW, VictoryLevel.STRATEGIC,
                           "No Axis combat units on map")

    ax_vp = 0
    cw_vp = 0
    for name, ax_pts, cw_pts in _VP_LOCATIONS:
        if _controls(state, name, AX):
            ax_vp += ax_pts
        elif _controls(state, name, CW):
            cw_vp += cw_pts

    if ax_vp > cw_vp:
        return VictoryResult(AX, VictoryLevel.TACTICAL,
                           f"Axis VP {ax_vp} vs CW VP {cw_vp}")
    if cw_vp > ax_vp:
        return VictoryResult(CW, VictoryLevel.TACTICAL,
                           f"CW VP {cw_vp} vs Axis VP {ax_vp}")
    return VictoryResult(None, VictoryLevel.DRAW,
                        f"Tied VP: Axis {ax_vp}, CW {cw_vp}")
