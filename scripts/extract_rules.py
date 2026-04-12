"""CNA Rule Extraction Pipeline.

Processes the full 206-page CNA rulebook PDF in one pass.
Outputs:
  (a) Per-section markdown files in references/ (e.g., references/section_08.md)
  (b) Per-table data in references/tables/ (best-effort from PDF)
  (c) Master case list (references/case_index.json) mapping every case number
      to its section, title, and approximate page.
  (d) Cross-reference database (references/cross_refs.json) mapping every
      "See Case X.Y" citation found in the rules.

Usage:
    python scripts/extract_rules.py [--pdf PATH]
"""

import argparse
import json
import os
import re
import sys
import io

# Force UTF-8 output on Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

try:
    import fitz  # PyMuPDF
except ImportError:
    print("ERROR: PyMuPDF required. Install with: pip install PyMuPDF", file=sys.stderr)
    sys.exit(1)

DEFAULT_PDF = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "pdfcoffee.com-spi-the-campaign-for-north-africa.pdf"
)
REFERENCES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "references")
TABLES_DIR = os.path.join(REFERENCES_DIR, "tables")

# Section number to human-readable title mapping (from TOC)
SECTION_TITLES = {
    1: "Introduction",
    2: "How to Play the Game",
    3: "Glossary and Unit Definitions",
    4: "Game Equipment",
    5: "The Sequence of Play (Land Game)",
    6: "The Capability Point System",
    7: "Initiative",
    8: "Land Movement",
    9: "Stacking",
    10: "Zones of Control",
    11: "The Combat System",
    12: "Barrage (Artillery Combat)",
    13: "Retreat Before Assault",
    14: "Anti-Armor Combat",
    15: "Close Assault",
    16: "Patrols and Reconnaissance",
    17: "Morale",
    18: "Reserve Status",
    19: "Organization and Reorganization",
    20: "Reinforcements, Replacements, and Withdrawals",
    21: "Breakdown",
    22: "Repair",
    23: "Engineers",
    24: "Construction",
    25: "Fortifications",
    26: "Minefields",
    27: "Desert Raiders and Commandos",
    28: "Prisoners",
    29: "Weather",
    30: "The Mediterranean Fleet",
    31: "Rommel",
    32: "Abstract Logistics and Air Rules",
    33: "Air Game Sequence of Play",
    34: "Aircraft",
    35: "Squadron Ground Support Units",
    36: "Air Facilities",
    37: "Pilot Quality",
    38: "Maintenance",
    39: "Missions",
    40: "Fighters",
    41: "Bombing",
    42: "Non-Combat Air Missions",
    43: "Mediterranean Air Operations",
    44: "Air Supply",
    45: "Supply General Rules",
    46: "Supply Units",
    47: "Truck Convoys",
    48: "Supply Consumption",
    49: "Supply Distribution",
    50: "Axis Naval Convoys",
    51: "Commonwealth Shipping",
    52: "Convoy Operations",
    53: "Ports",
    54: "Water Supply",
    55: "Rail Transport",
    56: "Pipeline and Rail Logistics",
    57: "Replacement Production",
    58: "Replacement Delivery",
    59: "Special Logistics Rules",
    60: "Scenario: Operation Compass",
    61: "Scenario: Race for Tobruk",
    62: "Scenario: Crusader",
    63: "Scenario: Last Chance / Long Retreat",
    64: "Campaign Game",
    65: "Optional Rules",
}


def clean_text(text: str) -> str:
    """Clean OCR artifacts from extracted text."""
    text = text.replace('\u25a0', '')   # black square
    text = text.replace('\u25a1', '')   # white square
    text = text.replace('\u25cf', '')   # black circle
    text = text.replace('\xad', '-')    # soft hyphen
    text = text.replace('\ufb01', 'fi')
    text = text.replace('\ufb02', 'fl')
    text = text.replace('\ufb00', 'ff')
    text = text.replace('\ufb03', 'ffi')
    text = text.replace('\ufb04', 'ffl')
    # Collapse runs of whitespace (but not newlines)
    text = re.sub(r'[ \t]+', ' ', text)
    # Remove standalone page numbers
    text = re.sub(r'^\s*\d{1,3}\s*$', '', text, flags=re.MULTILINE)
    return text.strip()


def extract_pages(pdf_path: str) -> list[str]:
    """Extract text from every page of the PDF."""
    doc = fitz.open(pdf_path)
    pages = []
    for i in range(doc.page_count):
        pages.append(doc[i].get_text())
    doc.close()
    return pages


def parse_cases(full_text: str) -> list[dict]:
    """Parse all [X.Y] and [X.YZ] case references from the full text.

    Returns a list of dicts with keys: number, title, start, end, major_section.
    """
    pattern = re.compile(r'\[(\d+\.\d+)\]\s*(.*?)(?=\n|$)')
    matches = list(pattern.finditer(full_text))
    cases = []
    for i, m in enumerate(matches):
        num = m.group(1)
        title = m.group(2).strip()
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        major = int(num.split('.')[0])
        cases.append({
            'number': num,
            'title': title,
            'start': start,
            'end': end,
            'major_section': major,
        })
    return cases


def find_cross_references(text: str) -> list[dict]:
    """Find all 'See Case X.Y' or 'see Section X.Y' references."""
    pattern = re.compile(
        r'[Ss]ee\s+(?:[Cc]ase|[Ss]ection)\s+(\d+\.\d+)',
        re.IGNORECASE
    )
    refs = []
    for m in pattern.finditer(text):
        refs.append({
            'target': m.group(1),
            'position': m.start(),
            'context': text[max(0, m.start() - 40):m.end() + 40].replace('\n', ' ').strip(),
        })
    return refs


def estimate_page(position: int, page_boundaries: list[int]) -> int:
    """Estimate the PDF page number for a text position."""
    for i, boundary in enumerate(page_boundaries):
        if position < boundary:
            return i
    return len(page_boundaries)


def format_case_as_markdown(case: dict, full_text: str) -> str:
    """Format a single case as markdown with appropriate heading level."""
    num = case['number']
    title = case['title']
    content = full_text[case['start']:case['end']].strip()

    parts = num.split('.')
    decimal = parts[1] if len(parts) > 1 else '0'

    if decimal == '0':
        prefix = '#'
    elif len(decimal) == 1:
        prefix = '##'
    else:
        prefix = '###'

    # Remove the [X.Y] TITLE header from body since we're replacing it
    header_pat = re.compile(r'^\[' + re.escape(num) + r'\]\s*.*?(?:\n|$)')
    body = header_pat.sub('', content, count=1).strip()

    return f"{prefix} [{num}] {title}\n\n{body}"


def build_section_markdown(section_num: int, cases: list[dict], full_text: str) -> str:
    """Build a full markdown file for one major section."""
    title = SECTION_TITLES.get(section_num, f"Section {section_num}")
    section_cases = [c for c in cases if c['major_section'] == section_num]

    if not section_cases:
        return ""

    parts = [f"# Section {section_num}.0 — {title}\n"]
    for case in section_cases:
        parts.append(format_case_as_markdown(case, full_text))

    return '\n\n---\n\n'.join(parts)


def main():
    parser = argparse.ArgumentParser(description="Extract CNA rules from PDF")
    parser.add_argument('--pdf', default=DEFAULT_PDF, help="Path to CNA PDF")
    args = parser.parse_args()

    os.makedirs(REFERENCES_DIR, exist_ok=True)
    os.makedirs(TABLES_DIR, exist_ok=True)

    print(f"Extracting text from: {args.pdf}")
    pages = extract_pages(args.pdf)
    print(f"  {len(pages)} pages extracted")

    # Build page boundary positions for page estimation
    full_parts = []
    page_boundaries = []
    pos = 0
    for page_text in pages:
        cleaned = clean_text(page_text)
        full_parts.append(cleaned)
        pos += len(cleaned) + 2  # +2 for \n\n join
        page_boundaries.append(pos)
    full_text = '\n\n'.join(full_parts)

    # Parse all cases
    print("Parsing cases...")
    cases = parse_cases(full_text)
    print(f"  {len(cases)} cases found")

    major_sections = sorted(set(c['major_section'] for c in cases))
    print(f"  Major sections: {major_sections}")

    # Build case index
    print("Building case index...")
    case_index = {}
    for case in cases:
        page = estimate_page(case['start'], page_boundaries)
        case_index[case['number']] = {
            'title': case['title'],
            'major_section': case['major_section'],
            'section_title': SECTION_TITLES.get(case['major_section'], ''),
            'approx_page': page + 1,  # 1-indexed
        }

    index_path = os.path.join(REFERENCES_DIR, 'case_index.json')
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(case_index, f, indent=2, ensure_ascii=False)
    print(f"  Saved {len(case_index)} entries to case_index.json")

    # Build cross-reference database
    print("Finding cross-references...")
    all_refs = {}
    for case in cases:
        case_text = full_text[case['start']:case['end']]
        refs = find_cross_references(case_text)
        if refs:
            all_refs[case['number']] = [
                {'target': r['target'], 'context': r['context']}
                for r in refs
            ]

    refs_path = os.path.join(REFERENCES_DIR, 'cross_refs.json')
    with open(refs_path, 'w', encoding='utf-8') as f:
        json.dump(all_refs, f, indent=2, ensure_ascii=False)
    total_refs = sum(len(v) for v in all_refs.values())
    print(f"  Saved {total_refs} cross-references from {len(all_refs)} cases")

    # Generate per-section markdown files
    print("Generating per-section markdown files...")
    files_written = 0
    for section_num in major_sections:
        md = build_section_markdown(section_num, cases, full_text)
        if md:
            filename = f"section_{section_num:02d}.md"
            filepath = os.path.join(REFERENCES_DIR, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(md)
            case_count = sum(1 for c in cases if c['major_section'] == section_num)
            print(f"  {filename} ({case_count} cases)")
            files_written += 1

    print(f"\nDone! {files_written} section files, {len(case_index)} cases indexed, "
          f"{total_refs} cross-references mapped.")


if __name__ == '__main__':
    main()
