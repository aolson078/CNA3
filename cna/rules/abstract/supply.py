"""Section 32.0 — Abstract Supply Rules.

Implements Cases 32.1-32.9: supply units, supply expenditures, supply
movement, motorization points, and the simplified convoy system.

When playing the Land Game without the full Logistics Game, supply is
handled through abstract Supply Units that contain Ammo and Fuel points.
Supply lines are traced from units to supply dumps.

Key rules:
  - Case 32.11: Supply Units carry max 40 Ammo + 60 Fuel.
  - Case 32.16: Supply line = half unit CPA in hexes.
  - Case 32.21: Ammo costs — 1 point per assault (non-phasing), 2 per
    barrage; phasing costs doubled.
  - Case 32.22: Fuel costs — 1 point per first movement ops stage;
    additional per CP overage.
  - Case 32.51: Motorization Points replace trucks in abstract mode.
  - Case 32.61: Simplified Axis Naval Convoys.

Cross-references:
  - Case 5.2 II: Naval Convoy Stage.
  - Case 6.0: CP system — supply affects movement ability.
  - Case 11.2: Combat costs ammo.
  - Case 60.92: Scenario-specific abstract supply setup.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from cna.engine.errors import RuleViolationError
from cna.engine.game_state import GameState, HexCoord, Side, Unit
from cna.engine.hex_map import HexMap, distance
from cna.rules.capability_points import effective_cpa


# ---------------------------------------------------------------------------
# Supply Unit (Case 32.1)
# ---------------------------------------------------------------------------

MAX_AMMO_PER_UNIT = 40  # Case 32.11
MAX_FUEL_PER_UNIT = 60  # Case 32.11


@dataclass
class SupplyUnit:
    """An abstract Supply Unit (Case 32.11).

    Stored in GameState.extras["supply_units"] as a list of dicts.
    """
    id: str
    side: Side
    position: Optional[HexCoord]
    ammo: int = 0
    fuel: int = 0

    @property
    def is_empty(self) -> bool:
        """Case 32.11 — True if no supplies remain."""
        return self.ammo <= 0 and self.fuel <= 0


# ---------------------------------------------------------------------------
# Supply line tracing (Case 32.16)
# ---------------------------------------------------------------------------


def supply_line_range(unit: Unit) -> int:
    """Maximum supply line range in hexes (Case 32.16).

    Half of the unit's CPA, traced as if the unit were a vehicle.
    """
    return effective_cpa(unit) // 2


def is_in_supply(
    state: GameState,
    unit: Unit,
    supply_positions: list[HexCoord],
) -> bool:
    """Whether *unit* can trace a supply line to any supply position.

    Case 32.16 — Supply line = half CPA distance (straight-line hex
    distance for abstract mode). Full logistics uses road/track tracing.
    """
    if unit.position is None:
        return False
    max_range = supply_line_range(unit)
    for sp in supply_positions:
        if distance(unit.position, sp) <= max_range:
            return True
    return False


# ---------------------------------------------------------------------------
# Supply expenditure (Cases 32.21-32.24)
# ---------------------------------------------------------------------------

# Ammo costs (Case 32.21).
AMMO_COST_DEFEND = 1     # Non-phasing unit in assault.
AMMO_COST_BARRAGE = 2    # Barrage.
AMMO_COST_ATTACK = 2     # Phasing unit in assault (doubled from defense).

# Fuel costs (Case 32.22).
FUEL_COST_MOVEMENT = 1   # Per first movement ops stage.


@dataclass(frozen=True)
class SupplyExpenditure:
    """Record of supply consumed by an action.

    Case 32.2 — Tracks ammo and fuel spent.
    """
    ammo: int = 0
    fuel: int = 0
    unit_id: str = ""
    action: str = ""


# ---------------------------------------------------------------------------
# Motorization Points (Case 32.5)
# ---------------------------------------------------------------------------


MOTORIZATION_MONTHLY_LOSS_PCT = 5  # Case 32.59: ~5% monthly loss.


@dataclass
class MotorizationPool:
    """Abstract motorization point pool (Case 32.51).

    Replaces detailed truck tracking in abstract mode.
    """
    side: Side
    points: int = 0

    def apply_monthly_loss(self) -> int:
        """Case 32.59 — Monthly attrition of motorization points.

        Returns points lost.
        """
        loss = max(1, self.points * MOTORIZATION_MONTHLY_LOSS_PCT // 100)
        self.points = max(0, self.points - loss)
        return loss


# ---------------------------------------------------------------------------
# Supply Pool — per-side aggregate (Case 32.0 / 60.92)
# ---------------------------------------------------------------------------

SUPPLY_POOL_KEY = "supply_pool"


@dataclass
class SupplyPool:
    """Per-side aggregate supply pool for abstract logistics.

    Case 32.0 / 60.92 — Tracks total ammo and fuel available to a side.
    Stored in GameState.extras["supply_pool"][side.value].
    """
    ammo: int = 0
    fuel: int = 0

    def spend_ammo(self, amount: int) -> int:
        """Spend ammo, capped at available. Returns amount actually spent (Case 32.21)."""
        actual = min(amount, self.ammo)
        self.ammo -= actual
        return actual

    def spend_fuel(self, amount: int) -> int:
        """Spend fuel, capped at available. Returns amount actually spent (Case 32.22)."""
        actual = min(amount, self.fuel)
        self.fuel -= actual
        return actual

    def has_ammo(self, amount: int = 1) -> bool:
        """Case 32.21 — Whether enough ammo is available."""
        return self.ammo >= amount

    def has_fuel(self, amount: int = 1) -> bool:
        """Case 32.22 — Whether enough fuel is available."""
        return self.fuel >= amount


def get_supply_pool(state: GameState, side: Side) -> SupplyPool:
    """Retrieve the SupplyPool for *side* from state extras.

    Case 32.0 — Creates a default empty pool if not initialized.
    """
    raw = state.extras.get(SUPPLY_POOL_KEY)
    if not isinstance(raw, dict):
        raw = {}
        state.extras[SUPPLY_POOL_KEY] = raw
    side_data = raw.get(side.value)
    if not isinstance(side_data, dict):
        side_data = {"ammo": 0, "fuel": 0}
        raw[side.value] = side_data
    return SupplyPool(ammo=side_data.get("ammo", 0), fuel=side_data.get("fuel", 0))


def save_supply_pool(state: GameState, side: Side, pool: SupplyPool) -> None:
    """Write the SupplyPool back to state extras (Case 32.0)."""
    raw = state.extras.setdefault(SUPPLY_POOL_KEY, {})
    raw[side.value] = {"ammo": pool.ammo, "fuel": pool.fuel}


def init_supply_pools(state: GameState, axis_ammo: int, axis_fuel: int,
                      cw_ammo: int, cw_fuel: int) -> None:
    """Initialize supply pools for both sides (Case 60.92).

    Called by scenario setup.
    """
    state.extras[SUPPLY_POOL_KEY] = {
        Side.AXIS.value: {"ammo": axis_ammo, "fuel": axis_fuel},
        Side.COMMONWEALTH.value: {"ammo": cw_ammo, "fuel": cw_fuel},
    }


# ---------------------------------------------------------------------------
# Supply consumption hooks
# ---------------------------------------------------------------------------


def consume_movement_fuel(state: GameState, unit: Unit, hexes_moved: int) -> SupplyExpenditure:
    """Consume fuel for unit movement (Case 32.22).

    Case 32.22 — Motorized units consume 1 fuel per movement ops stage.
    Non-motorized units do not consume fuel.
    """
    from cna.rules.land_movement import is_motorized
    if not is_motorized(unit) or hexes_moved <= 0:
        return SupplyExpenditure(unit_id=unit.id, action="movement")

    pool = get_supply_pool(state, unit.side)
    fuel_cost = FUEL_COST_MOVEMENT
    spent = pool.spend_fuel(fuel_cost)
    save_supply_pool(state, unit.side, pool)
    return SupplyExpenditure(fuel=spent, unit_id=unit.id, action="movement")


def consume_combat_ammo(
    state: GameState,
    side: Side,
    *,
    is_phasing: bool,
    is_barrage: bool = False,
    is_probe: bool = False,
) -> SupplyExpenditure:
    """Consume ammo for combat (Case 32.21).

    Case 32.21:
      - Non-phasing defender: 1 ammo per assault.
      - Barrage: 2 ammo.
      - Phasing attacker: 2 ammo (assault), 2 ammo (barrage).
      - Probe: 1 ammo (phasing).
    """
    pool = get_supply_pool(state, side)

    if is_barrage:
        cost = AMMO_COST_BARRAGE
    elif is_phasing:
        cost = 1 if is_probe else AMMO_COST_ATTACK
    else:
        cost = AMMO_COST_DEFEND

    spent = pool.spend_ammo(cost)
    save_supply_pool(state, side, pool)
    return SupplyExpenditure(ammo=spent, unit_id="", action="combat")
