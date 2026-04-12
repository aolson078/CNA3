---
name: extract-section
description: >
  Extract clean, machine-readable rule text for a specific section from the CNA PDF.
  Usage: /extract-section 12.0
  Reads from references/section_XX.md (already extracted by scripts/extract_rules.py),
  cleans OCR artifacts, identifies case boundaries, tags cross-references, and
  presents the structured text for review or further processing.
user_invocable: true
---

# Extract Section

Extract and present the cleaned rule text for a CNA rulebook section.

## Input

The user provides a section number like `12.0` or `8` or `Section 15`.

## Procedure

1. **Parse the section number** from the user's input. Extract the major section number (e.g., `12.0` → `12`, `8` → `8`).

2. **Read the reference file**: `references/section_{NUMBER:02d}.md`
   - If it doesn't exist, tell the user to run `python scripts/extract_rules.py` first.

3. **Read cross-references**: `references/cross_refs.json`
   - Filter for entries where the source or target is in this section.

4. **Present the section** with:
   - Section title and case count
   - Clean, formatted rule text with markdown headings per case
   - A **Cross-References** appendix listing all "See Case X.Y" references from this section and sections that reference this one
   - Any OCR quality warnings (garbled text, unreadable table cells)

5. **If the user asks to re-extract** (e.g., the text quality is poor), offer to run the extraction script for just that section with additional cleanup.

## Output Format

```markdown
# Section X.0 — Title
Cases: N

[formatted rule text with ## and ### headings per case]

---

## Cross-References

### This section references:
- [X.3] → See [12.2] (barrage terrain modifier)
- [X.5] → See [6.1] (CPA cost)

### Referenced by:
- [15.4] references [X.2] (combined arms modifier)
```
