"""CNA scenario data package.

Each scenario module exposes a build_*() function returning a
GameState configured for that scenario's initial conditions.
"""

from cna.data.scenarios.operation_compass import (
    SCENARIO_ID_GRAZIANI,
    SCENARIO_ID_ITALIAN_CAMPAIGN,
    build_grazianis_offensive,
    build_italian_campaign,
)
from cna.data.scenarios.race_for_tobruk import (
    SCENARIO_ID as SCENARIO_ID_RACE_FOR_TOBRUK,
    build_race_for_tobruk,
)

__all__ = [
    "SCENARIO_ID_GRAZIANI",
    "SCENARIO_ID_ITALIAN_CAMPAIGN",
    "SCENARIO_ID_RACE_FOR_TOBRUK",
    "build_grazianis_offensive",
    "build_italian_campaign",
    "build_race_for_tobruk",
]
