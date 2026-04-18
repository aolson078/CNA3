"""Section 11.0 — Combat System common calculations.

Implements Cases 11.1-11.38: combat characteristics, CP expenditure
rules, and the Actual Strength formula.

The combat strength formula (Case 11.32 correction):
  Raw Points = Combat Rating × TOE Strength Points used
  Actual Points = Raw Points ÷ 10 (rounded to nearest whole number)

Exception: AA Points are not divided by 10 (Case 11.37).
Exception: Vulnerability and Armor Protection are not multiplied by
TOE (Case 11.38).

CP expenditure for combat (Cases 11.21-11.27):
  - Phasing attacker: 5 CP (full assault), 2 CP (probe)
  - Non-phasing defender: 3 CP (full assault), 2 CP (probe),
    1 CP (if assault differential is -4 or worse for attacker)

Cross-references:
  - Case 3.5: Unit characteristics (ratings).
  - Case 6.0: CP system — combat costs CP and may earn DP.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from cna.engine.game_state import Unit, UnitStats


# ---------------------------------------------------------------------------
# Strength calculations (Case 11.3)
# ---------------------------------------------------------------------------


def raw_points(rating: int, toe_used: int) -> int:
    """Raw combat points = Rating × TOE Strength used (Case 11.32)."""
    return rating * toe_used


def actual_points(raw: int) -> int:
    """Actual Points = Raw ÷ 10, rounded to nearest whole number.

    Case 11.32 — 11.4 → 11, 11.5 → 12.
    Case 11.33 — Less than 5 Raw Points → 0 Actual.
    """
    if raw < 5:
        return 0
    return round(raw / 10)


def barrage_actual(unit: Unit, toe_used: int | None = None) -> int:
    """Actual Barrage Points for *unit* (Case 11.11, 11.32).

    Case 11.11 — Only artillery units possess a Barrage Rating.
    """
    toe = toe_used if toe_used is not None else unit.current_toe
    return actual_points(raw_points(unit.stats.barrage_rating, toe))


def anti_armor_actual(unit: Unit, toe_used: int | None = None) -> int:
    """Actual Anti-Armor Points for *unit* (Case 11.13, 11.32)."""
    toe = toe_used if toe_used is not None else unit.current_toe
    return actual_points(raw_points(unit.stats.anti_armor_strength, toe))


def offensive_assault_actual(unit: Unit, toe_used: int | None = None) -> int:
    """Actual Offensive Close Assault Points (Case 11.15, 11.32)."""
    toe = toe_used if toe_used is not None else unit.current_toe
    return actual_points(raw_points(unit.stats.offensive_close_assault, toe))


def defensive_assault_actual(unit: Unit, toe_used: int | None = None) -> int:
    """Actual Defensive Close Assault Points (Case 11.15, 11.32)."""
    toe = toe_used if toe_used is not None else unit.current_toe
    return actual_points(raw_points(unit.stats.defensive_close_assault, toe))


def aa_actual(unit: Unit, toe_used: int | None = None) -> int:
    """Actual AA Points (Case 11.37 — not divided by 10)."""
    toe = toe_used if toe_used is not None else unit.current_toe
    return raw_points(unit.stats.anti_aircraft_rating, toe)


# ---------------------------------------------------------------------------
# CP costs for combat (Case 11.2)
# ---------------------------------------------------------------------------


class CombatRole(str, Enum):
    """Role a unit plays in combat, determining CP cost (Cases 11.21-11.27)."""
    PHASING_ASSAULT = "phasing_assault"     # 5 CP (Case 11.22)
    PHASING_PROBE = "phasing_probe"         # 2 CP (Case 11.23)
    PHASING_BARRAGE_ONLY = "phasing_barrage" # 5 CP (Case 11.22)
    DEFENDING_FULL = "defending_full"        # 3 CP (Case 11.21)
    DEFENDING_PROBE = "defending_probe"      # 2 CP (Case 11.21)
    DEFENDING_WEAK = "defending_weak"        # 1 CP (Case 11.27)
    UNDERGOING_BARRAGE = "undergoing_barrage" # 3 CP (Case 11.23)


# Case 11.21-11.27 — CP costs per combat role.
COMBAT_CP_COSTS: dict[CombatRole, int] = {
    CombatRole.PHASING_ASSAULT: 5,
    CombatRole.PHASING_PROBE: 2,
    CombatRole.PHASING_BARRAGE_ONLY: 5,
    CombatRole.DEFENDING_FULL: 3,
    CombatRole.DEFENDING_PROBE: 2,
    CombatRole.DEFENDING_WEAK: 1,
    CombatRole.UNDERGOING_BARRAGE: 3,
}


def combat_cp_cost(role: CombatRole) -> int:
    """CP cost for a unit in a given combat *role* (Cases 11.21-11.27)."""
    return COMBAT_CP_COSTS[role]


# ---------------------------------------------------------------------------
# Rulebook example (Case 11.35) — 90th Leichte Division
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CombatStrengthSummary:
    """Snapshot of a unit or formation's combat strengths.

    Case 11.36 — Players keep a running track of Raw and Actual Points.
    """

    barrage_raw: int = 0
    barrage_actual: int = 0
    anti_armor_raw: int = 0
    anti_armor_actual: int = 0
    offensive_assault_raw: int = 0
    offensive_assault_actual: int = 0
    defensive_assault_raw: int = 0
    defensive_assault_actual: int = 0
    aa_points: int = 0


def summarize_combat_strength(units: list[Unit]) -> CombatStrengthSummary:
    """Compute aggregate combat strengths for a list of units.

    Case 11.34 — All Raw Points are totaled before dividing by 10.
    """
    b_raw = sum(raw_points(u.stats.barrage_rating, u.current_toe) for u in units)
    aa_raw = sum(raw_points(u.stats.anti_armor_strength, u.current_toe) for u in units)
    oa_raw = sum(raw_points(u.stats.offensive_close_assault, u.current_toe) for u in units)
    da_raw = sum(raw_points(u.stats.defensive_close_assault, u.current_toe) for u in units)
    aa_pts = sum(raw_points(u.stats.anti_aircraft_rating, u.current_toe) for u in units)
    return CombatStrengthSummary(
        barrage_raw=b_raw,
        barrage_actual=actual_points(b_raw),
        anti_armor_raw=aa_raw,
        anti_armor_actual=actual_points(aa_raw),
        offensive_assault_raw=oa_raw,
        offensive_assault_actual=actual_points(oa_raw),
        defensive_assault_raw=da_raw,
        defensive_assault_actual=actual_points(da_raw),
        aa_points=aa_pts,
    )
