"""CNA Hex Map Data Integrity Checker.

Validates hex map data files in cna/data/maps/ for:
  - Symmetric adjacency (if A neighbors B, B must neighbor A)
  - Valid road/rail connections between adjacent hexes only
  - Legal terrain types
  - No orphan hexes (disconnected from the main map graph)
  - Simple ASCII visualization for spot-checking

Hex data format (JSON):
    {
        "hexes": {
            "0101": {
                "terrain": "desert",
                "adjacency": ["0102", "0201", "0202"],
                "roads": ["0102"],
                "rails": []
            },
            ...
        }
    }

Usage:
    python scripts/validate_map.py                       # Check all map files
    python scripts/validate_map.py --file path/to/map.json
    python scripts/validate_map.py --visualize           # Show ASCII map
"""

import argparse
import io
import json
import os
import sys
from collections import deque

# Force UTF-8 output on Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAPS_DIR = os.path.join(PROJECT_ROOT, "cna", "data", "maps")

# Legal terrain types for CNA (Case 8.1 terrain effects)
LEGAL_TERRAIN = {
    "desert",       # Open desert (default)
    "rough",        # Rough terrain
    "sand_sea",     # Sand sea / erg
    "escarpment",   # Escarpment hex
    "coastal",      # Coastal hex
    "sea",          # Full sea hex
    "salt_marsh",   # Salt marsh / sebkha
    "oasis",        # Oasis hex
    "town",         # Town hex
    "city",         # Major city
    "port",         # Port hex
    "airfield",     # Airfield hex
    "pass",         # Mountain pass
    "ridge",        # Ridge hex
    "wadi",         # Wadi hex
    "road",         # Road hex (terrain overlay)
    "trail",        # Trail hex
    "impassable",   # Impassable terrain
}


class MapValidator:
    """Validates a single hex map data file."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.data: dict = {}
        self.hexes: dict = {}
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def load(self) -> bool:
        """Load and parse the map file. Returns True on success."""
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
        except json.JSONDecodeError as e:
            self.errors.append(f"Invalid JSON: {e}")
            return False
        except OSError as e:
            self.errors.append(f"Cannot read file: {e}")
            return False

        self.hexes = self.data.get("hexes", {})
        if not self.hexes:
            self.warnings.append("Map file contains no hex data.")
            return False
        return True

    def check_terrain_types(self):
        """Verify all terrain types are legal (Case 8.1)."""
        for hex_id, hex_data in self.hexes.items():
            terrain = hex_data.get("terrain", "")
            if terrain not in LEGAL_TERRAIN:
                self.errors.append(
                    f"Hex {hex_id}: illegal terrain type '{terrain}'. "
                    f"Legal types: {', '.join(sorted(LEGAL_TERRAIN))}"
                )

    def check_symmetric_adjacency(self):
        """If A lists B as neighbor, B must list A (Case 8.0 hex geometry)."""
        for hex_id, hex_data in self.hexes.items():
            for neighbor in hex_data.get("adjacency", []):
                if neighbor not in self.hexes:
                    self.errors.append(
                        f"Hex {hex_id}: neighbor '{neighbor}' does not exist in map."
                    )
                    continue
                neighbor_adj = self.hexes[neighbor].get("adjacency", [])
                if hex_id not in neighbor_adj:
                    self.errors.append(
                        f"Asymmetric adjacency: {hex_id} -> {neighbor}, "
                        f"but {neighbor} does not list {hex_id}."
                    )

    def check_connections(self):
        """Road/rail connections must be between adjacent hexes (Case 55.0 rails, Case 8.3 roads)."""
        for hex_id, hex_data in self.hexes.items():
            adj = set(hex_data.get("adjacency", []))

            for road_target in hex_data.get("roads", []):
                if road_target not in adj:
                    self.errors.append(
                        f"Hex {hex_id}: road to '{road_target}' but they are not adjacent."
                    )
                # Check symmetry: if A has road to B, B should have road to A
                if road_target in self.hexes:
                    other_roads = self.hexes[road_target].get("roads", [])
                    if hex_id not in other_roads:
                        self.errors.append(
                            f"Asymmetric road: {hex_id} -> {road_target}, "
                            f"but {road_target} does not have road back to {hex_id}."
                        )

            for rail_target in hex_data.get("rails", []):
                if rail_target not in adj:
                    self.errors.append(
                        f"Hex {hex_id}: rail to '{rail_target}' but they are not adjacent."
                    )
                if rail_target in self.hexes:
                    other_rails = self.hexes[rail_target].get("rails", [])
                    if hex_id not in other_rails:
                        self.errors.append(
                            f"Asymmetric rail: {hex_id} -> {rail_target}, "
                            f"but {rail_target} does not have rail back to {hex_id}."
                        )

    def check_connectivity(self):
        """Check for orphan hexes disconnected from the main map graph."""
        if len(self.hexes) <= 1:
            return

        # BFS from the first hex
        all_ids = set(self.hexes.keys())
        start = next(iter(all_ids))
        visited = set()
        queue = deque([start])
        visited.add(start)

        while queue:
            current = queue.popleft()
            for neighbor in self.hexes.get(current, {}).get("adjacency", []):
                if neighbor in all_ids and neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        orphans = all_ids - visited
        if orphans:
            orphan_list = sorted(orphans)[:20]
            extra = f" (and {len(orphans) - 20} more)" if len(orphans) > 20 else ""
            self.errors.append(
                f"Disconnected hexes found ({len(orphans)} orphans): "
                f"{', '.join(orphan_list)}{extra}"
            )

    def validate(self) -> bool:
        """Run all validation checks. Returns True if no errors."""
        if not self.load():
            return len(self.errors) == 0

        self.check_terrain_types()
        self.check_symmetric_adjacency()
        self.check_connections()
        self.check_connectivity()

        return len(self.errors) == 0

    def ascii_visualization(self, max_cols: int = 40, max_rows: int = 30) -> str:
        """Generate a simple ASCII visualization of the hex map.

        Hexes are placed based on their column/row ID (e.g., 0101 = col 01, row 01).
        """
        if not self.hexes:
            return "(No hex data to visualize)"

        # Parse hex IDs into (col, row) tuples
        positions: dict[str, tuple[int, int]] = {}
        for hex_id in self.hexes:
            try:
                if len(hex_id) == 4:
                    col = int(hex_id[:2])
                    row = int(hex_id[2:])
                elif len(hex_id) == 6:
                    col = int(hex_id[:3])
                    row = int(hex_id[3:])
                else:
                    continue
                positions[hex_id] = (col, row)
            except ValueError:
                continue

        if not positions:
            return "(Cannot parse hex IDs for visualization)"

        min_col = min(c for c, r in positions.values())
        min_row = min(r for c, r in positions.values())
        max_col_val = min(max(c for c, r in positions.values()), min_col + max_cols - 1)
        max_row_val = min(max(r for c, r in positions.values()), min_row + max_rows - 1)

        # Terrain abbreviations
        abbrev = {
            "desert": "..", "rough": "RG", "sand_sea": "SS", "escarpment": "ES",
            "coastal": "CO", "sea": "~~", "salt_marsh": "SM", "oasis": "OA",
            "town": "TW", "city": "CT", "port": "PT", "airfield": "AF",
            "pass": "PS", "ridge": "RI", "wadi": "WD", "road": "RD",
            "trail": "TR", "impassable": "XX",
        }

        lines = []
        lines.append(f"  Map: {self.filename} ({len(self.hexes)} hexes)")
        lines.append(f"  Showing cols {min_col}-{max_col_val}, rows {min_row}-{max_row_val}")
        lines.append("")

        # Column header
        header = "     "
        for c in range(min_col, max_col_val + 1):
            header += f"{c:>4}"
        lines.append(header)
        lines.append("     " + "----" * (max_col_val - min_col + 1))

        # Build a lookup for fast access
        pos_lookup: dict[tuple[int, int], str] = {}
        for hex_id, (c, r) in positions.items():
            pos_lookup[(c, r)] = hex_id

        for r in range(min_row, max_row_val + 1):
            row_str = f"{r:>3} |"
            for c in range(min_col, max_col_val + 1):
                hex_id = pos_lookup.get((c, r))
                if hex_id and hex_id in self.hexes:
                    terrain = self.hexes[hex_id].get("terrain", "??")
                    sym = abbrev.get(terrain, "??")
                    row_str += f" {sym} "
                else:
                    row_str += "    "
            lines.append(row_str)

        lines.append("")
        lines.append("  Legend: ..=desert RG=rough SS=sand_sea ES=escarpment CO=coastal")
        lines.append("          ~~=sea SM=salt_marsh OA=oasis TW=town CT=city PT=port")
        lines.append("          AF=airfield PS=pass RI=ridge WD=wadi RD=road XX=impassable")

        return '\n'.join(lines)


def find_map_files(maps_dir: str) -> list[str]:
    """Find all JSON map data files."""
    if not os.path.isdir(maps_dir):
        return []
    files = []
    for fname in sorted(os.listdir(maps_dir)):
        if fname.endswith('.json'):
            files.append(os.path.join(maps_dir, fname))
    return files


def main():
    parser = argparse.ArgumentParser(description="CNA Hex Map Data Integrity Checker")
    parser.add_argument('--file', '-f', help="Validate a specific map file")
    parser.add_argument('--visualize', '-V', action='store_true',
                        help="Show ASCII visualization of each map")
    args = parser.parse_args()

    print()
    print("=" * 60)
    print("  CNA Hex Map Validator")
    print("=" * 60)
    print()

    if args.file:
        files = [args.file]
    else:
        files = find_map_files(MAPS_DIR)

    if not files:
        print("  No map data files found.")
        print()
        if not args.file:
            print(f"  Expected location: {MAPS_DIR}/")
            print("  Map files should be JSON with a 'hexes' key.")
            print()
            print("  Example hex data format:")
            print('  {')
            print('    "hexes": {')
            print('      "0101": {')
            print('        "terrain": "desert",')
            print('        "adjacency": ["0102", "0201"],')
            print('        "roads": [],')
            print('        "rails": []')
            print('      }')
            print('    }')
            print('  }')
        print()
        sys.exit(0)

    total_errors = 0
    total_warnings = 0

    for filepath in files:
        validator = MapValidator(filepath)
        is_valid = validator.validate()

        status = "PASS" if is_valid else "FAIL"
        marker = "  " if is_valid else "!!"

        print(f"  {marker} [{status}] {validator.filename}")

        for w in validator.warnings:
            print(f"       WARN: {w}")
            total_warnings += 1

        for e in validator.errors:
            print(f"       ERROR: {e}")
            total_errors += 1

        if is_valid and not validator.warnings:
            hex_count = len(validator.hexes)
            print(f"       {hex_count} hexes validated successfully.")

        if args.visualize and validator.hexes:
            print()
            print(validator.ascii_visualization())

        print()

    # Summary
    print("-" * 60)
    print(f"  Files checked: {len(files)}")
    print(f"  Errors: {total_errors}")
    print(f"  Warnings: {total_warnings}")
    if total_errors == 0:
        print("  Status: ALL CHECKS PASSED")
    else:
        print("  Status: ISSUES FOUND - see errors above")
    print()

    sys.exit(1 if total_errors > 0 else 0)


if __name__ == '__main__':
    main()
