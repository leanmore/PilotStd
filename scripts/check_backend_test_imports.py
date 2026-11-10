#!/usr/bin/env python
"""G-XXX: forbid module-level GUI imports in backend root tests (U37).

The ``test-backend`` job intentionally does not install PyQt6.  A root
test module that imports ``pilotstd.ui`` / ``PyQt6`` at module scope
fails during collection, before any test runs.  This guard mirrors the
backend job's ignore set and scans only **module-level** imports.

Lazy imports inside a test function are allowed because existing tests
guard them with ``pytest.importorskip`` / CI skips; module-level imports
are the actual collection-time failure mode.
"""

from __future__ import annotations

import ast
import fnmatch
import sys
from pathlib import Path

_FORBIDDEN_PREFIXES = ("pilotstd.ui", "PyQt6")
# Keep in sync with .github/workflows/ci.yml test-backend --ignore list.
# These files are intentionally not collected by the backend job.
_IGNORED_NAMES = {
    "test_regression_architecture.py",
    "test_scan_misc.py",
    "test_groups23_remaining.py",
    "test_last_push.py",
    "test_unified_progress.py",
    "test_platform_notify.py",
    "test_monitor.py",
    "test_query.py",
    "test_ci_scan_fix.py",
}


def _is_forbidden(module: str | None) -> bool:
    if not module:
        return False
    return any(module == p or module.startswith(p + ".") for p in _FORBIDDEN_PREFIXES)


def _is_ignored(path: Path) -> bool:
    return path.name in _IGNORED_NAMES or fnmatch.fnmatch(path.name, "*test_ui*.py")


def find_violations(paths: list[Path]) -> list[str]:
    """Return ``path:line: import`` for module-level forbidden imports."""
    violations: list[str] = []
    for path in sorted(paths):
        # Skip files the backend job explicitly ignores (GUI/architecture).
        if _is_ignored(path):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError) as exc:
            violations.append(f"{path}: cannot parse: {exc}")
            continue
        # Only module-level imports fail during pytest collection.
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _is_forbidden(alias.name):
                        violations.append(f"{path}:{node.lineno}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if _is_forbidden(node.module):
                    violations.append(f"{path}:{node.lineno}: from {node.module} import ...")
                elif node.module == "pilotstd" and any(a.name == "ui" for a in node.names):
                    violations.append(f"{path}:{node.lineno}: from pilotstd import ui")
    return violations


def main() -> int:
    """Scan backend root tests and return 1 on any module-level GUI import."""
    root = Path(__file__).resolve().parent.parent
    tests_dir = root / "tests"
    # Root test files only; tests/gui/ is the GUI job's responsibility.
    paths = sorted(tests_dir.glob("test_*.py"))
    violations = find_violations(paths)
    if violations:
        print("[backend-test-imports] FAIL: module-level GUI imports in backend tests:")
        for item in violations:
            print(f"  {item}")
        print("Move the test to tests/gui/ (GUI job installs PyQt6) or extract pure logic.")
        return 1
    checked = sum(1 for p in paths if not _is_ignored(p))
    # Count excludes files the backend CI job intentionally ignores.
    print(f"[backend-test-imports] PASS: checked {checked}/{len(paths)} backend test files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
