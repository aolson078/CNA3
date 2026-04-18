"""Section 25.0 — Fortifications.

Implements Cases 25.1-25.2: fortification levels and their combat effects.

Key rules:
  - Case 25.11: Level-based defense (1, 2, or 3). Major cities are
    Level 2; Cairo/Alexandria are Level 3.
  - Case 25.13: Constructed max Level 2 (except Cairo/Alex = 3).
  - Case 25.14: Only barrage or air bombardment reduces level.
  - Case 25.22: Defense column shifts on CRT.
  - Case 25.24: Level 3 cities ignore Pinned results.

Cross-references:
  - Case 8.37: Terrain Effects Chart fortification rows.
  - Case 12.0: Barrage against fortifications.
  - Case 15.3: Close Assault terrain effects.
  - Case 24.4: Constructing fortifications.
"""

from __future__ import annotations

from enum import IntEnum


class FortificationLevel(IntEnum):
    """Case 25.11 — Fortification levels."""
    NONE = 0
    LEVEL_1 = 1
    LEVEL_2 = 2
    LEVEL_3 = 3


# Combat column shifts per fortification level (Case 25.22).
# Negative = defender benefit (shifts left on CRT).
FORT_BARRAGE_SHIFTS: dict[FortificationLevel, int] = {
    FortificationLevel.NONE: 0,
    FortificationLevel.LEVEL_1: -1,
    FortificationLevel.LEVEL_2: -2,
    FortificationLevel.LEVEL_3: -3,
}

FORT_ANTI_ARMOR_SHIFTS: dict[FortificationLevel, int] = {
    FortificationLevel.NONE: 0,
    FortificationLevel.LEVEL_1: -1,
    FortificationLevel.LEVEL_2: -2,
    FortificationLevel.LEVEL_3: -2,
}

FORT_CLOSE_ASSAULT_SHIFTS: dict[FortificationLevel, int] = {
    FortificationLevel.NONE: 0,
    FortificationLevel.LEVEL_1: -1,
    FortificationLevel.LEVEL_2: -2,
    FortificationLevel.LEVEL_3: -3,
}

MAX_CONSTRUCTED_LEVEL = FortificationLevel.LEVEL_2  # Case 25.13


def ignores_pinned(level: FortificationLevel) -> bool:
    """Case 25.24 — Level 3 cities ignore Pinned results."""
    return level >= FortificationLevel.LEVEL_3
