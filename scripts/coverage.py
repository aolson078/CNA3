"""CNA Rules Coverage Dashboard.

Scans all Python source files for case number references (e.g., 12.6, 8.12)
in docstrings and comments, then compares against the master case index to
produce a per-section coverage report.

Usage:
    python scripts/coverage.py              # CLI table output
    python scripts/coverage.py --json       # Machine-readable JSON
    python scripts/coverage.py --verbose    # Show which cases are missing
"""

import argparse
import ast
import io
import json
import os
import re
import sys

# Force UTF-8 output on Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFERENCES_DIR = os.path.join(PROJECT_ROOT, "references")
CASE_INDEX_PATH = os.path.join(REFERENCES_DIR, "case_index.json")
CODE_DIRS = [
    os.path.join(PROJECT_ROOT, "cna"),
]

# Pattern to match case references like 12.6, 8.12, 45.31 in docstrings/comments
CASE_PATTERN = re.compile(r'\b(\d{1,2}\.\d{1,2})\b')


def load_case_index(path: str) -> dict:
    """Load the master case index from JSON."""
    if not os.path.isfile(path):
        print(f"ERROR: Case index not found at {path}", file=sys.stderr)
        print("  Run: python scripts/extract_rules.py", file=sys.stderr)
        sys.exit(1)
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def find_python_files(dirs: list[str]) -> list[str]:
    """Recursively find all .py files in the given directories."""
    py_files = []
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for root, _subdirs, files in os.walk(d):
            for fname in files:
                if fname.endswith('.py'):
                    py_files.append(os.path.join(root, fname))
    return sorted(py_files)


def extract_case_refs_from_file(filepath: str) -> set[str]:
    """Extract all case number references from a Python file.

    Looks in:
      1. Docstrings (via AST parsing)
      2. Comments (via line-by-line scan)
    """
    refs = set()

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
    except (OSError, UnicodeDecodeError):
        return refs

    # 1. Parse docstrings via AST
    try:
        tree = ast.parse(source, filename=filepath)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
                docstring = ast.get_docstring(node, clean=False)
                if docstring:
                    for m in CASE_PATTERN.finditer(docstring):
                        refs.add(m.group(1))
    except SyntaxError:
        pass

    # 2. Scan comments (lines starting with # after stripping)
    for line in source.splitlines():
        stripped = line.strip()
        # Inline or full-line comments
        comment_idx = stripped.find('#')
        if comment_idx != -1:
            comment_text = stripped[comment_idx:]
            for m in CASE_PATTERN.finditer(comment_text):
                refs.add(m.group(1))

    return refs


def gather_all_refs(code_dirs: list[str]) -> tuple[set[str], dict[str, set[str]]]:
    """Scan all Python files and collect case references.

    Returns:
        (all_refs, per_file_refs) where per_file_refs maps filepath to its refs.
    """
    py_files = find_python_files(code_dirs)
    all_refs = set()
    per_file = {}
    for fp in py_files:
        file_refs = extract_case_refs_from_file(fp)
        if file_refs:
            per_file[fp] = file_refs
            all_refs |= file_refs
    return all_refs, per_file


def build_section_report(case_index: dict, found_refs: set[str]) -> list[dict]:
    """Build per-section coverage stats.

    Returns a list of dicts with keys:
        section, title, total, implemented, percentage, missing
    """
    sections: dict[int, dict] = {}
    for case_num, info in case_index.items():
        sec = info['major_section']
        if sec not in sections:
            sections[sec] = {
                'section': sec,
                'title': info.get('section_title', f'Section {sec}'),
                'total': 0,
                'implemented': 0,
                'missing': [],
            }
        sections[sec]['total'] += 1
        if case_num in found_refs:
            sections[sec]['implemented'] += 1
        else:
            sections[sec]['missing'].append(case_num)

    report = []
    for sec_num in sorted(sections.keys()):
        s = sections[sec_num]
        pct = (s['implemented'] / s['total'] * 100) if s['total'] > 0 else 0.0
        s['percentage'] = round(pct, 1)
        s['missing'] = sorted(s['missing'], key=lambda x: list(map(int, x.split('.'))))
        report.append(s)
    return report


def progress_bar(pct: float, width: int = 20) -> str:
    """Render a simple ASCII progress bar."""
    filled = int(round(pct / 100 * width))
    filled = max(0, min(filled, width))
    bar = '#' * filled + '-' * (width - filled)
    return f'[{bar}]'


def print_table(report: list[dict], total_cases: int, total_implemented: int):
    """Print a nicely formatted CLI coverage table."""
    overall_pct = (total_implemented / total_cases * 100) if total_cases > 0 else 0.0

    print()
    print("=" * 80)
    print("  CNA Rules Coverage Dashboard")
    print("=" * 80)
    print()

    # Header
    header = f"{'Sec':>4}  {'Title':<35} {'Done':>5}/{'Total':<5} {'%':>6}  {'Progress':<22}"
    print(header)
    print("-" * 80)

    for s in report:
        title = s['title'][:35]
        bar = progress_bar(s['percentage'])
        line = (
            f"{s['section']:>4}  {title:<35} {s['implemented']:>5}/{s['total']:<5} "
            f"{s['percentage']:>5.1f}%  {bar}"
        )
        print(line)

    print("-" * 80)

    overall_bar = progress_bar(overall_pct)
    print(
        f"{'':>4}  {'TOTAL':<35} {total_implemented:>5}/{total_cases:<5} "
        f"{overall_pct:>5.1f}%  {overall_bar}"
    )
    print()


def print_missing(report: list[dict]):
    """Print missing cases per section (verbose mode)."""
    any_missing = False
    for s in report:
        if s['missing']:
            if not any_missing:
                print("Missing Cases by Section:")
                print("-" * 50)
                any_missing = True
            cases_str = ', '.join(s['missing'][:20])
            extra = f" ... and {len(s['missing']) - 20} more" if len(s['missing']) > 20 else ""
            print(f"  Section {s['section']:>2} ({s['title'][:30]}): {cases_str}{extra}")
    if not any_missing:
        print("No missing cases! Full coverage achieved.")
    print()


def main():
    parser = argparse.ArgumentParser(description="CNA Rules Coverage Dashboard")
    parser.add_argument('--json', action='store_true', help="Output machine-readable JSON")
    parser.add_argument('--verbose', '-v', action='store_true', help="Show missing cases per section")
    args = parser.parse_args()

    case_index = load_case_index(CASE_INDEX_PATH)
    found_refs, _per_file = gather_all_refs(CODE_DIRS)

    # Only count refs that are actually in the case index
    valid_refs = found_refs & set(case_index.keys())

    report = build_section_report(case_index, valid_refs)

    total_cases = sum(s['total'] for s in report)
    total_implemented = sum(s['implemented'] for s in report)

    if args.json:
        output = {
            'total_cases': total_cases,
            'total_implemented': total_implemented,
            'overall_percentage': round(
                (total_implemented / total_cases * 100) if total_cases > 0 else 0.0, 1
            ),
            'sections': report,
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print_table(report, total_cases, total_implemented)
        if args.verbose:
            print_missing(report)


if __name__ == '__main__':
    main()
