"""Layer 4 -- Basic AI Opponent

A heuristic-based AI that plays one side of the CNA land game.
Uses simple distance-based evaluation to decide movement and combat:
  - Moves toward nearest enemies or objective hexes
  - Attacks when strength ratio is favorable
  - Retreats when outnumbered
  - Respects all movement and combat rules from Layers 1-3

This is the foundational AI; more sophisticated strategies can be
layered on top via the strategy/ subpackage.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from cna.engine.dice import DiceRoller
from cna.engine.errors import RuleViolationError
from cna.engine.game_state import GameState, HexCoord, Side, Unit
from cna.engine.hex_map import distance, neighbors
from cna.rules.combat.common import (
    defensive_assault_actual,
    offensive_assault_actual,
)
from cna.rules.combat.resolver import resolve_combat
from cna.rules.land_movement import move_unit

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def nearest_enemy(state: GameState, unit: Unit) -> HexCoord | None:
    """Layer 4 -- Find the closest enemy unit to the given unit.

    Scans all enemy units on the map and returns the hex coordinate
    of the nearest one (by hex distance). Returns None if there are
    no enemy units on the map.

    Ties are broken by preferring the enemy at lower column, then lower row,
    for deterministic behavior.
    """
    if unit.position is None:
        return None

    enemies = [u for u in state.units.values() if u.side != unit.side and u.position is not None]
    if not enemies:
        return None

    best_dist = None
    best_pos = None
    for enemy in enemies:
        if enemy.position is None:
            continue
        d = distance(unit.position, enemy.position)
        if best_dist is None or d < best_dist or (
            d == best_dist and (enemy.position.col, enemy.position.row)
            < (best_pos.col, best_pos.row)
        ):
            best_dist = d
            best_pos = enemy.position

    return best_pos


def strength_ratio(state: GameState, attacker_hex: HexCoord,
                   defender_hex: HexCoord, side: Side) -> float:
    """Layer 4 -- Calculate the strength ratio for a potential attack.

    Returns attacker_strength / defender_strength. If defender strength
    is zero, returns a large number (99.0) indicating overwhelming advantage.
    If attacker strength is zero, returns 0.0.
    """
    defending_side = Side.AXIS if side == Side.ALLIED else Side.ALLIED
    att = offensive_assault_actual(state, attacker_hex, side)
    defn = defensive_assault_actual(state, defender_hex, defending_side)

    if att == 0.0:
        return 0.0
    if defn == 0.0:
        return 99.0
    return att / defn


def best_move_toward(state: GameState, unit: Unit,
                     target: HexCoord) -> HexCoord | None:
    """Layer 4 -- Find the best adjacent hex that moves toward the target.

    Examines all six neighbors of the unit's current position and returns
    the one that is closest to the target (by hex distance), provided the
    move is legal (no enemy occupation, sufficient CP). Returns None if
    no legal move gets closer to the target, or if the unit is already
    at the target.
    """
    if unit.position is None or unit.position == target:
        return None

    current_dist = distance(unit.position, target)
    best_hex = None
    best_dist = current_dist  # Only consider moves that get closer

    for neighbor in neighbors(unit.position):
        d = distance(neighbor, target)
        if d >= best_dist:
            continue

        # Check legality: no enemy units, sufficient CP
        enemy_in_hex = [u for u in state.units_at(neighbor) if u.side != unit.side]
        if enemy_in_hex:
            continue

        # Check CP cost (simplified: 1 CP per hex)
        from cna.rules.land_movement import terrain_cp_cost
        cost = terrain_cp_cost(unit, unit.position, neighbor, state)
        if unit.capability_points < cost:
            continue

        if d < best_dist or (d == best_dist and best_hex is not None
                             and (neighbor.col, neighbor.row)
                             < (best_hex.col, best_hex.row)):
            best_dist = d
            best_hex = neighbor

    return best_hex


def _nearest_supply_source(state: GameState, unit: Unit) -> HexCoord | None:
    """Layer 4 -- Find the nearest friendly supply source hex.

    Used to determine retreat direction when the AI is outnumbered.
    Falls back to nearest friendly unit if no supply sources are defined.
    """
    if unit.position is None:
        return None

    sources = state.supply_sources.get(unit.side, [])
    if sources:
        return min(sources, key=lambda h: distance(unit.position, h))

    # Fallback: retreat toward nearest friendly unit
    friendlies = [u for u in state.friendly_units(unit.side)
                  if u.unit_id != unit.unit_id and u.position is not None]
    if friendlies:
        nearest = min(friendlies, key=lambda u: distance(unit.position, u.position))
        return nearest.position

    return None


def _is_adjacent_to_enemy(state: GameState, unit: Unit) -> bool:
    """Check if the unit is adjacent to any enemy unit."""
    if unit.position is None:
        return False
    adj = neighbors(unit.position)
    for enemy in [u for u in state.units.values() if u.side != unit.side and u.position is not None]:
        if enemy.position in adj:
            return True
    return False


def _adjacent_enemy_hexes(state: GameState, position: HexCoord,
                          side: Side) -> list[HexCoord]:
    """Return hexes adjacent to position that contain enemy units."""
    enemy_side = Side.AXIS if side == Side.ALLIED else Side.ALLIED
    adj = neighbors(position)
    result = []
    seen = set()
    for enemy in [u for u in state.units.values() if u.side != side and u.position is not None]:
        if enemy.position in adj and enemy.position not in seen:
            seen.add(enemy.position)
            result.append(enemy.position)
    return result


def _total_adjacent_enemy_strength(state: GameState, unit: Unit) -> float:
    """Sum the attack strength of all enemy units adjacent to this unit."""
    if unit.position is None:
        return 0.0
    enemy_hexes = _adjacent_enemy_hexes(state, unit.position, unit.side)
    enemy_side = Side.AXIS if unit.side == Side.ALLIED else Side.ALLIED
    total = 0.0
    for eh in enemy_hexes:
        total += offensive_assault_actual(state, eh, enemy_side)
    return total


def _choose_objective_target(state: GameState, unit: Unit) -> HexCoord | None:
    """Layer 4 -- Pick the nearest objective hex not already held by friendlies.

    Returns None if no objective hexes exist or all are already held.
    Considers objectives for both sides (attack enemy objectives, defend own).
    """
    if unit.position is None:
        return None

    # Gather all objective hexes (both sides)
    all_objectives: list[HexCoord] = []
    for hexes in state.objective_hexes.values():
        all_objectives.extend(hexes)

    if not all_objectives:
        return None

    # Filter out objectives already securely held by friendlies
    targets = []
    for obj in all_objectives:
        units_here = state.units_at(obj)
        friendly_here = [u for u in units_here if u.side == unit.side]
        if not friendly_here:
            targets.append(obj)

    if not targets:
        return None

    return min(targets, key=lambda h: distance(unit.position, h))


# ---------------------------------------------------------------------------
# Main AI class
# ---------------------------------------------------------------------------

@dataclass
class BasicAI:
    """Layer 4 -- A basic heuristic AI opponent for CNA.

    Plays one side using simple distance and strength-ratio evaluation.
    Executes movement and combat phases sequentially, logging all actions.

    Attributes:
        side: Which side this AI controls.
        dice: Dice roller for combat resolution (seeded for reproducibility).
    """

    side: Side
    dice: DiceRoller = field(default_factory=lambda: DiceRoller(seed=42))

    def __init__(self, side: Side, state: GameState):
        """Layer 4 -- Initialize the AI for a given side.

        Args:
            side: Which side the AI will play.
            state: Initial game state (used for setup analysis).
        """
        self.side = side
        self.dice = DiceRoller(seed=42)

    def take_turn(self, state: GameState) -> list[str]:
        """Layer 4 -- Execute all actions for one Movement and Combat phase.

        Performs the movement phase first (moving all friendly units),
        then the combat phase (resolving attacks where favorable).

        Returns a list of human-readable action descriptions for logging.
        """
        actions: list[str] = []
        actions.extend(self._movement_phase(state))
        actions.extend(self._combat_phase(state))
        return actions

    def _movement_phase(self, state: GameState) -> list[str]:
        """Layer 4 -- Execute the movement phase for all friendly units.

        Units are processed in order of distance to nearest enemy
        (closest first), so threatened units act before rear-echelon ones.

        Movement decision tree per unit:
        1. Adjacent to weaker enemy -> stay (will attack in combat phase)
        2. Not adjacent to enemy -> move toward nearest enemy or objective
        3. Outnumbered by adjacent enemies -> retreat toward supply/friendlies
        """
        actions: list[str] = []
        friendlies = state.friendly_units(self.side)

        # Sort by distance to nearest enemy (closest first)
        def sort_key(u: Unit) -> tuple[int, int, int]:
            ne = nearest_enemy(state, u)
            d = distance(u.position, ne) if ne and u.position else 999
            return (d, u.position.col if u.position else 999,
                    u.position.row if u.position else 999)

        friendlies.sort(key=sort_key)

        for unit in friendlies:
            if unit.position is None:
                continue
            if unit.capability_points <= 0:
                continue

            adjacent_to_enemy = _is_adjacent_to_enemy(state, unit)

            if adjacent_to_enemy:
                # Check if we're outnumbered
                my_defense = unit.defense_strength
                enemy_attack = _total_adjacent_enemy_strength(state, unit)

                if enemy_attack > my_defense * 2:
                    # Outnumbered: retreat toward supply/friendlies
                    retreat_target = _nearest_supply_source(state, unit)
                    if retreat_target:
                        dest = best_move_toward(state, unit, retreat_target)
                        if dest:
                            try:
                                move_unit(unit, dest, state)
                                actions.append(
                                    f"RETREAT {unit.name} from {unit.position} "
                                    f"toward supply via {dest}"
                                )
                                # Continue moving if CP allows
                                self._continue_moving(state, unit, retreat_target,
                                                      actions, "RETREAT")
                            except RuleViolationError as e:
                                logger.debug("Retreat blocked for %s: %s",
                                             unit.name, e)
                    # else: no retreat path, stay and fight
                # else: stay adjacent, will attack in combat phase
                continue

            # Not adjacent to enemy: move toward target
            target = self._pick_movement_target(state, unit)
            if target is None:
                continue

            dest = best_move_toward(state, unit, target)
            if dest:
                try:
                    move_unit(unit, dest, state)
                    actions.append(
                        f"MOVE {unit.name} to {dest} (toward {target})"
                    )
                    # Continue moving if CP allows
                    self._continue_moving(state, unit, target, actions, "MOVE")
                except RuleViolationError as e:
                    logger.debug("Move blocked for %s: %s", unit.name, e)

        return actions

    def _continue_moving(self, state: GameState, unit: Unit,
                         target: HexCoord, actions: list[str],
                         action_prefix: str) -> None:
        """Keep moving the unit toward the target while CP allows.

        Stops if the unit becomes adjacent to an enemy (to preserve
        the option to attack in the combat phase).
        """
        while unit.capability_points > 0:
            if _is_adjacent_to_enemy(state, unit):
                break
            dest = best_move_toward(state, unit, target)
            if dest is None:
                break
            try:
                move_unit(unit, dest, state)
                actions.append(
                    f"{action_prefix} {unit.name} to {dest} (toward {target})"
                )
            except RuleViolationError:
                break

    def _pick_movement_target(self, state: GameState,
                              unit: Unit) -> HexCoord | None:
        """Layer 4 -- Decide where a unit should move.

        Priority:
        1. Nearest uncontrolled objective hex
        2. Nearest enemy unit
        """
        # First, check for nearby objectives
        obj_target = _choose_objective_target(state, unit)
        enemy_target = nearest_enemy(state, unit)

        if obj_target and enemy_target and unit.position:
            # Prefer whichever is closer, with bias toward objectives
            obj_dist = distance(unit.position, obj_target)
            enemy_dist = distance(unit.position, enemy_target)
            if obj_dist <= enemy_dist + 2:
                return obj_target
            return enemy_target

        return obj_target or enemy_target

    def _combat_phase(self, state: GameState) -> list[str]:
        """Layer 4 -- Execute the combat phase.

        For each friendly hex adjacent to enemies, evaluate whether to
        attack based on the strength ratio:
        - Ratio >= 2.0: full assault
        - Ratio >= 1.0: probe
        - Ratio < 1.0: skip (don't attack)

        Each defender hex is only attacked once per phase.
        """
        actions: list[str] = []
        attacked_hexes: set[HexCoord] = set()

        # Find all friendly hexes that are adjacent to enemies
        attacker_hexes: list[HexCoord] = []
        seen: set[HexCoord] = set()
        for unit in state.friendly_units(self.side):
            if unit.position is None or unit.position in seen:
                continue
            if _is_adjacent_to_enemy(state, unit):
                seen.add(unit.position)
                attacker_hexes.append(unit.position)

        # Sort attacker hexes for deterministic processing
        attacker_hexes.sort(key=lambda h: (h.col, h.row))

        for att_hex in attacker_hexes:
            # Find adjacent enemy hexes
            enemy_hexes = _adjacent_enemy_hexes(state, att_hex, self.side)

            # Sort by weakest defender first (prioritize favorable attacks)
            defending_side = (Side.AXIS if self.side == Side.ALLIED
                              else Side.ALLIED)
            enemy_hexes.sort(
                key=lambda eh: defensive_assault_actual(state, eh, defending_side)
            )

            for def_hex in enemy_hexes:
                if def_hex in attacked_hexes:
                    continue

                ratio = strength_ratio(state, att_hex, def_hex, self.side)

                if ratio < 1.0:
                    actions.append(
                        f"SKIP combat at {att_hex} vs {def_hex} "
                        f"(unfavorable ratio {ratio:.1f}:1)"
                    )
                    continue

                is_probe = ratio < 2.0
                label = "PROBE" if is_probe else "ASSAULT"

                try:
                    report = resolve_combat(
                        state, att_hex, def_hex, is_probe=is_probe,
                    )
                    attacked_hexes.add(def_hex)
                    actions.append(
                        f"{label} {att_hex} vs {def_hex} "
                        f"(ratio {ratio:.1f}:1, "
                        f"att lost {report.attacker_toe_lost}, "
                        f"def lost {report.defender_toe_lost})"
                    )
                except Exception as exc:
                    actions.append(f"COMBAT ERROR at {att_hex}: {exc}")

        return actions
