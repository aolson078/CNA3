"""Section 3.6 — Limited Intelligence view model.

Produces a sanitized view of a GameState from a specific side's
perspective, enforcing Case 3.6 and 3.61: "Players are not entitled to
any knowledge of the status, composition, or any other attributes of any
opposing counter in CNA except as expressly indicated in the rules."

Case 3.62 enumerates what an opposing player IS entitled to see. This
module applies those rules centrally so UI panels and logs don't have to
re-implement them.

The view model is read-only: it copies the fields a viewing side is
allowed to see and redacts everything else. The runtime GameState itself
is never mutated.

Key policies (Case 3.62):
  - On-map stacks are visible (you can see that *some* units are in a hex),
    but their composition/strength is hidden.
  - Patrol and Air Recon leak limited info (categories only).
  - Prisoners reveal nothing beyond totals.
  - Trucks and Replacement Points are always secret.

For now (Layer 1), we implement the conservative version: an enemy unit
exposes only its side and its hex, nothing else. Patrols/recon refinements
come in later sections.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from cna.engine.game_state import (
    GameState,
    HexCoord,
    LogEntry,
    MapHex,
    OrgSize,
    Side,
    Unit,
    UnitClass,
    UnitType,
)


@dataclass
class UnitView:
    """A sanitized view of a Unit.

    Fields not visible to the viewing side are None or left as defaults.
    Case 3.62 governs what is revealed.
    """

    id: str
    side: Side
    position: Optional[HexCoord]
    is_friendly: bool
    # The following fields are populated only for friendly units (unless a
    # specific rule like Patrol/Recon has revealed them):
    name: Optional[str] = None
    unit_type: Optional[UnitType] = None
    unit_class: Optional[UnitClass] = None
    org_size: Optional[OrgSize] = None
    current_toe: Optional[int] = None
    max_toe: Optional[int] = None
    current_morale: Optional[int] = None
    cohesion: Optional[str] = None
    reserve_status: Optional[str] = None
    pinned: Optional[bool] = None
    broken_down: Optional[bool] = None
    capability_points_spent: Optional[int] = None
    capability_point_allowance: Optional[int] = None

    @property
    def is_opaque(self) -> bool:
        """True if only side/position are known (i.e. enemy unit at full fog)."""
        return not self.is_friendly and self.name is None


@dataclass
class HexView:
    """A sanitized view of a MapHex and its stack.

    The hex's terrain and named feature are always visible (the map is
    public). The units stacked there are projected through UnitView, so
    enemy stacks show as N opaque units.
    """

    hex: MapHex
    units: list[UnitView] = field(default_factory=list)

    @property
    def stack_count(self) -> int:
        return len(self.units)

    def friendly_units(self) -> list[UnitView]:
        return [u for u in self.units if u.is_friendly]

    def enemy_units(self) -> list[UnitView]:
        return [u for u in self.units if not u.is_friendly]


@dataclass
class GameView:
    """The full dashboard-ready view of a GameState from one side's POV.

    Attributes:
        state: The underlying GameState (for fields that are always public:
            turn/stage/phase/active_side/weather/players).
        viewer: Which side this view is for.
        units: UnitView for every unit (friendly = full, enemy = redacted).
        hexes: HexView for every on-map hex.
        log: Log entries, redacted so that enemy-side entries surface only
            phase-level context, not content (Case 3.6).
    """

    state: GameState
    viewer: Side
    units: list[UnitView]
    hexes: dict[HexCoord, HexView]
    log: list[LogEntry]

    # -- convenience --------------------------------------------------

    def hex_at(self, coord: HexCoord) -> Optional[HexView]:
        return self.hexes.get(coord)

    def friendly_units(self) -> list[UnitView]:
        return [u for u in self.units if u.is_friendly]

    def enemy_units(self) -> list[UnitView]:
        return [u for u in self.units if not u.is_friendly]

    def friendly_on_map(self) -> list[UnitView]:
        return [u for u in self.friendly_units() if u.position is not None]


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def project_unit(unit: Unit, viewer: Side) -> UnitView:
    """Project a Unit through the viewer's knowledge.

    Case 3.61 — "Players are not entitled to any knowledge of the status,
    composition, or any other attributes of any opposing counter ...
    except as expressly indicated in the rules."

    Friendly units are fully visible. Enemy units show only side + position
    (you can see a stack on the map; Case 3.62 "Map" entry).
    """
    is_friendly = unit.side == viewer
    if not is_friendly:
        return UnitView(
            id=unit.id,
            side=unit.side,
            position=unit.position,
            is_friendly=False,
        )
    return UnitView(
        id=unit.id,
        side=unit.side,
        position=unit.position,
        is_friendly=True,
        name=unit.name,
        unit_type=unit.unit_type,
        unit_class=unit.unit_class,
        org_size=unit.org_size,
        current_toe=unit.current_toe,
        max_toe=unit.stats.max_toe_strength,
        current_morale=unit.current_morale,
        cohesion=unit.cohesion.value,
        reserve_status=unit.reserve_status.value,
        pinned=unit.pinned,
        broken_down=unit.broken_down,
        capability_points_spent=unit.capability_points_spent,
        capability_point_allowance=unit.stats.capability_point_allowance,
    )


def _project_log(entries: list[LogEntry], viewer: Side) -> list[LogEntry]:
    """Redact log entries belonging to the opposing side.

    Case 3.6 — The viewer should see *that* something happened on the
    enemy's turn (so they know phases advanced) but not the content.

    Policy: entries whose side is the viewer, or None (global), pass
    through unchanged. Entries from the enemy side are replaced with a
    stub showing only turn/stage/phase/side and a generic message.
    """
    redacted: list[LogEntry] = []
    for e in entries:
        if e.side is None or e.side == viewer:
            redacted.append(e)
            continue
        redacted.append(
            LogEntry(
                seq=e.seq,
                turn=e.turn,
                stage=e.stage,
                phase=e.phase,
                side=e.side,
                message="(enemy action)",
                category=e.category,
                data={},
            )
        )
    return redacted


def build_view(state: GameState, viewer: Side) -> GameView:
    """Build a GameView of *state* from *viewer*'s perspective.

    The returned view is a read-only snapshot; mutating *state* afterwards
    won't affect the view (aside from shared MapHex references, which are
    treated as immutable from the UI's perspective).
    """
    unit_views = [project_unit(u, viewer) for u in state.units.values()]

    # Group units by position into HexView objects.
    hex_views: dict[HexCoord, HexView] = {
        coord: HexView(hex=mh) for coord, mh in state.map.items()
    }
    for uv in unit_views:
        if uv.position is None:
            continue
        hv = hex_views.get(uv.position)
        if hv is None:
            # Off-map-but-positioned shouldn't happen, but don't crash.
            continue
        hv.units.append(uv)

    return GameView(
        state=state,
        viewer=viewer,
        units=unit_views,
        hexes=hex_views,
        log=_project_log(state.turn_log, viewer),
    )
