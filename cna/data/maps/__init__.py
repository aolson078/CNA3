"""CNA hex map data.

Case 4.1 — The game map consists of five sections (A-E) laid west to
east. Each section uses 4-digit hex IDs where the first two digits are
the column and the last two are the row. Sections overlap: column 01 of
section N overlays column 39 of section N-1.

Modules:
  - coords: Hex ID parsing and global coordinate conversion.
  - hex_catalog: Named hexes, terrain, features for all referenced hexes.
  - map_builder: Constructs a full GameState.map from the catalog.
"""

from cna.data.maps.coords import GameHexId, parse_hex_id, hex_id_to_coord, coord_to_hex_id
from cna.data.maps.map_builder import build_full_map

__all__ = [
    "GameHexId",
    "build_full_map",
    "coord_to_hex_id",
    "hex_id_to_coord",
    "parse_hex_id",
]
