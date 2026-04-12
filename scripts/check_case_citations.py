#!/usr/bin/env python
"""Check that public functions in rules/ and tables/ have Case-number citations.

Every public function/class in cna/rules/ and cna/data/tables/ must have a
docstring containing at least one Case reference in d+.d+ format (e.g. "12.6").
Module-level docstrings must contain a Section citation.
"""

import ast
import re
import sys
from pathlib import Path

CASE_PATTERN = re.compile(r"\d+\.\d+")

SCAN_DIRS = [
    Path("cna/rules"),
    Path("cna/data/tables"),
]


def find_violations(filepath: Path) -> list[str]:
    """Return a list of violation messages for the given file."""
    violations: list[str] = []
    source = filepath.read_text(encoding="utf-8")

    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError as exc:
        violations.append(f"{filepath}: SyntaxError - {exc}")
        return violations

    # --- Module-level docstring check ---
    module_docstring = ast.get_docstring(tree)
    if module_docstring is None:
        violations.append(f"{filepath}: module missing docstring with Section citation")
    elif not CASE_PATTERN.search(module_docstring):
        violations.append(
            f"{filepath}: module docstring missing Section citation (expected \\d+.\\d+ pattern)"
        )

    # --- Function / class docstring check ---
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue

        # Skip private names (start with _)
        if node.name.startswith("_"):
            continue

        docstring = ast.get_docstring(node)
        kind = "class" if isinstance(node, ast.ClassDef) else "function"

        if docstring is None:
            violations.append(
                f"{filepath}:{node.lineno}: {kind} '{node.name}' missing docstring with Case citation"
            )
        elif not CASE_PATTERN.search(docstring):
            violations.append(
                f"{filepath}:{node.lineno}: {kind} '{node.name}' docstring missing Case citation "
                f"(expected \\d+.\\d+ pattern)"
            )

    return violations


def main(files: list[str] | None = None) -> int:
    """Run the citation checker.

    Parameters
    ----------
    files : list[str] | None
        If provided, only check these files.  Otherwise scan all SCAN_DIRS.

    Returns
    -------
    int
        0 if no violations, 1 otherwise.
    """
    if files:
        paths = [Path(f) for f in files]
    else:
        paths = []
        for scan_dir in SCAN_DIRS:
            if scan_dir.exists():
                paths.extend(scan_dir.rglob("*.py"))

    # Filter to only relevant directories and skip __init__.py
    relevant: list[Path] = []
    for p in paths:
        if p.name == "__init__.py":
            continue
        # Ensure the file is under one of the scan dirs
        try:
            for scan_dir in SCAN_DIRS:
                if scan_dir.exists() and p.resolve().is_relative_to(scan_dir.resolve()):
                    relevant.append(p)
                    break
            else:
                # When given explicit files, also accept paths that textually match
                p_str = p.as_posix()
                for scan_dir in SCAN_DIRS:
                    if scan_dir.as_posix() in p_str:
                        relevant.append(p)
                        break
        except (ValueError, OSError):
            continue

    if not relevant:
        return 0

    all_violations: list[str] = []
    for filepath in sorted(set(relevant)):
        if not filepath.exists():
            continue
        all_violations.extend(find_violations(filepath))

    if all_violations:
        print("Case citation violations found:\n")
        for v in all_violations:
            print(f"  {v}")
        print(f"\n{len(all_violations)} violation(s) found.")
        return 1

    print("All docstrings have proper Case citations.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] if len(sys.argv) > 1 else None))
