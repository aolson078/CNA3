---
name: playtest
description: >
  Micro-scenario runner for quick tactile testing of subsystems. Sets up a minimal
  test scenario with units in hexes, runs a sequence of game actions, and reports
  outcomes. Great for verifying rules logic works end-to-end.
  Usage: /playtest
user_invocable: true
---

# Playtest

Micro-scenario runner for quick tactile testing of CNA subsystems.

## Purpose

Quickly verify that encoded rules produce correct results by setting up tiny scenarios and running them. This is not a full game --- it's a focused test of one or two mechanics at a time.

## Procedure

### Step 1 --- Choose a scenario or accept a description

Ask the user what they want to test. Examples:

- "Fire artillery from C2010 at a target in C2011"
- "Move an armoured unit from A1005 to A1010 along the road"
- "Run a barrage attack at 3:1 odds in clear terrain"
- "Test supply tracing from a port to a unit 8 hexes inland"
- "Can two infantry and one armour stack in the same hex?"

The user can also describe a custom micro-scenario in plain language.

### Step 2 --- Set up the scenario

Based on the user's description, programmatically construct a minimal game state:

1. **Create the hex map**: Only the hexes needed (typically 2-10 hexes). Use inline HexData definitions --- don't require the full map.

```python
from cna.engine.game_state import GameState
from cna.data.maps.hex_schema import HexData

# Minimal map for this test
test_hexes = [
    HexData(id="C2010", col=20, row=10, terrain_type="clear_desert",
            elevation=0, road=["C2011"], track=[], rail=[],
            coast=False, features=[]),
    HexData(id="C2011", col=20, row=11, terrain_type="clear_desert",
            elevation=0, road=["C2010"], track=[], rail=[],
            coast=False, features=[]),
]
```

2. **Place units**: Create minimal unit objects with just the stats needed for this test.

```python
artillery = Unit(
    designation="Test Artillery",
    unit_type="artillery",
    attack_strength=6,
    # ... only the fields needed for this test
)
state.place_unit(artillery, "C2010")
```

3. **Set game phase**: Put the game in the correct phase for the action being tested (movement phase, combat phase, supply phase, etc.).

### Step 3 --- Run the action sequence

Execute the game actions step by step, printing each step and its result:

```
--- Playtest: Artillery Barrage ---

Setup:
  - Hex C2010: Test Artillery (ATK 6) [friendly]
  - Hex C2011: Target Infantry (DEF 4) [enemy]
  - Terrain: clear desert, range 1

Action 1: Calculate barrage odds
  > Attacker strength: 6
  > Defender strength: 4
  > Odds ratio: 3:2, rounded to 1:1
  > Terrain modifier: none (clear desert)
  > Final column: 1:1

Action 2: Roll on Barrage Results Table (Case 12.6)
  > Die roll: 4
  > Result: "D1" (Defender loses 1 step)

Action 3: Apply result
  > Target Infantry reduced from 4 to 3 defense strength
  > No retreat required

Outcome: Barrage successful, 1 step loss inflicted.
```

### Step 4 --- Handle missing implementations

If a required function or module doesn't exist yet:

1. **Report what's missing**: "Cannot complete this playtest --- `cna.rules.combat.barrage.resolve_barrage()` is not implemented yet (Section 12.0)."
2. **Simulate with manual values**: Offer to manually specify the result of the missing function so the rest of the chain can be tested. "Want me to simulate the barrage result so we can test the casualty application logic?"
3. **Log the gap**: Note which sections need to be encoded before this scenario can run fully.

### Step 5 --- Validate against the rules

After running the scenario, cross-check:

1. **Was the sequence of phases correct?** (e.g., you can't fire in the movement phase)
2. **Were the right tables used?** (barrage vs assault vs bombardment)
3. **Were modifiers applied correctly?** (terrain, range, unit type)
4. **Does the outcome match a manual calculation?** Show the math.

If a discrepancy is found, report it as a potential bug with the case number reference.

### Step 6 --- Report

Present the full playtest result:

```markdown
## Playtest Report

### Scenario
Artillery unit fires barrage at adjacent infantry in clear desert.

### Result
Barrage at 1:1 odds, die roll 4 -> D1 (1 step loss).

### Rules Applied
- Case 12.3 (barrage procedure)
- Case 12.6 (Barrage Results Table)
- Case 12.8 (step loss application)

### Issues Found
- None (all results match manual calculation)

### Missing Implementations
- None (all required functions exist)

### Suggested Follow-up Tests
- Same scenario with rough terrain (should shift odds)
- Same scenario at range 2 (should incur range penalty)
- Barrage with multiple firing units (Case 12.4)
```

## Quick-start Scenarios

If the user just types `/playtest` with no description, offer these starter scenarios:

1. **Movement test**: Move a motorized unit 3 hexes along a road
2. **Stacking test**: Try to place 4 units in a single hex
3. **Barrage test**: Fire artillery at an adjacent hex
4. **Supply test**: Trace supply from a port to a unit
5. **CPA test**: Spend capability points on multiple actions in one turn
6. **Custom**: Describe your own scenario
