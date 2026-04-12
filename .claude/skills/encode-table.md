---
name: encode-table
description: >
  Transcribe a Combat Results Table or lookup table from the rulebook into a Python
  module in cna/data/tables/, with cell-by-cell verification tests.
  Usage: /encode-table 12.6
user_invocable: true
---

# Encode Table

Transcribe a CNA rulebook table into Python with verification tests.

## Input

The user provides a table ID (e.g., `12.6` for the Barrage Results Table) or a descriptive name.

## Procedure

### Step 1 — Locate the table

1. Read `references/case_index.json` to find the case matching the table ID.
2. Read the corresponding `references/section_{XX}.md` file.
3. Find the table within the rule text. Common table types in CNA:
   - **CRT (Combat Results Table)**: Cross-indexed by odds ratio and die roll
   - **Simple lookup**: Single column keyed by a value
   - **Stepped range**: Ranges of values map to results
   - **Multi-result**: Each cell contains multiple outcomes

### Step 2 — Understand the table structure

Identify:
- **Row keys**: What determines the row? (die roll, odds ratio, range, etc.)
- **Column keys**: What determines the column? (terrain, unit type, etc.)
- **Cell values**: What's in each cell? (numeric, code like "NE"/"D2", multiple results)
- **Special rules**: "Read the result as...", "If the result is X, also apply Y"

### Step 3 — Generate the Python module

Write to `cna/data/tables/{table_name}.py`. Use the appropriate data structure:

**For simple lookup tables**:
```python
"""Case 12.6 — Artillery Barrage Results Table"""

BARRAGE_RESULTS = {
    (odds_column, die_roll): result,
    ...
}

def lookup_barrage_result(odds_column: int, die_roll: int) -> str:
    """Case 12.6 — Look up barrage result."""
    return BARRAGE_RESULTS.get((odds_column, die_roll), "NE")
```

**For range-based tables**:
```python
def lookup_by_range(value: int) -> str:
    """Case X.Y — Range-based lookup."""
    if value <= 5:
        return "A"
    elif value <= 10:
        return "B"
    ...
```

### Step 4 — Generate verification tests

Create `cna/tests/test_table_{name}.py` with:
- **Every cell tested** (or a representative sample for very large tables)
- **Boundary values** at the edges of each range
- **All columns and rows** represented

```python
def test_barrage_table_cell_1_1():
    """Verify Case 12.6 — Row 1:1, Col 1 = NE"""
    assert lookup_barrage_result(1, 1) == "NE"
```

### Step 5 — Quality notes

If any cells were unreadable in the PDF extraction, add comments:
```python
# WARNING: Cell (3, 4) was unreadable in PDF — value "D2" inferred from pattern
```

## Output

- The table Python module in `cna/data/tables/`
- Verification test file in `cna/tests/`
- Summary of table dimensions, any unreadable cells, and confidence level
