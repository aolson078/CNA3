"""Case 4.1 — Hex coordinate system.

CNA uses five map sections (A-E) laid west to east. Each section has
hex IDs like "C4218" where C is the section, 42 is the column, and 18
is the row. Sections overlap: column 01 of section N overlays column 39
of section N-1.

This module converts between game hex IDs and axial (q, r) coordinates
used by the engine (cna/engine/hex_map.py).

Global axial mapping:
  q = section_offset + column
  r = row

Section offsets:
  A: 0   (columns ~01-59)
  B: 38  (B.01 = A.39)
  C: 76  (C.01 = B.39 = A.77)
  D: 114 (D.01 = C.39 = A.115)
  E: 152 (E.01 = D.39 = A.153)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from cna.engine.game_state import HexCoord


# ---------------------------------------------------------------------------
# Section offsets (Case 4.1 / 4.22)
# ---------------------------------------------------------------------------

SECTION_OFFSETS: dict[str, int] = {
    "A": 0,
    "B": 38,
    "C": 76,
    "D": 114,
    "E": 152,
}

SECTIONS = ("A", "B", "C", "D", "E")


# ---------------------------------------------------------------------------
# Game hex ID
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GameHexId:
    """A parsed game hex ID.

    Case 4.1 — e.g. "C4218" → section='C', col=42, row=18.
    """
    section: str
    col: int
    row: int

    def __str__(self) -> str:
        return f"{self.section}{self.col:02d}{self.row:02d}"

    def to_coord(self) -> HexCoord:
        """Convert to axial (q, r) via section offset."""
        offset = SECTION_OFFSETS.get(self.section, 0)
        return HexCoord(q=offset + self.col, r=self.row)


def parse_hex_id(hex_id: str) -> GameHexId:
    """Parse a game hex ID string like 'C4218'.

    Case 4.1 — One letter (A-E) + four digits (col + row).

    Raises:
        ValueError: if the string is malformed.
    """
    hex_id = hex_id.strip().upper()
    if len(hex_id) < 5:
        raise ValueError(f"Hex ID too short: '{hex_id}'")
    section = hex_id[0]
    if section not in SECTION_OFFSETS:
        raise ValueError(f"Unknown map section: '{section}'")
    try:
        col = int(hex_id[1:3])
        row = int(hex_id[3:5])
    except ValueError as exc:
        raise ValueError(f"Invalid hex digits in '{hex_id}': {exc}") from exc
    return GameHexId(section=section, col=col, row=row)


def hex_id_to_coord(hex_id: str) -> HexCoord:
    """Shorthand: parse a hex ID string and return axial coord."""
    return parse_hex_id(hex_id).to_coord()


def coord_to_hex_id(coord: HexCoord) -> Optional[GameHexId]:
    """Reverse-map an axial coord to a GameHexId.

    Returns the hex ID in the westernmost section where the column falls
    within the non-overlapping range (1-38). If the column is in the
    overlap zone (39-59), the western section is preferred to match
    the convention that e.g. B5504 is the canonical ID for that hex.
    Returns None if the coord is outside all sections.
    """
    q, r = coord.q, coord.r
    if r < 0 or q < 0:
        return None
    for section in SECTIONS:
        offset = SECTION_OFFSETS[section]
        col = q - offset
        if 1 <= col <= 59:
            return GameHexId(section=section, col=col, row=r)
    return None
