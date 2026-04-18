"""Case 4.0, 8.37, 60.5 — Catalog of all named and referenced hexes.

This catalog encodes every hex referenced by name, hex ID, or feature
in the CNA rulebook. It provides terrain type, named features, port
capacity, and air facility status for each hex.

Hexes not in this catalog are assumed to be default desert terrain.
The catalog is the authoritative source for named hexes; the map_builder
module fills in surrounding desert hexes to create a complete grid.

Sources:
  - Case 60.31/60.41: Unit deployment hex IDs.
  - Case 60.5: Air facility locations.
  - Case 60.7: Construction/port state at scenario start.
  - Case 8.37: Terrain types.
  - Case 8.71: Rail lines.
  - Various sections: Named places referenced in rules text.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from cna.engine.game_state import HexCoord, Side, TerrainType
from cna.data.maps.coords import hex_id_to_coord


# ---------------------------------------------------------------------------
# Hex entry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HexEntry:
    """A cataloged hex with known attributes.

    Case 4.0 — Properties from the game map and rules.
    """
    hex_id: str
    coord: HexCoord
    name: str = ""
    terrain: TerrainType = TerrainType.DESERT
    port_capacity: int = 0
    has_airfield: bool = False
    has_landing_strip: bool = False
    has_flying_boat_basin: bool = False
    has_flying_boat_area: bool = False
    initial_controller: Side | None = None
    road_connections: tuple[str, ...] = ()
    track_connections: tuple[str, ...] = ()
    rail_connections: tuple[str, ...] = ()


def _h(hex_id: str, name: str = "", terrain: TerrainType = TerrainType.DESERT,
       port: int = 0, airfield: bool = False, strip: bool = False,
       fb_basin: bool = False, fb_area: bool = False,
       ctrl: Side | None = None,
       roads: tuple[str, ...] = (), tracks: tuple[str, ...] = (),
       rails: tuple[str, ...] = ()) -> HexEntry:
    return HexEntry(
        hex_id=hex_id, coord=hex_id_to_coord(hex_id), name=name,
        terrain=terrain, port_capacity=port,
        has_airfield=airfield, has_landing_strip=strip,
        has_flying_boat_basin=fb_basin, has_flying_boat_area=fb_area,
        initial_controller=ctrl,
        road_connections=roads, track_connections=tracks,
        rail_connections=rails,
    )


AX = Side.AXIS
CW = Side.COMMONWEALTH

# ---------------------------------------------------------------------------
# Hex catalog — all named/referenced hexes from the rulebook
# ---------------------------------------------------------------------------

# Organized by map section (A-E), west to east.
# Sources: Case 60.31, 60.41, 60.5, 60.7, 8.71, and named references
# throughout the rules.

HEX_CATALOG: tuple[HexEntry, ...] = (
    # ===== MAP SECTION A (Tripolitania / western Libya) =====
    _h("A1816", "El Agheila", strip=True, ctrl=AX),
    _h("A2021", "Mersa Brega", ctrl=AX),
    _h("A2109", "Marble Arch", ctrl=AX),
    _h("A2629", "Agadabia", ctrl=AX),
    _h("A2802", "Tripolitania Entry", ctrl=AX),
    _h("A4130", "Soluch", terrain=TerrainType.TOWN, airfield=True, ctrl=AX),
    _h("A4728", "El Berea", airfield=True, ctrl=AX),
    _h("A4829", "Benina", terrain=TerrainType.TOWN, airfield=True, ctrl=AX),

    # ===== MAP SECTION B (Cyrenaica) =====
    _h("B0707", "Augila", strip=True, ctrl=AX),
    _h("B4827", "Benghazi", terrain=TerrainType.CITY, port=5, airfield=True,
        ctrl=AX),
    _h("B4921", "Mechili", strip=True, ctrl=AX),
    _h("B4933", "Gazala", strip=True, ctrl=AX),
    _h("B5229", "Tmimi", strip=True, ctrl=AX),
    _h("B5331", "Bomba", fb_basin=True, ctrl=AX),
    _h("B5410", "Maraua", strip=True, ctrl=AX),
    _h("B5504", "Barce", terrain=TerrainType.TOWN, airfield=True, ctrl=AX,
        rails=("B5504",)),  # Soluch-Benghazi-Barce rail (historical only)
    _h("B5526", "Martuba", airfield=True, ctrl=AX),
    _h("B5825", terrain=TerrainType.DESERT, ctrl=AX),
    _h("B5917", "Ztert", strip=True, ctrl=AX),
    _h("B5925", "Derna", terrain=TerrainType.PORT, port=2,
        fb_area=True, ctrl=AX),

    # ===== MAP SECTION C (Frontier zone — main operational area) =====
    _h("C0127", "Siwa", terrain=TerrainType.OASIS, strip=True, ctrl=CW),
    _h("C0716", terrain=TerrainType.DESERT, ctrl=AX),
    _h("C1014", "Giarabub", terrain=TerrainType.OASIS, strip=True, ctrl=AX),
    _h("C1715", "el Grein", ctrl=AX),
    _h("C3019", "Fort Maddalena", strip=True, ctrl=AX),
    _h("C3320", ctrl=CW),
    _h("C3419", "Bir Scheferzen", ctrl=AX),
    _h("C3520", ctrl=CW),
    _h("C3617", ctrl=AX),
    _h("C3618", "Sidi Omar", strip=True, ctrl=AX),
    _h("C3721", ctrl=CW),
    _h("C3918", ctrl=AX),
    _h("C3919", ctrl=AX),
    _h("C3920", ctrl=AX),
    _h("C3922", "Halfaya Pass", terrain=TerrainType.ESCARPMENT, ctrl=CW),
    _h("C3926", "Buq Buq", strip=True, ctrl=CW),
    _h("C4020", "Fort Capuzzo", strip=True, ctrl=AX),
    _h("C4021", "Sollum", strip=True, ctrl=CW),
    _h("C4108", "Bir el Gubi", strip=True),
    _h("C4119", strip=True, ctrl=AX),
    _h("C4120", ctrl=AX),
    _h("C4131", "Sidi Barrani", strip=True, ctrl=CW),
    _h("C4218", "Sidi Azeiz", strip=True, ctrl=AX),
    _h("C4219", ctrl=AX),
    _h("C4321", "Bardia", terrain=TerrainType.PORT, port=2, strip=True, ctrl=AX),
    _h("C4414", "Gambut", strip=True),
    _h("C4419", "Menastir", strip=True),
    _h("C4507", "El Adem", airfield=True, ctrl=AX),
    _h("C4707", ctrl=AX),
    _h("C4807", "Tobruk", terrain=TerrainType.PORT, port=7, strip=True, ctrl=AX),

    # ===== MAP SECTION D (Western Egypt) =====
    _h("D3227", "Qotifiya", strip=True, ctrl=CW),
    _h("D3231", strip=True, ctrl=CW),
    _h("D3323", "Fuka", strip=True, ctrl=CW),
    _h("D3416", strip=True, ctrl=CW),
    _h("D3418", "Sidi Haneish", strip=True, ctrl=CW),
    _h("D3516", strip=True, ctrl=CW),
    _h("D3520", "Matten Baggush", strip=True, ctrl=CW),
    _h("D3612", ctrl=CW),
    _h("D3615", ctrl=CW),
    _h("D3714", "Mersa Matruh", terrain=TerrainType.PORT, port=3,
        airfield=True, ctrl=CW,
        rails=("D3714",)),  # Rail terminus (Case 8.71)
    _h("D3903", strip=True, ctrl=CW),

    # ===== MAP SECTION E (Nile Delta / eastern Egypt) =====
    _h("E1430", "Cairo", terrain=TerrainType.CITY, airfield=True, ctrl=CW),
    _h("E1829", "El Alamein", ctrl=CW),
    _h("E2132", "Abbassia", airfield=True, ctrl=CW),
    _h("E2133", "Almaza", airfield=True, ctrl=CW),
    _h("E2212", "Amiriya", airfield=True, ctrl=CW),
    _h("E3007", "El Hamman", strip=True, ctrl=CW),
    _h("E3109", "Burg el Arab", strip=True, ctrl=CW),
    _h("E3512", "Dekheila", airfield=True, ctrl=CW),
    _h("E3613", "Alexandria", terrain=TerrainType.CITY, port=10,
        airfield=True, ctrl=CW,
        rails=("E3613",)),  # Rail start (Case 8.71)
    _h("E3614", "Alexandria (harbor)", fb_basin=True, ctrl=CW),
    _h("E3714", "Alexandria East", airfield=True, ctrl=CW),
    _h("E3815", "Aboukir", airfield=True, ctrl=CW),
)

# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

_BY_HEX_ID: dict[str, HexEntry] = {e.hex_id: e for e in HEX_CATALOG}
_BY_NAME: dict[str, HexEntry] = {e.name: e for e in HEX_CATALOG if e.name}
_BY_COORD: dict[HexCoord, HexEntry] = {e.coord: e for e in HEX_CATALOG}


def get_by_hex_id(hex_id: str) -> HexEntry | None:
    """Look up a hex entry by game hex ID (e.g. 'C4807')."""
    return _BY_HEX_ID.get(hex_id.upper())


def get_by_name(name: str) -> HexEntry | None:
    """Look up a hex entry by place name (e.g. 'Tobruk')."""
    return _BY_NAME.get(name)


def get_by_coord(coord: HexCoord) -> HexEntry | None:
    """Look up a hex entry by axial coordinate."""
    return _BY_COORD.get(coord)


def all_entries() -> tuple[HexEntry, ...]:
    """Return all catalog entries."""
    return HEX_CATALOG
