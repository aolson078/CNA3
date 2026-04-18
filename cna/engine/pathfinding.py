"""Section 8.0 — A* pathfinding and Dijkstra reachability for multi-hex movement.

Implements pathfinding support for Cases 8.11-8.14, 8.31 (terrain costs),
8.32 (terrain prohibition), and 10.23 (ZoC stops movement).

This module provides:
  - find_path(): A* search for the cheapest CP-cost path between two hexes.
  - find_reachable(): Dijkstra flood-fill returning all hexes within a CP budget.
  - path_cp_cost(): Calculate total CP cost for a given hex path.

Movement restrictions enforced:
  - Terrain prohibition (Case 8.32): hexes that can_enter() returns False are skipped.
  - Enemy-occupied hexes (Case 8.13): cannot enter hexes with enemy units.
  - Enemy ZoC (Case 10.23): unit must stop upon entering an enemy ZoC hex;
    pathfinding will not route *through* a ZoC hex (it may end at one).

Cross-references:
  - cna/engine/hex_map.py: HexMap, neighbors, is_adjacent, distance
  - cna/rules/land_movement.py: terrain_cp_cost, can_enter, is_motorized
  - cna/rules/zones_of_control.py: is_enemy_zoc
  - cna/rules/capability_points.py: effective_cpa
"""

from __future__ import annotations

import heapq
from typing import Optional

from cna.engine.game_state import GameState, HexCoord, Unit
from cna.engine.hex_map import HexMap, distance, is_adjacent
from cna.rules.land_movement import can_enter, terrain_cp_cost
from cna.rules.zones_of_control import is_enemy_zoc


def find_path(
    state: GameState,
    unit: Unit,
    start: HexCoord,
    goal: HexCoord,
) -> Optional[list[HexCoord]]:
    """Find the cheapest CP-cost path from *start* to *goal* for *unit*.

    Case 8.11, Case 8.31 — A* search using terrain_cp_cost as the edge
    weight.  The heuristic is hex distance (admissible because the
    minimum terrain cost is 1 CP per hex).

    Restrictions enforced:
      - Case 8.32: terrain prohibition (can_enter returns False -> skip).
      - Case 8.13: cannot enter enemy-occupied hexes.
      - Case 10.23: enemy ZoC hexes stop movement; the path may *end* at
        a ZoC hex but cannot pass *through* one.

    Args:
        state: Current game state (map, units).
        unit: The unit being moved.
        start: Starting hex coordinate.
        goal: Destination hex coordinate.

    Returns:
        Ordered list of HexCoords from *start* to *goal* (inclusive),
        or None if no valid path exists.
    """
    hex_map = HexMap(state.map)

    if start not in hex_map or goal not in hex_map:
        return None

    if start == goal:
        return [start]

    enemy_side = state.enemy(unit.side)

    # Priority queue entries: (f_score, tie_breaker, coord)
    # tie_breaker ensures stable ordering when f_scores are equal.
    open_set: list[tuple[int, int, HexCoord]] = []
    counter = 0
    heapq.heappush(open_set, (distance(start, goal), counter, start))
    counter += 1

    came_from: dict[HexCoord, HexCoord] = {}
    g_score: dict[HexCoord, int] = {start: 0}

    while open_set:
        _, _, current = heapq.heappop(open_set)

        if current == goal:
            return _reconstruct_path(came_from, current)

        # Case 10.23: if the current hex is in enemy ZoC (and it is not
        # the start hex), the unit must stop — do not expand further.
        if current != start and is_enemy_zoc(state, current, unit.side):
            continue

        current_g = g_score[current]

        for neighbor in hex_map.neighbors_in_bounds(current):
            # Case 8.13: cannot enter enemy-occupied hexes.
            enemy_units = [
                u for u in state.units_at(neighbor) if u.side == enemy_side
            ]
            if enemy_units:
                continue

            # Case 8.32: terrain prohibition.
            neighbor_hex = hex_map.require(neighbor)
            on_road = hex_map.has_road(current, neighbor)
            on_track = hex_map.has_track(current, neighbor)
            if not can_enter(
                neighbor_hex.terrain, unit, on_road=on_road, on_track=on_track
            ):
                continue

            # Edge cost = terrain CP cost to enter the neighbor.
            cost = terrain_cp_cost(
                neighbor_hex.terrain, unit, on_road=on_road, on_track=on_track
            )
            tentative_g = current_g + cost

            if tentative_g < g_score.get(neighbor, float("inf")):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f = tentative_g + distance(neighbor, goal)
                heapq.heappush(open_set, (f, counter, neighbor))
                counter += 1

    return None


def find_reachable(
    state: GameState,
    unit: Unit,
    max_cp: int,
) -> dict[HexCoord, int]:
    """Return all hexes reachable by *unit* within *max_cp* capability points.

    Case 8.11, Case 8.31 — Dijkstra flood-fill from the unit's current
    position.  Returns a dict mapping each reachable HexCoord to the
    minimum CP cost to reach it.  The unit's starting hex is included
    with cost 0.

    Same movement restrictions as find_path():
      - Case 8.32: terrain prohibition.
      - Case 8.13: enemy-occupied hexes blocked.
      - Case 10.23: enemy ZoC hexes are reachable (included in output)
        but are not expanded further (the unit must stop there).

    Args:
        state: Current game state.
        unit: The unit being considered.
        max_cp: Maximum CP budget for the flood-fill.

    Returns:
        dict mapping reachable HexCoords to their minimum CP cost.
    """
    if unit.position is None:
        return {}

    hex_map = HexMap(state.map)
    start = unit.position

    if start not in hex_map:
        return {}

    enemy_side = state.enemy(unit.side)

    # Dijkstra: (cost, tie_breaker, coord)
    dist: dict[HexCoord, int] = {start: 0}
    pq: list[tuple[int, int, HexCoord]] = [(0, 0, start)]
    counter = 1

    while pq:
        cost, _, current = heapq.heappop(pq)

        if cost > dist.get(current, float("inf")):
            continue

        # Case 10.23: ZoC hex is reachable but not expanded (unit stops).
        if current != start and is_enemy_zoc(state, current, unit.side):
            continue

        for neighbor in hex_map.neighbors_in_bounds(current):
            # Case 8.13: cannot enter enemy-occupied hexes.
            enemy_units = [
                u for u in state.units_at(neighbor) if u.side == enemy_side
            ]
            if enemy_units:
                continue

            # Case 8.32: terrain prohibition.
            neighbor_hex = hex_map.require(neighbor)
            on_road = hex_map.has_road(current, neighbor)
            on_track = hex_map.has_track(current, neighbor)
            if not can_enter(
                neighbor_hex.terrain, unit, on_road=on_road, on_track=on_track
            ):
                continue

            step_cost = terrain_cp_cost(
                neighbor_hex.terrain, unit, on_road=on_road, on_track=on_track
            )
            new_cost = cost + step_cost

            if new_cost > max_cp:
                continue

            if new_cost < dist.get(neighbor, float("inf")):
                dist[neighbor] = new_cost
                heapq.heappush(pq, (new_cost, counter, neighbor))
                counter += 1

    return dist


def path_cp_cost(
    state: GameState,
    unit: Unit,
    path: list[HexCoord],
) -> int:
    """Calculate the total CP cost for *unit* to traverse *path*.

    Case 8.31 — Sums terrain_cp_cost for each hex entered (all hexes
    in *path* after the first, which is the starting position).

    Args:
        state: Current game state (for road/track lookups).
        unit: The unit being moved.
        path: Ordered list of HexCoords (start to destination, inclusive).

    Returns:
        Total CP cost. Raises ValueError if path contains non-adjacent
        hexes or prohibited terrain.
    """
    if len(path) <= 1:
        return 0

    hex_map = HexMap(state.map)
    total = 0

    for i in range(1, len(path)):
        prev, cur = path[i - 1], path[i]
        if not is_adjacent(prev, cur):
            raise ValueError(
                f"Non-adjacent hexes in path: {prev} -> {cur} (Case 8.13)"
            )
        mh = hex_map.get(cur)
        if mh is None:
            raise ValueError(f"Hex {cur} is off-map")

        on_road = hex_map.has_road(prev, cur)
        on_track = hex_map.has_track(prev, cur)
        cost = terrain_cp_cost(mh.terrain, unit, on_road=on_road, on_track=on_track)

        if cost < 0:
            raise ValueError(
                f"Terrain {mh.terrain.value} at {cur} is prohibited "
                f"for unit {unit.id} (Case 8.32)"
            )
        total += cost

    return total


def _reconstruct_path(
    came_from: dict[HexCoord, HexCoord],
    current: HexCoord,
) -> list[HexCoord]:
    """Reconstruct A* path by walking the came_from chain backwards."""
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path
