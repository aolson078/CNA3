# CNA — The Campaign for North Africa (Computer Edition)

## What This Is

A faithful computer implementation of SPI's "The Campaign for North Africa" (1979), the most complex board wargame ever published. 206 pages of rules, encoded 1:1 as Python.

## Project Structure

```
cna/
  engine/       — Core engine: game state, hex map, dice, sequence of play, saves
  rules/        — Rule modules mirroring the Case System (Sections 5-58)
    combat/     — Barrage, anti-armor, close assault, patrols
    units/      — Morale, reserves, organization, reinforcements, breakdown, repair, engineers
    terrain/    — Construction, fortifications, minefields
    special/    — Desert raiders, prisoners, weather, naval, Rommel
    abstract/   — Simplified logistics/air (Section 32, used when full layers inactive)
    air/        — Air game (Sections 33-44)
    logistics/  — Full logistics (Sections 45-58)
  data/
    tables/     — Combat Results Tables, lookup functions (Sections 12.6, 14.6, 15.7, etc.)
    scenarios/  — Scenario setup data
    oob/        — Order of Battle data files
    maps/       — Hex map data files
  ui/           — Rich/Textual terminal UI
  ai/           — AI opponent (Layer 4)
  tests/        — pytest tests mirroring rules/ structure
rules/          — Extracted rulebook markdown (from PDF)
references/     — Machine-readable per-section rule text + case_index.json
scripts/        — Infrastructure scripts (extraction, coverage, validation, replay)
guides/         — Walkthrough guides (logistics, etc.)
```

## Conventions

### Case System in Code
Every public function in `cna/rules/` and `cna/data/tables/` MUST have a docstring citing the Case number(s) it implements:

```python
def calculate_barrage_points(unit, target, terrain):
    """Section 12.0, Cases 12.1-12.4

    Resolves artillery barrage against a target hex.
    See Case 12.23 for target designation rules.
    See Case 12.6 for the Barrage Results Table.
    """
```

Format: `[X.Y]` or `[X.YZ]` where X = Major Section, Y = Primary Case, Z = Secondary Case.

### Module-to-Section Mapping
Each rules module maps to specific rulebook sections. The module docstring must state which section(s) it implements:

```python
"""Section 8.0 — Land Movement

Implements Cases 8.1 through 8.9 covering all land movement rules.
"""
```

### Error Handling
All rule violations raise `RuleViolationError(case_number, message)` from `cna/engine/errors.py`. The UI catches these and displays the violated rule.

### Game State
- Runtime state: plain `@dataclass` objects (NOT pydantic)
- Serialization: JSON via `cna/engine/saves.py` with `schema_version` field
- Pydantic used ONLY at save/load boundary for validation
- Mutation: in-place within a phase, `copy.deepcopy()` snapshots between phases for undo

### Dice
`cna/engine/dice.py` supports three modes:
- Concatenated two-digit (roll 2,5 → "52")
- Single die
- Summed dice
All seeded for deterministic replay.

### Testing
- One test file per rules module in `cna/tests/`
- Three test types: example tests (from rulebook), property tests (invariants), integration tests
- Cases without rulebook examples flagged with `# TODO: verify via manual playtest`

### Build Order (Layered)
- **Layer 1:** Land Game + Abstract Air/Logistics (Sections 5-32) → Operation Compass playable
- **Layer 2:** Air Game (Sections 33-44)
- **Layer 3:** Full Logistics (Sections 45-58) → The Full Monster
- **Layer 4:** AI Opponent

### Technology
- Python 3.12+ (dataclasses, pattern matching, type hints)
- Rich for terminal UI (Layer 1)
- Textual deferred to after Layer 1
- pytest for testing
- pydantic for save/load validation only

## Custom Tooling

### Agents (`.claude/agents/`)
- `rule-fidelity-reviewer` — Reviews code against rulebook text for completeness
- `case-number-auditor` — Scans code for case citations, reports coverage
- `crt-verifier` — Verifies encoded tables cell-by-cell against rulebook
- `cross-reference-tracer` — Maps code call graph against rulebook cross-references
- `game-state-inspector` — Validates GameState for internal consistency
- `test-scenario-generator` — Generates test scaffolds from rule text

### Skills
- `/extract-section` — Extract clean rule text from PDF for a section
- `/encode-section` — THE daily driver: read rules → generate/extend Python module
- `/encode-table` — Transcribe a CRT with verification tests
- `/verify-section` — Health check: fidelity + coverage for a section
- `/encode-hex` — Guided hex map data entry
- `/encode-oob` — Structured unit data entry
- `/playtest` — Micro-scenario runner for quick tactile testing

### Scripts (`scripts/`)
- `extract_rules.py` — PDF → per-section markdown + case_index.json
- `coverage.py` — Case number coverage dashboard
- `validate_map.py` — Hex map data integrity checker
- `replay.py` — Deterministic replay regression harness
