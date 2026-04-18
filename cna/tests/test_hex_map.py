"""Smoke tests for cna.engine.hex_map."""

from __future__ import annotations

import pytest

from cna.engine.game_state import HexCoord, MapHex, TerrainType
from cna.engine.hex_map import (
    AXIAL_NEIGHBORS,
    HexMap,
    distance,
    hex_range,
    hex_ring,
    is_adjacent,
    line,
    neighbors,
)


def test_neighbors_returns_six():
    ns = neighbors(HexCoord(0, 0))
    assert len(ns) == 6
    # All six canonical neighbor offsets applied to origin.
    expected = {HexCoord(dq, dr) for (dq, dr) in AXIAL_NEIGHBORS}
    assert set(ns) == expected


def test_is_adjacent_symmetric():
    a, b = HexCoord(0, 0), HexCoord(1, 0)
    assert is_adjacent(a, b)
    assert is_adjacent(b, a)
    assert not is_adjacent(a, HexCoord(5, 5))


def test_distance_self_is_zero():
    assert distance(HexCoord(3, -2), HexCoord(3, -2)) == 0


def test_distance_adjacent_is_one():
    origin = HexCoord(0, 0)
    for n in neighbors(origin):
        assert distance(origin, n) == 1


def test_distance_symmetric():
    a, b = HexCoord(2, 5), HexCoord(-3, 1)
    assert distance(a, b) == distance(b, a)


def test_distance_triangle_inequality():
    a, b, c = HexCoord(0, 0), HexCoord(3, 4), HexCoord(-2, 1)
    assert distance(a, c) <= distance(a, b) + distance(b, c)


def test_hex_ring_sizes():
    c = HexCoord(0, 0)
    assert hex_ring(c, 0) == [c]
    assert len(hex_ring(c, 1)) == 6
    assert len(hex_ring(c, 2)) == 12
    assert len(hex_ring(c, 3)) == 18


def test_hex_ring_rejects_negative():
    with pytest.raises(ValueError):
        hex_ring(HexCoord(0, 0), -1)


def test_hex_range_inclusive():
    c = HexCoord(0, 0)
    r0 = hex_range(c, 0)
    r1 = hex_range(c, 1)
    r2 = hex_range(c, 2)
    assert r0 == [c]
    assert len(r1) == 1 + 6
    assert len(r2) == 1 + 6 + 12


def test_line_endpoints_included():
    a, b = HexCoord(0, 0), HexCoord(3, -1)
    path = line(a, b)
    assert path[0] == a
    assert path[-1] == b
    # Every adjacent pair is actually adjacent.
    for p, q in zip(path, path[1:]):
        assert is_adjacent(p, q)


def _make_map() -> HexMap:
    hexes = [
        MapHex(coord=HexCoord(0, 0), terrain=TerrainType.TOWN, name="Alpha"),
        MapHex(coord=HexCoord(1, 0), terrain=TerrainType.DESERT),
        MapHex(coord=HexCoord(0, 1), terrain=TerrainType.DESERT),
    ]
    return HexMap.from_iterable(hexes)


def test_hexmap_contains_and_get():
    m = _make_map()
    assert HexCoord(0, 0) in m
    assert HexCoord(99, 99) not in m
    assert m.get(HexCoord(0, 0)).name == "Alpha"
    assert m.get(HexCoord(99, 99)) is None


def test_hexmap_require_raises():
    m = _make_map()
    with pytest.raises(KeyError):
        m.require(HexCoord(99, 99))


def test_hexmap_neighbors_in_bounds():
    m = _make_map()
    # Origin has two in-bounds neighbors among the test map.
    ns = m.neighbors_in_bounds(HexCoord(0, 0))
    assert set(ns) == {HexCoord(1, 0), HexCoord(0, 1)}


def test_hexmap_terrain_lookup():
    m = _make_map()
    assert m.terrain_at(HexCoord(0, 0)) == TerrainType.TOWN
    assert m.terrain_at(HexCoord(1, 0)) == TerrainType.DESERT
    assert m.terrain_at(HexCoord(99, 99)) is None


def test_hexmap_road_requires_both_sides():
    a, b = HexCoord(0, 0), HexCoord(1, 0)
    # Only one side connected -> no road.
    ha = MapHex(coord=a, road_exits=frozenset({b}))
    hb = MapHex(coord=b)  # no exit back
    m = HexMap.from_iterable([ha, hb])
    assert not m.has_road(a, b)
    # Both sides connected -> road.
    ha2 = MapHex(coord=a, road_exits=frozenset({b}))
    hb2 = MapHex(coord=b, road_exits=frozenset({a}))
    m2 = HexMap.from_iterable([ha2, hb2])
    assert m2.has_road(a, b)
    assert m2.has_road(b, a)
