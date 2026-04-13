"""Section 4.0, 8.0 — Hex map geometry and queries.

CNA uses a standard flat-topped hex grid. Coordinates are stored in
axial form (q, r); see https://www.redblobgames.com/grids/hexagons/
for background.

This module provides:
  - Neighbor enumeration (the six hexes adjacent to a given hex).
  - Distance (shortest hex path, ignoring terrain).
  - Hex-based line drawing (for future LOS / reconnaissance).
  - HexMap container: thin wrapper over GameState.map with spatial helpers.

Terrain-aware movement-point costs and ZoC interactions live in the
respective rules modules (cna/rules/terrain/, cna/rules/land_movement.py,
cna/rules/zones_of_control.py). This module provides only the geometry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator

from cna.engine.game_state import HexCoord, MapHex, TerrainType


# The six axial neighbor offsets, in a canonical order (N, NE, SE, S, SW, NW).
# Flat-topped hexes, "odd-r" style axial; see Red Blob reference.
AXIAL_NEIGHBORS: tuple[tuple[int, int], ...] = (
    (0, -1),   # N
    (+1, -1),  # NE
    (+1, 0),   # SE
    (0, +1),   # S
    (-1, +1),  # SW
    (-1, 0),   # NW
)


def neighbors(coord: HexCoord) -> list[HexCoord]:
    """Return the six hexes adjacent to *coord* in canonical order.

    Case 4.0 — A hex has six neighbors. No map-bounds check; callers that
    need in-bounds neighbors should filter against HexMap.
    """
    return [HexCoord(coord.q + dq, coord.r + dr) for (dq, dr) in AXIAL_NEIGHBORS]


def is_adjacent(a: HexCoord, b: HexCoord) -> bool:
    """True if *a* and *b* are adjacent (share a hex-edge)."""
    return b in neighbors(a)


def distance(a: HexCoord, b: HexCoord) -> int:
    """Hex distance between two coords (shortest path, ignoring terrain).

    Case 4.0 — Distance is counted in hexes. Uses the standard cube-axial
    distance formula.
    """
    dq = a.q - b.q
    dr = a.r - b.r
    ds = -dq - dr
    return (abs(dq) + abs(dr) + abs(ds)) // 2


def hex_ring(center: HexCoord, radius: int) -> list[HexCoord]:
    """Return all hexes exactly *radius* steps from *center*.

    Useful for reconnaissance range (Case 16.0) and barrage range (Case 12.0).
    """
    if radius < 0:
        raise ValueError("radius must be non-negative")
    if radius == 0:
        return [center]
    results: list[HexCoord] = []
    # Walk the ring: start at one corner, traverse six edges of length *radius*.
    cur = HexCoord(center.q + AXIAL_NEIGHBORS[4][0] * radius,
                   center.r + AXIAL_NEIGHBORS[4][1] * radius)
    for side in range(6):
        dq, dr = AXIAL_NEIGHBORS[side]
        for _ in range(radius):
            results.append(cur)
            cur = HexCoord(cur.q + dq, cur.r + dr)
    return results


def hex_range(center: HexCoord, radius: int) -> list[HexCoord]:
    """All hexes within *radius* steps of *center* (inclusive).

    Case 12.0 / Case 16.0 — Used for barrage range and recon range queries.
    """
    if radius < 0:
        raise ValueError("radius must be non-negative")
    results = [center]
    for r in range(1, radius + 1):
        results.extend(hex_ring(center, r))
    return results


def line(a: HexCoord, b: HexCoord) -> list[HexCoord]:
    """Straight line of hexes from *a* to *b*, inclusive.

    Used later for line-of-sight. Uses cube-coordinate linear interpolation
    then rounds to the nearest hex at each step.
    """
    n = distance(a, b)
    if n == 0:
        return [a]
    results: list[HexCoord] = []
    a_s = -a.q - a.r
    b_s = -b.q - b.r
    for i in range(n + 1):
        t = i / n
        q = a.q + (b.q - a.q) * t
        r = a.r + (b.r - a.r) * t
        s = a_s + (b_s - a_s) * t
        results.append(_cube_round(q, r, s))
    return results


def _cube_round(q: float, r: float, s: float) -> HexCoord:
    """Round fractional cube coords to the nearest hex."""
    rq = round(q)
    rr = round(r)
    rs = round(s)
    dq = abs(rq - q)
    dr = abs(rr - r)
    ds = abs(rs - s)
    if dq > dr and dq > ds:
        rq = -rr - rs
    elif dr > ds:
        rr = -rq - rs
    # else: rs is corrected implicitly
    return HexCoord(rq, rr)


# ---------------------------------------------------------------------------
# HexMap wrapper
# ---------------------------------------------------------------------------


@dataclass
class HexMap:
    """Spatial queries over a dict[HexCoord, MapHex].

    Thin adapter that operates on GameState.map. Kept as a separate class
    so that rules modules can take a HexMap parameter without needing the
    full GameState for read-only geometry.
    """

    hexes: dict[HexCoord, MapHex]

    # -- containment ----------------------------------------------------

    def __contains__(self, coord: object) -> bool:
        return isinstance(coord, HexCoord) and coord in self.hexes

    def __iter__(self) -> Iterator[HexCoord]:
        return iter(self.hexes)

    def __len__(self) -> int:
        return len(self.hexes)

    def get(self, coord: HexCoord) -> MapHex | None:
        """Return the MapHex at *coord*, or None if off-map."""
        return self.hexes.get(coord)

    def require(self, coord: HexCoord) -> MapHex:
        """Return the MapHex at *coord*, raising KeyError if off-map."""
        try:
            return self.hexes[coord]
        except KeyError as exc:
            raise KeyError(f"No hex at {coord}") from exc

    # -- neighbors ------------------------------------------------------

    def neighbors_in_bounds(self, coord: HexCoord) -> list[HexCoord]:
        """The subset of neighbors(coord) that exist on this map."""
        return [n for n in neighbors(coord) if n in self.hexes]

    def neighbor_hexes(self, coord: HexCoord) -> list[MapHex]:
        """Return MapHex objects for in-bounds neighbors of *coord*."""
        return [self.hexes[n] for n in self.neighbors_in_bounds(coord)]

    # -- terrain queries ------------------------------------------------

    def terrain_at(self, coord: HexCoord) -> TerrainType | None:
        """Terrain at *coord*, or None if off-map."""
        mh = self.hexes.get(coord)
        return mh.terrain if mh is not None else None

    def hexes_with_terrain(self, terrain: TerrainType) -> list[HexCoord]:
        """All coords whose primary terrain is *terrain*."""
        return [c for c, mh in self.hexes.items() if mh.terrain == terrain]

    # -- connectivity ---------------------------------------------------

    def has_road(self, a: HexCoord, b: HexCoord) -> bool:
        """True if a road connects hexes *a* and *b*.

        Case 8.7 — Rail/road/track movement requires the connection on both
        hex sides; we check symmetrically.
        """
        ma = self.hexes.get(a)
        mb = self.hexes.get(b)
        if ma is None or mb is None:
            return False
        return b in ma.road_exits and a in mb.road_exits

    def has_track(self, a: HexCoord, b: HexCoord) -> bool:
        """True if a desert track connects hexes *a* and *b*."""
        ma = self.hexes.get(a)
        mb = self.hexes.get(b)
        if ma is None or mb is None:
            return False
        return b in ma.track_exits and a in mb.track_exits

    def has_rail(self, a: HexCoord, b: HexCoord) -> bool:
        """True if rail connects hexes *a* and *b* (Case 8.7)."""
        ma = self.hexes.get(a)
        mb = self.hexes.get(b)
        if ma is None or mb is None:
            return False
        return b in ma.rail_exits and a in mb.rail_exits

    # -- construction helpers ------------------------------------------

    @classmethod
    def from_iterable(cls, hexes: Iterable[MapHex]) -> "HexMap":
        """Build a HexMap from an iterable of MapHex objects."""
        return cls({h.coord: h for h in hexes})
