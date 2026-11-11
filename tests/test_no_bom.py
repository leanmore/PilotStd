"""P2-06：Python 源码不得带 UTF-8 BOM（G-010/AST 会把 BOM 当语法错误跳过）。"""

from __future__ import annotations

from pathlib import Path

BOM = b"\xef\xbb\xbf"


def _python_files() -> list[Path]:
    roots = [Path("pilotstd"), Path("docker"), Path("scripts")]
    files: list[Path] = []
    for root in roots:
        if root.exists():
            files.extend(root.rglob("*.py"))
    return files


def test_no_utf8_bom_in_python_sources() -> None:
    offenders = [str(p) for p in _python_files() if p.read_bytes().startswith(BOM)]
    assert offenders == [], f"Python 源码含 UTF-8 BOM: {offenders}"


def test_g_032_script_has_no_bom() -> None:
    p = Path("scripts/check_g_032_doc_health.py")
    assert p.read_bytes().startswith(BOM) is False
