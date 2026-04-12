---
name: verify-section
description: >
  Orchestrates rule-fidelity-reviewer and case-number-auditor agents against a section
  to answer "How done is Section X?" Reports cases implemented, cases missing,
  fidelity issues, and a confidence rating.
  Usage: /verify-section 8.0
user_invocable: true
---

# Verify Section

Run a comprehensive verification of a CNA rulebook section's implementation status.

## Input

The user provides a section number like `8.0` or `12` or `Section 15`.

## Procedure

### Step 1 --- Gather context

1. **Parse the section number** (e.g., `8.0` -> 8).

2. **Read the rule text**: `references/section_{NUMBER:02d}.md`
   - If it doesn't exist, tell the user to run `python scripts/extract_rules.py` first.

3. **Read the case index**: `references/case_index.json` --- filter for this section to get the complete list of cases (the "expected" set).

4. **Determine the target module**: Read `CLAUDE.md` to find the module mapping for this section.

5. **Read the existing code** for this section's module(s). If no code exists yet, the section is 0% done --- skip to the report.

### Step 2 --- Run the case-number-auditor agent

Spawn the `case-number-auditor` agent with this section number. This agent will:
- Scan all Python source files in the target module for case citations (docstrings, comments)
- Compare found case numbers against the expected set from `case_index.json`
- Report: cases implemented, cases missing, cases cited but not in the index (possible errors)

Collect its output: `implemented_cases`, `missing_cases`, `extra_cases`.

### Step 3 --- Run the rule-fidelity-reviewer agent

Spawn the `rule-fidelity-reviewer` agent with this section number. This agent will:
- For each implemented case, compare the Python logic against the rule text
- Flag discrepancies: wrong modifiers, missing conditions, incorrect table references
- Flag ambiguities in the rules that may have been resolved incorrectly
- Check cross-references are wired correctly

Collect its output: `fidelity_issues` (list of case + description + severity).

### Step 4 --- Compute the confidence rating

Calculate a composite score:

- **Coverage**: `len(implemented_cases) / len(all_cases) * 100` --- what percentage of cases have code
- **Fidelity**: Penalize based on issues found:
  - Critical (wrong result): -10 points each
  - Major (missing condition): -5 points each
  - Minor (style, naming): -1 point each
- **Test coverage**: Check if `cna/tests/test_{module}.py` exists and count test functions vs cases
- **Confidence rating**: HIGH (>85% coverage, 0 critical), MEDIUM (50-85% or has critical issues), LOW (<50%)

### Step 5 --- Generate the report

## Output Format

```markdown
# Section X.0 --- Title | Verification Report

## Summary
- **Coverage**: 7/12 cases implemented (58%)
- **Fidelity issues**: 2 major, 1 minor
- **Test coverage**: 5 tests for 7 functions
- **Confidence**: MEDIUM

## Implemented Cases
- [X.1] calculate_movement_cost() --- HIGH fidelity
- [X.2] check_stacking_limit() --- MEDIUM fidelity (1 major issue)
- ...

## Missing Cases
- [X.5] --- Night movement penalty (no code found)
- [X.8] --- Strategic movement restrictions (no code found)
- ...

## Fidelity Issues
### MAJOR
- [X.2] check_stacking_limit(): Rule says "3 units per hex" but code allows 4.
  Rule text: "No more than three ground units may occupy a single hex..."
  Code: `if count > 4:` (line 42 of movement.py)

### MINOR
- [X.3] Missing cross-reference comment for Case 6.1 dependency

## Test Gaps
- [X.1] has test --- PASS
- [X.2] has test --- PASS
- [X.3] no test file found

## Recommended Next Steps
1. Implement missing cases X.5 and X.8
2. Fix stacking limit in X.2 (critical)
3. Add tests for X.3, X.4, X.6, X.7
```
