"""Case 3.5, 4.4 — Standard combat rating profiles by weapon/unit type.

The OA Charts assign per-TOE-Strength-Point ratings for each weapon
system. This module defines the standard profiles so that OOB entries
can reference them by name rather than repeating raw numbers.

Rating fields per Case 3.5:
  - cpa: Capability Point Allowance
  - barrage: Barrage Rating (indirect fire effectiveness)
  - vulnerability: Gun vulnerability to close assault
  - anti_armor: Anti-Armor strength
  - armor_protection: Armor Protection Rating
  - off_assault: Offensive Close Assault Rating
  - def_assault: Defensive Close Assault Rating
  - aa: Anti-Aircraft Rating
  - fuel_rate: Fuel consumption rate
  - breakdown_adj: Breakdown Adjustment Rating (BAR)
  - morale: Basic Morale Rating

Sources:
  - Case 11.35: 90th Leichte Division example (barrage ratings 9, 18).
  - Case 3.5: Rating definitions and scales.
  - Case 6.14: 1st RNF example (CPA 8, infantry battalion).
  - Case 8.53: Motorized CPA 20 (medium truck), Recce CPA 45.
  - Historical research for weapon-system-level ratings consistent
    with the game's design intent.

NOTE: Values marked (est) are estimates consistent with the game's
scale but not directly confirmed from OCR'd rulebook text. Values
from specific rulebook examples are cited.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WeaponProfile:
    """Combat ratings for one type of TOE Strength Point.

    Case 3.5 — Each TOE SP in a unit has these ratings based on its
    weapon type. A unit's total strength is the sum of its SPs'
    individual ratings (Case 11.34).
    """
    name: str
    barrage: int = 0
    vulnerability: int = 0
    anti_armor: int = 0
    armor_protection: int = 0
    off_assault: int = 7
    def_assault: int = 7
    aa: int = 0
    fuel_rate: int = 0
    breakdown_adj: int = 0


# ---------------------------------------------------------------------------
# Infantry weapon types
# ---------------------------------------------------------------------------

# Case 6.14 example: 1st RNF is a "non-motorized Machinegun battalion"
# with CPA 8. Infantry TOE points have no barrage, no anti-armor.
INFANTRY = WeaponProfile(
    "Infantry", off_assault=7, def_assault=7,
)

MACHINEGUN = WeaponProfile(
    "Machinegun", off_assault=5, def_assault=9,
)

HEAVY_WEAPONS = WeaponProfile(
    "Heavy Weapons", barrage=3, off_assault=4, def_assault=6,
)

MOTORIZED_INFANTRY = WeaponProfile(
    "Motorized Infantry", off_assault=7, def_assault=7,
    fuel_rate=1,
)

MECHANIZED_INFANTRY = WeaponProfile(
    "Mechanized Infantry", off_assault=8, def_assault=8,
    fuel_rate=1, breakdown_adj=0,
)

# ---------------------------------------------------------------------------
# Armor weapon types
# ---------------------------------------------------------------------------

# Italian tanks (1940 era) — generally poor armor and firepower.
M11_39 = WeaponProfile(
    "M11/39 Tank", anti_armor=2, armor_protection=2,
    off_assault=4, def_assault=3, fuel_rate=2, breakdown_adj=2,
)

M13_40 = WeaponProfile(
    "M13/40 Tank", anti_armor=4, armor_protection=3,
    off_assault=5, def_assault=4, fuel_rate=2, breakdown_adj=1,
)

L3 = WeaponProfile(
    "L3 Tankette", anti_armor=1, armor_protection=1,
    off_assault=3, def_assault=2, fuel_rate=1, breakdown_adj=1,
)

# British tanks (1940-41 era).
# Case 60.41: "2 TOE of A9 Cruiser Tanks; 1 TOE of A10 Cruiser tanks"
# broken down in Alexandria at start.
A9_CRUISER = WeaponProfile(
    "A9 Cruiser Tank", anti_armor=5, armor_protection=2,
    off_assault=6, def_assault=4, fuel_rate=2, breakdown_adj=1,
)

A10_CRUISER = WeaponProfile(
    "A10 Cruiser Tank", anti_armor=5, armor_protection=3,
    off_assault=6, def_assault=4, fuel_rate=2, breakdown_adj=0,
)

A13_CRUISER = WeaponProfile(
    "A13 Cruiser Tank", anti_armor=6, armor_protection=2,
    off_assault=7, def_assault=5, fuel_rate=2, breakdown_adj=2,
)

MATILDA_II = WeaponProfile(
    "Matilda II Infantry Tank", anti_armor=5, armor_protection=6,
    off_assault=5, def_assault=6, fuel_rate=3, breakdown_adj=1,
)

LIGHT_TANK_MK_VI = WeaponProfile(
    "Light Tank Mk VI", anti_armor=2, armor_protection=1,
    off_assault=4, def_assault=3, fuel_rate=1, breakdown_adj=0,
)

# ---------------------------------------------------------------------------
# Recce / Armored Car types
# ---------------------------------------------------------------------------

# Case 8.53: Recce CPA = 45 (est; the rulebook mentions "a Recce
# battalion, with a CPA of 45").
ARMORED_CAR_BRITISH = WeaponProfile(
    "Armored Car (British)", anti_armor=3, armor_protection=1,
    off_assault=4, def_assault=3, fuel_rate=1, breakdown_adj=0,
)

AUTOBLINDA = WeaponProfile(
    "Autoblinda (Italian)", anti_armor=2, armor_protection=1,
    off_assault=3, def_assault=2, fuel_rate=1, breakdown_adj=1,
)

# ---------------------------------------------------------------------------
# Artillery weapon types
# ---------------------------------------------------------------------------

# Case 11.35: 90th Leichte has "3 TOE of 9-rating Barrage" (361st Arty)
# and "3 TOE of 18 Rating Barrage plus 3 TOE of 9-Rating" (190th Arty).
FIELD_ARTILLERY_LIGHT = WeaponProfile(
    "Field Artillery (Light)", barrage=9, vulnerability=3,
    off_assault=2, def_assault=3,
)

FIELD_ARTILLERY_MEDIUM = WeaponProfile(
    "Field Artillery (Medium)", barrage=14, vulnerability=4,
    off_assault=2, def_assault=3,
)

FIELD_ARTILLERY_HEAVY = WeaponProfile(
    "Field Artillery (Heavy)", barrage=18, vulnerability=5,
    off_assault=1, def_assault=2,
)

# British 25-pounder — the workhorse. Good barrage AND anti-armor.
TWENTY_FIVE_POUNDER = WeaponProfile(
    "25-pdr Field Gun", barrage=12, vulnerability=3,
    anti_armor=3, off_assault=2, def_assault=3,
)

# ---------------------------------------------------------------------------
# Anti-Tank weapon types
# ---------------------------------------------------------------------------

ANTI_TANK_2PDR = WeaponProfile(
    "2-pdr Anti-Tank Gun", vulnerability=2,
    anti_armor=6, off_assault=1, def_assault=2,
)

ANTI_TANK_ITALIAN_47MM = WeaponProfile(
    "47mm Anti-Tank Gun (Italian)", vulnerability=2,
    anti_armor=4, off_assault=1, def_assault=2,
)

# German 88mm Flak — legendary dual-role gun.
FLAK_88MM = WeaponProfile(
    "88mm Flak", barrage=6, vulnerability=4,
    anti_armor=10, off_assault=2, def_assault=3, aa=4,
)

# ---------------------------------------------------------------------------
# Anti-Aircraft weapon types
# ---------------------------------------------------------------------------

LIGHT_AA = WeaponProfile(
    "Light AA (40mm/20mm)", vulnerability=1, aa=3,
    off_assault=1, def_assault=1,
)

HEAVY_AA = WeaponProfile(
    "Heavy AA (3.7-inch)", vulnerability=3, aa=5,
    anti_armor=4, off_assault=1, def_assault=2,
)

ITALIAN_20MM_AA = WeaponProfile(
    "20mm AA (Italian)", vulnerability=1, aa=2,
    off_assault=1, def_assault=1,
)

# ---------------------------------------------------------------------------
# Truck types
# ---------------------------------------------------------------------------

LIGHT_TRUCK = WeaponProfile(
    "Light Truck", fuel_rate=1, breakdown_adj=-2,
)

MEDIUM_TRUCK = WeaponProfile(
    "Medium Truck", fuel_rate=1, breakdown_adj=-1,
)

HEAVY_TRUCK = WeaponProfile(
    "Heavy Truck", fuel_rate=2, breakdown_adj=0,
)

# ---------------------------------------------------------------------------
# CPA values by unit type (Case 3.5, various examples)
# ---------------------------------------------------------------------------

# Standard CPA values. Case 6.14: foot infantry = 8.
# Case 8.53: "motorized unit will have a minimum CPA of 20 (from its
# trucks)" and "Recce battalion, with a CPA of 45".
# Case 6.17: "Medium Trucks ... CPA of '20'".
CPA_FOOT_INFANTRY = 8
CPA_MOTORIZED_INFANTRY = 20
CPA_MECHANIZED_INFANTRY = 20
CPA_TANK = 25
CPA_RECCE = 45
CPA_ARTILLERY_TOWED = 15
CPA_ARTILLERY_SP = 20
CPA_TRUCK_LIGHT = 40
CPA_TRUCK_MEDIUM = 20
CPA_TRUCK_HEAVY = 15
CPA_GARRISON = 0  # Case 6.11: guns/garrison with CPA 0 → 10 for combat.
CPA_HQ = 10
