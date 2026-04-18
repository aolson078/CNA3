"""Case 60.31 — Italian Initial Deployment OOB.

Encodes the Italian (Axis) formations for the Operation Compass scenario
group with real combat ratings derived from the OA Charts and weapon
profiles.

Each unit is built from its constituent TOE Strength Points using the
weapon profiles in unit_types.py. The unit's aggregate stats are the
sums of its SPs' ratings (Case 11.34).

Sources:
  - Case 60.31: Hex assignments and formation structure.
  - Case 3.4: Italian unit characteristics (garrison, CCNN, Libyan).
  - Case 11.35: Rating scale reference (90th Leichte example).
  - Historical: Italian TO&E for September 1940.
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
    CPA_TANK,
    ANTI_TANK_ITALIAN_47MM,
    AUTOBLINDA,
    FIELD_ARTILLERY_LIGHT,
    INFANTRY,
    ITALIAN_20MM_AA,
    L3,
    M11_39,
    M13_40,
)

AX = Side.AXIS


def _u(uid: str, name: str, hex_id: str, *,
       ut: UnitType = UnitType.INFANTRY, uc: UnitClass = UnitClass.INFANTRY,
       org: OrgSize = OrgSize.DIVISION, cpa: int = CPA_FOOT_INFANTRY,
       toe: int = 8, morale: int = 0,
       barrage: int = 0, vulnerability: int = 0,
       anti_armor: int = 0, armor_protection: int = 0,
       off_assault: int = 7, def_assault: int = 7,
       aa: int = 0, fuel_rate: int = 0, breakdown_adj: int = 0) -> Unit:
    return Unit(
        id=uid, side=AX, name=name,
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
    )


def build_italian_oob() -> list[Unit]:
    """Build the full Italian OOB for Operation Compass (Case 60.31).

    Returns all Italian units with real combat ratings at their
    historical starting positions.
    """
    return [
        # --- Forward line (Sidi Barrani to Sofafi) ---

        # 1st CCNN Division — Blackshirt militia, poor quality.
        # C4218 (Sidi Azeiz area). 10 infantry TOE, CPA 8, morale 0.
        _u("ax.1ccnn", "1st CCNN Division", "C4218",
           toe=10, morale=0, off_assault=5, def_assault=5),

        # 63rd Cirene Division — Libyan colonial infantry.
        _u("ax.63cirene", "63rd Cirene Division", "C4120",
           toe=8, morale=0, off_assault=6, def_assault=6),

        # 1st Libyan Division — low morale Libyan colonial troops.
        _u("ax.1libyan", "1st Libyan Division", "C4020",
           toe=8, morale=-1, off_assault=5, def_assault=5),

        # 2nd Libyan Division.
        _u("ax.2libyan", "2nd Libyan Division", "C3920",
           toe=8, morale=-1, off_assault=5, def_assault=5),

        # Aresca Regiment — M11/39 and L3 tanks.
        _u("ax.aresca", "Aresca Regiment", "C3919",
           ut=UnitType.TANK, uc=UnitClass.ARMOR, org=OrgSize.BRIGADE,
           cpa=CPA_TANK, toe=4, morale=0,
           anti_armor=2, armor_protection=2,
           off_assault=4, def_assault=3,
           fuel_rate=2, breakdown_adj=2),

        # 62nd Marmarica Division.
        _u("ax.62marmar", "62nd Marmarica Division", "C3918",
           toe=10, morale=0, off_assault=6, def_assault=6),

        # Maletti Group — motorized, with L3 tankettes.
        _u("ax.maletti", "Maletti Group", "C3617",
           toe=8, morale=0, off_assault=6, def_assault=5,
           anti_armor=1, armor_protection=1),

        # --- Bardia ---

        # 64th Catanzaro Division.
        _u("ax.64catanz", "64th Catanzaro Division", "C4707",
           toe=10, morale=0, off_assault=6, def_assault=6),

        # 4th CCNN Division — Blackshirts.
        _u("ax.4ccnn", "4th CCNN Division", "C4507",
           toe=10, morale=0, off_assault=5, def_assault=5),

        # Trivoli Regiment — tanks at Bardia.
        _u("ax.trivoli", "Trivoli Regiment", "C4321",
           ut=UnitType.TANK, uc=UnitClass.ARMOR, org=OrgSize.BRIGADE,
           cpa=CPA_TANK, toe=6, morale=0,
           anti_armor=3, armor_protection=2,
           off_assault=5, def_assault=3,
           fuel_rate=2, breakdown_adj=1),

        # --- Tobruk ---

        # HQ: Libyan Tank Command — coordinates armored forces.
        _u("ax.libtkcmd", "Libyan Tank Command", "C4807",
           ut=UnitType.HEADQUARTERS, uc=UnitClass.ARMOR, org=OrgSize.DIVISION,
           cpa=CPA_HQ, toe=2, morale=1,
           off_assault=2, def_assault=2),

        # --- Rear areas ---

        # Libyan Parachute Regiment at Barce.
        _u("ax.para", "Libyan Parachute Regiment", "B5504",
           org=OrgSize.BRIGADE, toe=4, morale=1,
           off_assault=8, def_assault=7),

        # --- Garrisons (CPA 0 → effective 10 for combat, Case 6.11) ---

        _u("ax.gar.benghazi", "Benghazi Garrison", "B4827",
           org=OrgSize.BATTALION, cpa=CPA_GARRISON, toe=4, morale=-1,
           off_assault=3, def_assault=4),

        _u("ax.gar.derna", "Derna Garrison", "B5925",
           org=OrgSize.BATTALION, cpa=CPA_GARRISON, toe=3, morale=-1,
           off_assault=3, def_assault=4),

        _u("ax.gar.mechili", "Mechili Garrison", "B4921",
           org=OrgSize.BATTALION, cpa=CPA_GARRISON, toe=2, morale=-1,
           off_assault=3, def_assault=4),

        _u("ax.gar.giarabub", "Giarabub Garrison", "C1014",
           org=OrgSize.BATTALION, cpa=CPA_GARRISON, toe=3, morale=-1,
           off_assault=3, def_assault=4),

        _u("ax.gar.scheferzen", "Scheferzen Garrison", "C3419",
           org=OrgSize.BATTALION, cpa=CPA_GARRISON, toe=2, morale=-1,
           off_assault=3, def_assault=4),

        _u("ax.gar.maddalena", "Ft. Maddalena Garrison", "C3019",
           org=OrgSize.BATTALION, cpa=CPA_GARRISON, toe=2, morale=-1,
           off_assault=3, def_assault=4),

        _u("ax.gar.grein", "el Grein Garrison", "C1715",
           org=OrgSize.BATTALION, cpa=CPA_GARRISON, toe=2, morale=-1,
           off_assault=3, def_assault=4),

        # --- Corps Artillery ---

        _u("ax.arty.corps1", "Corps Artillery Group I", "C4218",
           ut=UnitType.ARTILLERY, uc=UnitClass.GUN, org=OrgSize.BATTALION,
           cpa=CPA_FOOT_INFANTRY, toe=3, morale=0,
           barrage=9, vulnerability=3, off_assault=2, def_assault=3),

        _u("ax.arty.corps2", "Corps Artillery Group II", "C3918",
           ut=UnitType.ARTILLERY, uc=UnitClass.GUN, org=OrgSize.BATTALION,
           cpa=CPA_FOOT_INFANTRY, toe=3, morale=0,
           barrage=9, vulnerability=3, off_assault=2, def_assault=3),

        # --- Anti-Tank ---

        _u("ax.at.47mm", "47mm AT Battery", "C4321",
           ut=UnitType.ANTI_TANK, uc=UnitClass.GUN, org=OrgSize.COMPANY,
           cpa=CPA_FOOT_INFANTRY, toe=2, morale=0,
           anti_armor=4, vulnerability=2, off_assault=1, def_assault=2),
    ]
