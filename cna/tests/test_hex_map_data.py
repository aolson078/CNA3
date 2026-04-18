"""Tests for cna.data.maps — coordinate system, hex catalog, and map builder."""

from __future__ import annotations

import pytest

from cna.engine.game_state import HexCoord, Side, TerrainType
from cna.data.maps.coords import (
    GameHexId,
    coord_to_hex_id,
    hex_id_to_coord,
    parse_hex_id,
)
from cna.data.maps.hex_catalog import (
    all_entries,
    get_by_coord,
    get_by_hex_id,
    get_by_name,
)
from cna.data.maps.map_builder import (
    build_catalog_only_map,
    build_full_map,
    build_operational_map,
)


# ---------------------------------------------------------------------------
# Coordinate parsing (Case 4.1)
# ---------------------------------------------------------------------------


def test_parse_hex_id_basic():
    gid = parse_hex_id("C4218")
    assert gid.section == "C"
    assert gid.col == 42
    assert gid.row == 18


def test_parse_hex_id_lowercase():
    gid = parse_hex_id("c4218")
    assert gid.section == "C"


def test_parse_hex_id_str():
    gid = parse_hex_id("B5504")
    assert str(gid) == "B5504"


def test_parse_hex_id_invalid_section():
    with pytest.raises(ValueError):
        parse_hex_id("Z1234")


def test_parse_hex_id_too_short():
    with pytest.raises(ValueError):
        parse_hex_id("C42")


# ---------------------------------------------------------------------------
# Section offset mapping
# ---------------------------------------------------------------------------


def test_section_offsets():
    # Map B col 01 = Map A col 39.
    a39 = hex_id_to_coord("A3900")
    b01 = hex_id_to_coord("B0100")
    assert a39 == b01, "B.01 should overlay A.39"

    # Map C col 01 = Map B col 39.
    b39 = hex_id_to_coord("B3900")
    c01 = hex_id_to_coord("C0100")
    assert b39 == c01, "C.01 should overlay B.39"


def test_hex_id_to_coord_tobruk():
    # Tobruk = C4807 → q=76+48=124, r=7.
    coord = hex_id_to_coord("C4807")
    assert coord == HexCoord(124, 7)


def test_hex_id_to_coord_alexandria():
    # Alexandria = E3613 → q=152+36=188, r=13.
    coord = hex_id_to_coord("E3613")
    assert coord == HexCoord(188, 13)


def test_coord_to_hex_id_roundtrip():
    for hex_id in ("A1816", "B5504", "C4807", "D3714", "E3613"):
        coord = hex_id_to_coord(hex_id)
        gid = coord_to_hex_id(coord)
        assert gid is not None
        assert str(gid) == hex_id


# ---------------------------------------------------------------------------
# Hex catalog
# ---------------------------------------------------------------------------


def test_catalog_has_key_locations():
    assert get_by_name("Tobruk") is not None
    assert get_by_name("Bardia") is not None
    assert get_by_name("Alexandria") is not None
    assert get_by_name("Mersa Matruh") is not None
    assert get_by_name("Cairo") is not None
    assert get_by_name("Benghazi") is not None
    assert get_by_name("Siwa") is not None


def test_catalog_tobruk_attributes():
    t = get_by_name("Tobruk")
    assert t is not None
    assert t.hex_id == "C4807"
    assert t.terrain == TerrainType.PORT
    assert t.port_capacity == 7  # Case 60.7 — Efficiency Level 7.
    assert t.initial_controller == Side.AXIS


def test_catalog_alexandria_attributes():
    a = get_by_name("Alexandria")
    assert a is not None
    assert a.hex_id == "E3613"
    assert a.terrain == TerrainType.CITY
    assert a.port_capacity == 10
    assert a.has_airfield
    assert a.initial_controller == Side.COMMONWEALTH


def test_catalog_lookup_by_hex_id():
    entry = get_by_hex_id("C4807")
    assert entry is not None
    assert entry.name == "Tobruk"


def test_catalog_lookup_by_coord():
    coord = hex_id_to_coord("C4807")
    entry = get_by_coord(coord)
    assert entry is not None
    assert entry.name == "Tobruk"


def test_catalog_all_entries_nonempty():
    entries = all_entries()
    assert len(entries) >= 50


def test_catalog_no_duplicate_coords():
    entries = all_entries()
    coords = [e.coord for e in entries]
    assert len(coords) == len(set(coords)), "Duplicate coords in catalog"


def test_catalog_no_duplicate_hex_ids():
    entries = all_entries()
    ids = [e.hex_id for e in entries]
    assert len(ids) == len(set(ids)), "Duplicate hex IDs in catalog"


def test_catalog_air_facilities():
    # Case 60.5 — check a sampling of air facilities.
    benina = get_by_name("Benina")
    assert benina is not None and benina.has_airfield

    bardia = get_by_hex_id("C4321")
    assert bardia is not None and bardia.has_landing_strip

    bomba = get_by_hex_id("B5331")
    assert bomba is not None and bomba.has_flying_boat_basin

    derna = get_by_name("Derna")
    assert derna is not None and derna.has_flying_boat_area


# ---------------------------------------------------------------------------
# Map builder
# ---------------------------------------------------------------------------


def test_catalog_only_map():
    m = build_catalog_only_map()
    assert len(m) == len(all_entries())
    tobruk_coord = hex_id_to_coord("C4807")
    assert tobruk_coord in m
    assert m[tobruk_coord].name == "Tobruk"


def test_operational_map_includes_grid():
    m = build_operational_map()
    # Should have many more hexes than just the catalog.
    assert len(m) > len(all_entries())
    # A random desert hex in the C section grid should exist.
    grid_hex = HexCoord(76 + 25, 15)  # C2515
    assert grid_hex in m
    assert m[grid_hex].terrain == TerrainType.DESERT


def test_operational_map_overlays_catalog():
    m = build_operational_map()
    tobruk_coord = hex_id_to_coord("C4807")
    assert m[tobruk_coord].name == "Tobruk"
    assert m[tobruk_coord].port_capacity == 7


def test_operational_map_has_all_deployment_hexes():
    """Every hex referenced in the Operation Compass deployment exists."""
    m = build_operational_map()
    deploy_hexes = [
        "C4218", "C4120", "C4020", "C3920", "C3919", "C3918", "C3617",
        "C4707", "C4507", "C4321", "C4807", "B4827", "B5925", "C1014",
        "C4131", "C3922", "C3020", "D3714", "D3612", "D3615", "E3613",
        "E1829", "E1430",
    ]
    for hid in deploy_hexes:
        coord = hex_id_to_coord(hid)
        assert coord in m, f"Deployment hex {hid} ({coord}) missing from map"
