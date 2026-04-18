"""Section 24.0 — Construction.

Implements Cases 24.1-24.9: construction mechanics, minefields,
fortifications, roads, railroads, air facilities, repair facilities,
and supply dumps.

Construction occurs in the Construction Segment of the Organization
Phase (Case 5.2 III.C.2). Projects take multiple Operations Stages
and require engineer units and supplies.

Key rules:
  - Case 24.11: Construction initiated in Construction Segment.
  - Case 24.12: Any CP spent halts construction for that stage.
  - Case 24.31: Minefield: 1 ops stage, 15 Stores + 15 Ammo.
  - Case 24.41: Fortification: engineer + 3 TOE infantry, 3 ops stages, 30 Stores.
  - Case 24.53: Road: infantry bn 1 hex/stage, 2 Stores per hex.
  - Case 24.61: Rail: NZRRC 2 ops stages per hex.
  - Case 24.81: Temp repair facility: engineer, 3 ops stages,
    250 Stores + 150 Fuel. Max 2 per player (Case 24.85).

Cross-references:
  - Case 23.0: Engineers required for most construction.
  - Case 25.0: Fortification levels and effects.
  - Case 26.0: Minefield construction rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ConstructionType(str, Enum):
    """Case 24.0 — Types of construction projects."""
    MINEFIELD = "minefield"
    DUMMY_MINEFIELD = "dummy_minefield"
    FORTIFICATION = "fortification"
    ROAD = "road"
    RAILROAD = "railroad"
    AIR_FACILITY = "air_facility"
    REPAIR_FACILITY = "repair_facility"
    SUPPLY_DUMP = "supply_dump"
    DUMMY_SUPPLY_DUMP = "dummy_supply_dump"


@dataclass(frozen=True)
class ConstructionCost:
    """Resource and time cost for a construction project.

    Case 24.0 — Each project type has specific requirements.
    """
    ops_stages: int
    stores: int = 0
    ammo: int = 0
    fuel: int = 0
    requires_engineer: bool = True
    requires_infantry_toe: int = 0


# Case 24.31-24.85: construction costs.
CONSTRUCTION_COSTS: dict[ConstructionType, ConstructionCost] = {
    ConstructionType.MINEFIELD: ConstructionCost(1, stores=15, ammo=15),
    ConstructionType.DUMMY_MINEFIELD: ConstructionCost(1, stores=3),
    ConstructionType.FORTIFICATION: ConstructionCost(3, stores=30, requires_infantry_toe=3),
    ConstructionType.ROAD: ConstructionCost(1, stores=2, requires_engineer=False),
    ConstructionType.RAILROAD: ConstructionCost(2, stores=1),
    ConstructionType.REPAIR_FACILITY: ConstructionCost(3, stores=250, fuel=150),
    ConstructionType.SUPPLY_DUMP: ConstructionCost(1, stores=0, requires_engineer=False),
    ConstructionType.DUMMY_SUPPLY_DUMP: ConstructionCost(1, stores=0, requires_engineer=False),
}

MAX_TEMP_REPAIR_FACILITIES = 2  # Case 24.85
