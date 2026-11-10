"""U37：backend 根目录测试的 GUI import 守卫自测。"""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_guard():
    path = Path(__file__).resolve().parent.parent / "scripts" / "check_backend_test_imports.py"
    spec = importlib.util.spec_from_file_location("check_backend_test_imports", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_detects_module_level_ui_import(tmp_path):
    p = tmp_path / "test_bad.py"
    p.write_text("from pilotstd.ui import MainWindow\n", encoding="utf-8")
    violations = _load_guard().find_violations([p])
    assert violations and "from pilotstd.ui" in violations[0]


def test_detects_module_level_pyqt6_import(tmp_path):
    p = tmp_path / "test_bad_qt.py"
    p.write_text("import PyQt6.QtWidgets\n", encoding="utf-8")
    violations = _load_guard().find_violations([p])
    assert violations and "PyQt6.QtWidgets" in violations[0]


def test_allows_lazy_import_inside_test(tmp_path):
    p = tmp_path / "test_lazy.py"
    p.write_text(
        "def test_x():\n    from pilotstd.ui import MainWindow\n    assert MainWindow\n",
        encoding="utf-8",
    )
    assert _load_guard().find_violations([p]) == []
