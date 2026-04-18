"""Section 30.0 — The Mediterranean Fleet (Commonwealth).

Implements Cases 30.1-30.6: naval units, offshore bombardment, ship
damage/repair, chariot raids, and naval transport.

Key rules:
  - Case 30.11: Naval units have Gun Rating (barrage) and AA Rating.
  - Case 30.16: 2 ops stages in port per 1 at sea; max 3 consecutive.
  - Case 30.21: Bombard coastal hexes; gun rating = actual barrage pts.
  - Case 30.25: Ship needs 2 ops stages in Alexandria after firing.
  - Case 30.31: Ship damage repaired in port (6 ops stages per point).
  - Case 30.41: Chariot raid (Italian): planned 6 stages ahead.

Cross-references:
  - Case 5.2 III.E: Commonwealth Fleet Phase.
  - Case 12.0: Naval bombardment uses barrage system.
  - Case 60.45: Fleet availability per scenario.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ShipType(str, Enum):
    """Case 30.11 — Types of Commonwealth naval units."""
    BATTLESHIP = "battleship"
    CRUISER = "cruiser"
    AA_CRUISER = "aa_cruiser"
    DESTROYER = "destroyer"


@dataclass
class NavalUnit:
    """A Commonwealth Fleet unit.

    Case 30.11 — Abstracted naval counter.
    """
    id: str
    ship_type: ShipType
    gun_rating: int = 0
    aa_rating: int = 0
    damage: int = 0
    ops_at_sea: int = 0
    ops_in_port: int = 0
    port: str = "Alexandria"

    @property
    def is_at_sea(self) -> bool:
        """Case 30.16 — Currently at sea."""
        return self.ops_at_sea > 0

    @property
    def can_sortie(self) -> bool:
        """Case 30.16 — Must have 2 ops in port per 1 at sea. Max 3 at sea."""
        return self.ops_in_port >= 2 and self.ops_at_sea == 0


MAX_OPS_AT_SEA = 3          # Case 30.16
PORT_REST_PER_SEA_OPS = 2   # Case 30.16
REPAIR_OPS_PER_DAMAGE = 6   # Case 30.31
REFIT_AFTER_FIRE_OPS = 2    # Case 30.25
