"""Case 60.41 — Commonwealth Initial Deployment OOB.

Encodes the Commonwealth formations for the Operation Compass scenario
group with real combat ratings.

Sources:
  - Case 60.41: Hex assignments and formation structure.
  - Case 6.15: "7th Armoured Division ... CPA of '10', or that of its
    lowest-CPA unit — the 1st KRRC (without trucks)."
  - Case 6.14: "1st Royal Northumberland Fusiliers ... CPA of eight."
  - Case 8.53: "motorized unit will have a minimum CPA of 20" and
    "Recce battalion, with a CPA of 45".
  - Case 11.35: Rating scale reference.
  - Case 60.41: "1st RTR (7/7)" notation = Close Assault ratings 7/7.
  - Historical: British/Commonwealth TO&E, September 1940.
"""

from __future__ import annotations

from cna.engine.game_state import (
    OrgSize,
    Side,
    Unit,
    UnitClass,
    UnitStats,
    UnitType,
)
from cna.data.maps.coords import hex_id_to_coord
from cna.data.oob.unit_types import (
    CPA_FOOT_INFANTRY,
    CPA_GARRISON,
    CPA_HQ,
    CPA_MOTORIZED_INFANTRY,
    CPA_RECCE,
    CPA_TANK,
    CPA_ARTILLERY_TOWED,
)

CW = Side.COMMONWEALTH


def _u(uid: str, name: str, hex_id: str, *,
       ut: UnitType = UnitType.INFANTRY, uc: UnitClass = UnitClass.INFANTRY,
       org: OrgSize = OrgSize.BATTALION, cpa: int = CPA_FOOT_INFANTRY,
       toe: int = 6, morale: int = 2,
       barrage: int = 0, vulnerability: int = 0,
       anti_armor: int = 0, armor_protection: int = 0,
       off_assault: int = 7, def_assault: int = 7,
       aa: int = 0, fuel_rate: int = 0, breakdown_adj: int = 0,
       is_motorized: bool = False) -> Unit:
    return Unit(
        id=uid, side=CW, name=name,
        unit_type=ut, unit_class=uc, org_size=org,
        stats=UnitStats(
            capability_point_allowance=cpa,
            barrage_rating=barrage,
            vulnerability=vulnerability,
            anti_armor_strength=anti_armor,
            armor_protection_rating=armor_protection,
            offensive_close_assault=off_assault,
            defensive_close_assault=def_assault,
            anti_aircraft_rating=aa,
            basic_morale=morale,
            fuel_rate=fuel_rate,
            breakdown_adjustment=breakdown_adj,
            max_toe_strength=toe,
        ),
        position=hex_id_to_coord(hex_id),
        current_toe=toe,
        current_morale=morale,
        is_motorized=is_motorized,
    )


def build_commonwealth_oob() -> list[Unit]:
    """Build the full Commonwealth OOB for Operation Compass (Case 60.41).

    Returns all Commonwealth units with real combat ratings at their
    historical starting positions.
    """
    return [
        # --- Forward screen (7th Armoured Division elements) ---

        # 2nd Scots Guards — infantry battalion at Sidi Barrani.
        _u("cw.2scotsgds", "2nd Scots Guards", "C4131",
           toe=6, morale=2, off_assault=7, def_assault=8),

        # 31st Field Artillery Regiment — 25-pdrs.
        _u("cw.31field", "31st Field Arty Regt", "C4131",
           ut=UnitType.ARTILLERY, uc=UnitClass.GUN,
           cpa=CPA_ARTILLERY_TOWED, toe=4, morale=2,
           barrage=12, vulnerability=3, anti_armor=3,
           off_assault=2, def_assault=3),

        # 1st French Motor Marines — small motorized company.
        _u("cw.1french", "1st French Motor Marines", "C3926",
           org=OrgSize.COMPANY, cpa=CPA_MOTORIZED_INFANTRY,
           toe=2, morale=1, off_assault=7, def_assault=7,
           is_motorized=True),

        # 3rd Coldstream Guards — at Halfaya Pass (C3922).
        _u("cw.3cold", "3rd Coldstream Guards", "C3922",
           toe=6, morale=2, off_assault=8, def_assault=9),

        # 1st Kings Royal Rifle Corps — Case 6.15: CPA 10 (without trucks).
        # Notation "7Spt/7" = 7 Support Group / 7th Armoured Div.
        _u("cw.1krrc", "1st KRRC", "C3922",
           cpa=10, toe=6, morale=2, off_assault=7, def_assault=8),

        # 4th RHA — Royal Horse Artillery with 25-pdrs.
        _u("cw.4rha", "4th RHA", "C3922",
           ut=UnitType.ARTILLERY, uc=UnitClass.GUN,
           cpa=CPA_ARTILLERY_TOWED, toe=4, morale=2,
           barrage=12, vulnerability=3, anti_armor=3,
           off_assault=2, def_assault=3),

        # 7th Medium Arty Regt — heavier guns.
        _u("cw.7med", "7th Medium Arty Regt", "C3922",
           ut=UnitType.ARTILLERY, uc=UnitClass.GUN,
           cpa=CPA_ARTILLERY_TOWED, toe=3, morale=2,
           barrage=18, vulnerability=5,
           off_assault=1, def_assault=2),

        # 1st Royal Northumberland Fusiliers — Case 6.14: CPA 8.
        _u("cw.1rnf", "1st Royal Northumberland Fus", "C3721",
           cpa=8, toe=6, morale=2, off_assault=5, def_assault=9),

        # 3rd RHA (Anti-Tank) — 2-pdr AT guns.
        _u("cw.3rha_at", "3rd RHA (AT)", "C3721",
           ut=UnitType.ANTI_TANK, uc=UnitClass.GUN,
           cpa=CPA_ARTILLERY_TOWED, toe=4, morale=2,
           anti_armor=6, vulnerability=2,
           off_assault=1, def_assault=2),

        # 1st RTR — tanks. Case 60.41: "(7/7)" = assault 7/7.
        _u("cw.1rtr", "1st RTR", "C3520",
           ut=UnitType.TANK, uc=UnitClass.ARMOR,
           cpa=CPA_TANK, toe=4, morale=2,
           anti_armor=5, armor_protection=2,
           off_assault=7, def_assault=7,
           fuel_rate=2, breakdown_adj=1),

        # 2nd Rifle Brigade.
        _u("cw.2rifle", "2nd Rifle Bde", "C3320",
           cpa=10, toe=6, morale=2, off_assault=7, def_assault=8),

        # 11th Hussars — Recce. Case 8.53: CPA 45 (est).
        _u("cw.11hus", "11th Hussars", "C3020",
           ut=UnitType.RECCE, uc=UnitClass.ARMOR,
           cpa=CPA_RECCE, toe=3, morale=3,
           anti_armor=3, armor_protection=1,
           off_assault=4, def_assault=3,
           fuel_rate=1, breakdown_adj=0),

        # --- Mersa Matruh area ---

        # Matruh Garrison.
        _u("cw.matruh", "Matruh Garrison", "D3714",
           org=OrgSize.BRIGADE, cpa=CPA_GARRISON,
           toe=8, morale=1, off_assault=5, def_assault=6),

        # 7th Armoured Division HQ — at D3612.
        _u("cw.7armd_hq", "7th Armoured Div HQ", "D3612",
           ut=UnitType.HEADQUARTERS, org=OrgSize.DIVISION,
           cpa=CPA_HQ, toe=2, morale=2,
           off_assault=2, def_assault=2),

        # 4th Indian Division HQ — at D3615.
        _u("cw.4ind_hq", "4th Indian Div HQ", "D3615",
           ut=UnitType.HEADQUARTERS, org=OrgSize.DIVISION,
           cpa=CPA_HQ, toe=2, morale=2,
           off_assault=2, def_assault=2),

        # --- Rear areas ---

        # 16th Infantry Brigade — at E1829 (El Alamein area).
        _u("cw.16bde", "16th Inf Bde", "E1829",
           org=OrgSize.BRIGADE, cpa=CPA_FOOT_INFANTRY,
           toe=8, morale=1, off_assault=7, def_assault=7),

        # 2nd New Zealand Division HQ — Alexandria.
        _u("cw.2nz_hq", "2nd NZ Div HQ", "E3613",
           ut=UnitType.HEADQUARTERS, org=OrgSize.DIVISION,
           cpa=CPA_HQ, toe=2, morale=2,
           off_assault=2, def_assault=2),

        # 4th NZ Brigade — Alexandria.
        _u("cw.4nz_bde", "4th NZ Brigade", "E3613",
           org=OrgSize.BRIGADE, cpa=CPA_FOOT_INFANTRY,
           toe=6, morale=2, off_assault=7, def_assault=7),

        # 6th Australian Division HQ — Training at Cairo.
        _u("cw.6aus_hq", "6th Australian Div (Training)", "E1430",
           ut=UnitType.HEADQUARTERS, org=OrgSize.DIVISION,
           cpa=CPA_HQ, toe=2, morale=1,
           off_assault=2, def_assault=2),

        # --- Artillery (dispersed) ---

        # 8th Medium Arty Regt — rear area.
        _u("cw.8med", "8th Medium Arty Regt", "D3714",
           ut=UnitType.ARTILLERY, uc=UnitClass.GUN,
           cpa=CPA_ARTILLERY_TOWED, toe=3, morale=2,
           barrage=18, vulnerability=5,
           off_assault=1, def_assault=2),

        # 65th Anti-Tank Regt.
        _u("cw.65at", "65th Anti-Tank Regt", "D3714",
           ut=UnitType.ANTI_TANK, uc=UnitClass.GUN,
           cpa=CPA_ARTILLERY_TOWED, toe=4, morale=2,
           anti_armor=6, vulnerability=2,
           off_assault=1, def_assault=2),
    ]
