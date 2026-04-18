"""Sections 11-15 — Combat Resolution orchestrator.

Drives the full combat sequence for one attacking hex vs one defending
hex through the four combat steps per Case 11.0:

  1. Barrage (Section 12) — artillery indirect fire.
  2. Retreat Before Assault (Section 13) — defender may retreat.
  3. Anti-Armor Fire (Section 14) — simultaneous AT fire.
  4. Close Assault (Section 15) — decisive infantry/armor assault.

This module ties together the individual combat sub-modules (barrage,
anti_armor, close_assault, retreat) into a single resolve_combat() call
that mutates GameState and returns a structured CombatReport.

Cross-references:
  - Case 5.2 III.G.3: Combat Segment within Movement & Combat Phase.
  - Case 10.31: ZoC combat requirements (mandatory attack).
  - Case 11.2: CP costs for combat participants.
  - Case 6.21: DP from CP overspend during combat.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from cna.engine.game_state import (
    GameState,
    HexCoord,
    Side,
    Unit,
    UnitType,
)
from cna.rules.capability_points import spend_cp
from cna.rules.combat.barrage import BarrageResult, resolve_barrage
from cna.rules.combat.anti_armor import (
    AntiArmorResult,
    apply_armor_damage,
    resolve_anti_armor,
)
from cna.rules.combat.close_assault import (
    AssaultDifferential,
    AssaultOutcome,
    CloseAssaultResult,
    compute_assault_differential,
    resolve_close_assault,
)
from cna.rules.combat.common import (
    CombatRole,
    actual_points,
    combat_cp_cost,
    raw_points,
)


# ---------------------------------------------------------------------------
# Combat report
# ---------------------------------------------------------------------------


@dataclass
class CombatReport:
    """Full result of a combat resolution between two hexes.

    Case 11.0 — Records outcomes from all four combat steps.
    """
    attacker_hex: HexCoord
    defender_hex: HexCoord
    attacker_side: Side
    defender_side: Side

    # Step results (None if step was skipped).
    barrage: Optional[BarrageResult] = None
    anti_armor_attacker: Optional[AntiArmorResult] = None
    anti_armor_defender: Optional[AntiArmorResult] = None
    close_assault: Optional[CloseAssaultResult] = None
    differential: Optional[AssaultDifferential] = None

    # Casualties applied.
    attacker_toe_lost: int = 0
    defender_toe_lost: int = 0
    defender_retreated: bool = False
    defender_pinned: bool = False

    # CP costs.
    attacker_cp_spent: int = 0
    defender_cp_spent: int = 0

    @property
    def summary(self) -> str:
        """One-line summary for the turn log (Case 11.0)."""
        parts = []
        if self.barrage and (self.barrage.toe_losses or self.barrage.pinned):
            parts.append(f"Barrage: {'PIN' if self.barrage.pinned else ''} "
                        f"{self.barrage.toe_losses} losses")
        if self.anti_armor_attacker and self.anti_armor_attacker.damage_points:
            parts.append(f"AA→def: {self.anti_armor_attacker.damage_points} DP")
        if self.anti_armor_defender and self.anti_armor_defender.damage_points:
            parts.append(f"AA→att: {self.anti_armor_defender.damage_points} DP")
        if self.close_assault:
            ca = self.close_assault
            parts.append(f"Assault: att -{ca.attacker_raw_losses} "
                        f"def -{ca.defender_raw_losses} "
                        f"({ca.outcome.value})")
        if self.defender_retreated:
            parts.append("Defender retreated")
        return "; ".join(parts) if parts else "No effect"


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------


def _total_barrage_actual(units: list[Unit]) -> int:
    """Sum Actual Barrage Points for all artillery units (Case 11.34)."""
    total_raw = sum(
        raw_points(u.stats.barrage_rating, u.current_toe)
        for u in units if u.stats.barrage_rating > 0
    )
    return actual_points(total_raw)


def _total_anti_armor_actual(units: list[Unit]) -> int:
    """Sum Actual Anti-Armor Points (Case 11.34)."""
    total_raw = sum(
        raw_points(u.stats.anti_armor_strength, u.current_toe)
        for u in units if u.stats.anti_armor_strength > 0
    )
    return actual_points(total_raw)


def _total_assault_raw(units: list[Unit], *, offensive: bool) -> int:
    """Sum Raw Close Assault Points (Case 11.34)."""
    rating_attr = "offensive_close_assault" if offensive else "defensive_close_assault"
    return sum(
        raw_points(getattr(u.stats, rating_attr), u.current_toe)
        for u in units if getattr(u.stats, rating_attr) > 0
    )


def _largest_org(units: list[Unit]):
    """Find the largest org-size among *units*."""
    from cna.engine.game_state import OrgSize
    order = {OrgSize.COMPANY: 0, OrgSize.BATTALION: 1,
             OrgSize.BRIGADE: 2, OrgSize.DIVISION: 3}
    best = OrgSize.COMPANY
    for u in units:
        if order.get(u.org_size, 0) > order.get(best, 0):
            best = u.org_size
    return best


def _tank_and_infantry_toe(units: list[Unit]) -> tuple[int, int]:
    """Count tank TOE vs infantry TOE for combined arms (Case 15.4)."""
    tank_toe = sum(u.current_toe for u in units
                   if u.unit_type in {UnitType.TANK, UnitType.RECCE})
    inf_toe = sum(u.current_toe for u in units
                  if u.unit_type in {UnitType.INFANTRY, UnitType.ENGINEER})
    return tank_toe, inf_toe


def _armor_units(units: list[Unit]) -> list[Unit]:
    """Units with Armor Protection > 0 (targets for anti-armor fire)."""
    return [u for u in units if u.stats.armor_protection_rating > 0]


# ---------------------------------------------------------------------------
# Combat resolution
# ---------------------------------------------------------------------------


def resolve_combat(
    state: GameState,
    attacker_hex: HexCoord,
    defender_hex: HexCoord,
    *,
    is_probe: bool = False,
) -> CombatReport:
    """Resolve full combat between two adjacent hexes.

    Case 11.0, 5.2 III.G.3 — Executes the four-step combat sequence,
    mutating unit TOE/pinned/position state as results are applied.

    Args:
        state: Game state to mutate.
        attacker_hex: Hex containing attacking (phasing) units.
        defender_hex: Hex containing defending (non-phasing) units.
        is_probe: If True, this is a Probe (Case 15.9).

    Returns:
        CombatReport with full results and casualties.
    """
    att_side = state.active_side
    def_side = state.enemy(att_side)

    attackers = [u for u in state.units_at(attacker_hex) if u.side == att_side]
    defenders = [u for u in state.units_at(defender_hex) if u.side == def_side]

    report = CombatReport(
        attacker_hex=attacker_hex,
        defender_hex=defender_hex,
        attacker_side=att_side,
        defender_side=def_side,
    )

    if not attackers or not defenders:
        return report

    # --- Step 1: Barrage (Case 12.0) ---
    barrage_pts = _total_barrage_actual(attackers)
    if barrage_pts > 0:
        report.barrage = resolve_barrage(barrage_pts, state.dice)
        if report.barrage.pinned:
            for d in defenders:
                d.pinned = True
            report.defender_pinned = True
        if report.barrage.toe_losses > 0:
            _apply_toe_losses(defenders, report.barrage.toe_losses)
            report.defender_toe_lost += report.barrage.toe_losses

    # --- Step 2: Retreat Before Assault (Case 13.0) ---
    # In the automated resolver, defenders do NOT retreat (the interactive
    # UI would ask the player). Pinned defenders can't retreat anyway.

    # --- Step 3: Anti-Armor Fire (Case 14.0) ---
    # Attacker fires at defender's armor.
    att_aa = _total_anti_armor_actual(attackers)
    def_armor = _armor_units(defenders)
    if att_aa > 0 and def_armor:
        report.anti_armor_attacker = resolve_anti_armor(att_aa, state.dice)
        if report.anti_armor_attacker.damage_points > 0:
            for armor_u in def_armor:
                lost = apply_armor_damage(
                    report.anti_armor_attacker.damage_points,
                    armor_u.stats.armor_protection_rating,
                    armor_u.current_toe,
                )
                armor_u.current_toe = max(0, armor_u.current_toe - lost)
                report.defender_toe_lost += lost

    # Defender fires at attacker's armor.
    def_aa = _total_anti_armor_actual(defenders)
    att_armor = _armor_units(attackers)
    if def_aa > 0 and att_armor:
        report.anti_armor_defender = resolve_anti_armor(def_aa, state.dice)
        if report.anti_armor_defender.damage_points > 0:
            for armor_u in att_armor:
                lost = apply_armor_damage(
                    report.anti_armor_defender.damage_points,
                    armor_u.stats.armor_protection_rating,
                    armor_u.current_toe,
                )
                armor_u.current_toe = max(0, armor_u.current_toe - lost)
                report.attacker_toe_lost += lost

    # --- Step 4: Close Assault (Case 15.0) ---
    att_raw = _total_assault_raw(attackers, offensive=True)
    def_raw = _total_assault_raw(defenders, offensive=False)

    tank_toe, inf_toe = _tank_and_infantry_toe(attackers)
    att_org = _largest_org(attackers)
    def_org = _largest_org(defenders)

    # Morale differential (Case 15.6).
    from cna.rules.morale import morale_differential
    morale_shift = morale_differential(attackers, defenders)

    report.differential = compute_assault_differential(
        att_raw, def_raw,
        morale_shift=morale_shift,
        attacker_org=att_org,
        defender_org=def_org,
        attacker_tank_toe=tank_toe,
        attacker_infantry_toe=inf_toe,
        is_probe=is_probe,
    )

    report.close_assault = resolve_close_assault(
        report.differential, att_raw, def_raw, state.dice,
    )

    # Apply Close Assault losses.
    ca = report.close_assault
    if ca.attacker_raw_losses > 0:
        att_toe_lost = _apply_raw_losses(attackers, ca.attacker_raw_losses)
        report.attacker_toe_lost += att_toe_lost
    if ca.defender_raw_losses > 0:
        def_toe_lost = _apply_raw_losses(defenders, ca.defender_raw_losses)
        report.defender_toe_lost += def_toe_lost

    # Apply retreat (Case 15.8).
    if ca.outcome == AssaultOutcome.RETREAT and ca.retreat_hexes > 0:
        report.defender_retreated = True

    # --- CP costs (Case 11.2) ---
    att_role = CombatRole.PHASING_PROBE if is_probe else CombatRole.PHASING_ASSAULT
    def_role = CombatRole.DEFENDING_PROBE if is_probe else CombatRole.DEFENDING_FULL

    # Case 11.27: if differential ≤ -4, defender pays only 1 CP.
    if report.differential and report.differential.final_differential <= -4:
        def_role = CombatRole.DEFENDING_WEAK

    att_cp = combat_cp_cost(att_role)
    def_cp = combat_cp_cost(def_role)
    report.attacker_cp_spent = att_cp
    report.defender_cp_spent = def_cp

    for u in attackers:
        spend_cp(u, att_cp)
    for u in defenders:
        spend_cp(u, def_cp)

    return report


# ---------------------------------------------------------------------------
# Loss application helpers
# ---------------------------------------------------------------------------


def _apply_toe_losses(units: list[Unit], losses: int) -> None:
    """Spread TOE losses across units (barrage/direct losses)."""
    remaining = losses
    for u in units:
        if remaining <= 0:
            break
        take = min(remaining, u.current_toe)
        u.current_toe -= take
        remaining -= take


def _apply_raw_losses(units: list[Unit], raw_losses: int) -> int:
    """Convert raw losses to TOE losses and apply.

    Case 15.8 — Raw losses are distributed across units. Each unit
    loses TOE proportional to its share of the total raw strength.
    Returns total TOE actually lost.
    """
    total_toe = sum(u.current_toe for u in units)
    if total_toe <= 0:
        return 0
    # Convert raw losses to approximate TOE losses (raw ÷ 10, rounded).
    toe_losses = max(1, round(raw_losses / 10)) if raw_losses > 0 else 0
    toe_losses = min(toe_losses, total_toe)
    _apply_toe_losses(units, toe_losses)
    return toe_losses
