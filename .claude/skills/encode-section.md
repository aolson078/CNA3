---
name: encode-section
description: >
  THE daily driver skill. Given a section number, reads the extracted rule text,
  reads any existing code, and generates/extends the Python module with functions
  per case — docstrings with case citations, cross-reference comments, TODO markers.
  Usage: /encode-section 8.0
user_invocable: true
---

# Encode Section

The core development workflow for encoding CNA rulebook sections as Python code.

## Input

The user provides a section number like `8.0` or `12` or `Section 15`.

## Procedure

### Step 1 — Gather context

1. **Parse the section number** (e.g., `8.0` → 8).

2. **Read the rule text**: `references/section_{NUMBER:02d}.md`

3. **Read the case index**: `references/case_index.json` — filter for this section to get the complete list of cases.

4. **Read the cross-references**: `references/cross_refs.json` — filter for this section.

5. **Check the design doc module mapping**: Read `CLAUDE.md` to determine which Python file this section maps to. The mapping follows the architecture in the design doc:
   - Sections 5-10: `cna/rules/{module}.py`
   - Sections 11-16: `cna/rules/combat/{module}.py`
   - Sections 17-23: `cna/rules/units/{module}.py`
   - Sections 24-26: `cna/rules/terrain/{module}.py`
   - Sections 27-31: `cna/rules/special/{module}.py`
   - Section 32: `cna/rules/abstract/`
   - Sections 33-44: `cna/rules/air/{module}.py`
   - Sections 45-58: `cna/rules/logistics/{module}.py`

6. **Read existing code** if the target file already exists — extend, don't overwrite.

### Step 2 — Plan the encoding

For each case in the section:
1. Determine if it needs its own function, is part of a larger function, or is a constant/config.
2. Identify dependencies on other sections (from cross-refs).
3. Identify table lookups needed.
4. Note any ambiguities or unclear rules.

### Step 3 — Generate/extend the Python module

Write the Python file following these conventions:

**Module docstring**: Cite the section number and title.
```python
"""Section 8.0 — Land Movement

Implements Cases 8.1 through 8.9 covering all land movement rules.
"""
```

**Function docstrings**: Cite case numbers.
```python
def calculate_terrain_cost(unit, hex_terrain):
    """Case 8.3 — Terrain Effects on Movement
    
    Returns the CP cost for a unit to enter a hex based on terrain type.
    See Case 8.37 for the Terrain Effects Chart.
    """
```

**Cross-reference comments**: When calling another module.
```python
# See Case 6.2 — CPA expenditure
cpa_cost = capability_points.calculate_cost(unit, action)
```

**TODO markers** for:
- Unclear rules: `# TODO: verify interpretation — Case X.Y is ambiguous about...`
- Dependencies not yet implemented: `# TODO: requires Section X.0`
- Need manual playtest: `# TODO: verify via manual playtest`

**Imports**: Use relative imports within `cna/`.

**Type hints**: On all function signatures.

**RuleViolationError**: Raise from `cna.engine.errors` for illegal actions.

### Step 4 — Generate test stubs

Create or extend `cna/tests/test_{module}.py` with:
- One test per case (at minimum the golden path)
- TODO markers for cases needing manual verification
- Fixtures for common test objects

### Step 5 — Run the case-number-auditor

After writing the code, spawn the `case-number-auditor` agent to verify coverage for this section and report the result.

## Output

- The Python module file (created or extended)
- Test stubs file
- Coverage summary from the auditor
