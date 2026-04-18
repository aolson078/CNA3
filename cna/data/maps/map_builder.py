"""Case 4.1 — Build a complete GameState.map from the hex catalog.

Generates a full hex grid covering the operational area (the Egypt-Libya
frontier where combat occurs), populates it with terrain from the
hex_catalog, and fills uncataloged hexes with default desert.

The operational area spans roughly:
  - Map C columns 01-48, rows 01-33 (frontier zone)
  - Map D columns 30-39, rows 01-33 (western Egypt)
  - Map B columns 40-59, rows 01-33 (Cyrenaica)
  - Selectively: Map A and E named hexes

Full 5-section grid generation (A01,01 through E59,33) creates ~15,000
hexes. For Layer 1 we generate the operational subset plus all cataloged
hexes from any section, which gives adequate coverage for Operation
Compass while keeping the map manageable.
"""

from __future__ import annotations

from cna.engine.game_state import HexCoord, MapHex, Side, TerrainType
from cna.data.maps.coords import SECTION_OFFSETS, GameHexId, hex_id_to_coord
from cna.data.maps.hex_catalog import HexEntry, all_entries, get_by_coord


# ---------------------------------------------------------------------------
# Operational area bounds
# ---------------------------------------------------------------------------

# The main fighting zone for Operation Compass.
_OP_AREA: list[tuple[str, int, int, int, int]] = [
    # (section, col_min, col_max, row_min, row_max)
    ("B", 40, 59, 1, 33),   # Eastern Cyrenaica (Benghazi to Derna)
    ("C", 1, 48, 1, 33),    # Full frontier zone
    ("D", 30, 39, 1, 33),   # Western Egypt (Matruh area)
]


def _in_operational_area(section: str, col: int, row: int) -> bool:
    for s, c_min, c_max, r_min, r_max in _OP_AREA:
        if s == section and c_min <= col <= c_max and r_min <= row <= r_max:
            return True
    return False


# ---------------------------------------------------------------------------
# Map construction
# ---------------------------------------------------------------------------


def _catalog_entry_to_maphex(entry: HexEntry) -> MapHex:
    """Convert a HexEntry to a MapHex with road/track/rail connections."""
    road_exits = frozenset(hex_id_to_coord(hid) for hid in entry.road_connections)
    track_exits = frozenset(hex_id_to_coord(hid) for hid in entry.track_connections)
    rail_exits = frozenset(hex_id_to_coord(hid) for hid in entry.rail_connections)

    return MapHex(
        coord=entry.coord,
        terrain=entry.terrain,
        name=entry.name,
        port_capacity=entry.port_capacity,
        has_airfield=entry.has_airfield,
        has_landing_strip=entry.has_landing_strip,
        has_flying_boat_basin=entry.has_flying_boat_basin,
        has_flying_boat_area=entry.has_flying_boat_area,
        controller=entry.initial_controller,
        road_exits=road_exits,
        track_exits=track_exits,
        rail_exits=rail_exits,
    )


def build_full_map(*, include_grid: bool = True) -> dict[HexCoord, MapHex]:
    """Build the complete game map.

    Case 4.1 — Generates hexes from the catalog plus a default desert
    grid for the operational area.

    Args:
        include_grid: If True, fills the operational area with default
            desert hexes. If False, only cataloged hexes are included
            (useful for tests that want a sparse map).

    Returns:
        dict[HexCoord, MapHex] suitable for GameState.map.
    """
    result: dict[HexCoord, MapHex] = {}

    # Step 1: Generate the operational area grid with default desert.
    if include_grid:
        for section, c_min, c_max, r_min, r_max in _OP_AREA:
            offset = SECTION_OFFSETS[section]
            for col in range(c_min, c_max + 1):
                for row in range(r_min, r_max + 1):
                    coord = HexCoord(offset + col, row)
                    if coord not in result:
                        result[coord] = MapHex(
                            coord=coord,
                            terrain=TerrainType.DESERT,
                        )

    # Step 2: Overlay all cataloged hexes (overrides defaults).
    for entry in all_entries():
        result[entry.coord] = _catalog_entry_to_maphex(entry)

    return result


def build_operational_map() -> dict[HexCoord, MapHex]:
    """Build the operational-area map with full grid fill.

    Case 4.1 — The standard map for gameplay. Includes ~2,000 hexes
    covering the Cyrenaica-to-Matruh operational zone plus all named
    hexes from the catalog.
    """
    return build_full_map(include_grid=True)


def build_catalog_only_map() -> dict[HexCoord, MapHex]:
    """Build a map containing only cataloged (named) hexes.

    Useful for testing and scenario setup where you want only the
    referenced hexes without filling the grid.
    """
    return build_full_map(include_grid=False)
