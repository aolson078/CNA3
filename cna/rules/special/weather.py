"""Section 29.0 — Weather.

Implements Cases 29.1-29.6: weather determination, normal/hot/sandstorm/
rainstorm effects, and the Weather Table.

Weather is determined each Operations Stage by rolling two dice on the
Weather Table (indexed by season). Weather affects movement, breakdown,
construction, air operations, and water supply.

Key rules:
  - Case 29.1: Roll each ops stage; Weather Table by season.
  - Case 29.31: Hot weather: construction +10 Water, breakdown +1 column.
  - Case 29.41: Sandstorm: no construction, no aircraft, movement ×2,
    +1 breakdown column if 50%+ movement in sandstorm area.
  - Case 29.51: Rainstorm: no aircraft, wadis impassable (except roads),
    roads become tracks for movement.

Cross-references:
  - Case 5.2 III.B: Weather Determination Phase.
  - Case 21.0: Breakdown affected by weather.
  - Case 24.0: Construction halted in bad weather.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from cna.engine.dice import DiceRoller
from cna.engine.game_state import GameState, WeatherState


# ---------------------------------------------------------------------------
# Season (Case 29.1)
# ---------------------------------------------------------------------------


class Season(str, Enum):
    """Case 29.1 — Seasons for the Weather Table."""
    SPRING = "spring"       # Mar-May
    SUMMER = "summer"       # Jun-Aug
    AUTUMN = "autumn"       # Sep-Nov
    WINTER = "winter"       # Dec-Feb


def season_for_turn(game_turn: int) -> Season:
    """Determine season from game turn number (Case 29.1).

    Game-Turn 1 = September 1940 (Autumn). Each turn ≈ 1 week.
    ~4 turns/month, ~13 turns/season.
    """
    # Month offset from September 1940.
    month = 9 + (game_turn - 1) // 4  # approximate
    month_of_year = ((month - 1) % 12) + 1
    if month_of_year in (3, 4, 5):
        return Season.SPRING
    if month_of_year in (6, 7, 8):
        return Season.SUMMER
    if month_of_year in (9, 10, 11):
        return Season.AUTUMN
    return Season.WINTER


# ---------------------------------------------------------------------------
# Weather Table (Case 29.6)
# ---------------------------------------------------------------------------

# Simplified Weather Table. Roll 2d6 sum → weather.
# TODO-29.6: replace with full table by season.
_WEATHER_TABLE: dict[Season, dict[range, WeatherState]] = {
    Season.AUTUMN: {
        range(2, 5): WeatherState.CLEAR,
        range(5, 8): WeatherState.CLEAR,
        range(8, 10): WeatherState.OVERCAST,
        range(10, 12): WeatherState.SANDSTORM,
        range(12, 13): WeatherState.RAIN,
    },
    Season.WINTER: {
        range(2, 4): WeatherState.CLEAR,
        range(4, 7): WeatherState.OVERCAST,
        range(7, 9): WeatherState.RAIN,
        range(9, 11): WeatherState.SANDSTORM,
        range(11, 13): WeatherState.CLEAR,
    },
    Season.SPRING: {
        range(2, 5): WeatherState.CLEAR,
        range(5, 8): WeatherState.CLEAR,
        range(8, 10): WeatherState.OVERCAST,
        range(10, 12): WeatherState.SANDSTORM,
        range(12, 13): WeatherState.RAIN,
    },
    Season.SUMMER: {
        range(2, 7): WeatherState.CLEAR,
        range(7, 10): WeatherState.CLEAR,
        range(10, 12): WeatherState.SANDSTORM,
        range(12, 13): WeatherState.SANDSTORM,
    },
}


@dataclass(frozen=True)
class WeatherRollResult:
    """Outcome of a weather determination roll.

    Case 29.1 — Season, dice roll, and resulting weather.
    """
    season: Season
    dice_sum: int
    weather: WeatherState


def determine_weather(game_turn: int, dice: DiceRoller) -> WeatherRollResult:
    """Roll for weather this Operations Stage (Case 29.1).

    Args:
        game_turn: Current game turn (for season lookup).
        dice: DiceRoller for 2d6 sum.

    Returns:
        WeatherRollResult with the determined weather.
    """
    season = season_for_turn(game_turn)
    roll = dice.roll_sum(2)

    table = _WEATHER_TABLE.get(season, _WEATHER_TABLE[Season.AUTUMN])
    weather = WeatherState.CLEAR
    for rng, w in table.items():
        if roll in rng:
            weather = w
            break

    return WeatherRollResult(season=season, dice_sum=roll, weather=weather)


def handle_weather_phase(state: GameState, _step) -> None:
    """PhaseDriver handler for the Weather Determination Phase.

    Case 5.2 III.B — Roll weather and update state.
    """
    from cna.engine.game_state import Phase
    if state.phase != Phase.WEATHER_DETERMINATION:
        return
    result = determine_weather(state.game_turn, state.dice)
    state.weather = result.weather
    state.log(
        f"Weather: {result.weather.value} (season={result.season.value}, roll={result.dice_sum})",
        side=None,
        category="weather",
        data={"season": result.season.value, "roll": result.dice_sum,
              "weather": result.weather.value},
    )
