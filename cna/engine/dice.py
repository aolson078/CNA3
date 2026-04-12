"""Centralized dice module for CNA.

CNA uses multiple dice conventions:
  (a) Two dice read as big-small concatenation (roll 2,5 → "52")
  (b) Single die rolls (1-6)
  (c) Summed dice for certain tables

All rolls use a seeded RNG for deterministic replay.
"""

import random
from dataclasses import dataclass, field


@dataclass
class DiceRoller:
    """Seeded dice roller supporting all CNA dice conventions.

    Attributes:
        seed: The random seed for reproducibility.
        roll_log: History of all rolls for replay/audit.
    """

    seed: int = 0
    roll_log: list[dict] = field(default_factory=list)
    _rng: random.Random = field(init=False, repr=False)

    def __post_init__(self):
        self._rng = random.Random(self.seed)

    def _roll_single(self) -> int:
        """Roll a single d6 (1-6)."""
        return self._rng.randint(1, 6)

    def roll(self) -> int:
        """Roll a single die (1-6).

        Case 4.0 — Basic die roll mechanic.
        """
        result = self._roll_single()
        self._rng_log("single", result)
        return result

    def roll_concat(self) -> int:
        """Roll two dice and concatenate as big-small (e.g., roll 2,5 → 52).

        Case 4.0 — Two-digit die roll: the higher die is the tens digit,
        the lower die is the ones digit. Range: 11-66.
        """
        d1 = self._roll_single()
        d2 = self._roll_single()
        high = max(d1, d2)
        low = min(d1, d2)
        result = high * 10 + low
        self._rng_log("concat", result, dice=(d1, d2))
        return result

    def roll_sum(self, count: int = 2) -> int:
        """Roll multiple dice and sum them.

        Args:
            count: Number of dice to roll.
        """
        dice = [self._roll_single() for _ in range(count)]
        result = sum(dice)
        self._rng_log("sum", result, dice=tuple(dice))
        return result

    def _rng_log(self, mode: str, result: int, dice: tuple[int, ...] | None = None):
        entry = {"mode": mode, "result": result}
        if dice is not None:
            entry["dice"] = dice
        self.roll_log.append(entry)

    def reset(self, seed: int | None = None):
        """Reset the RNG, optionally with a new seed."""
        if seed is not None:
            self.seed = seed
        self._rng = random.Random(self.seed)
        self.roll_log.clear()
