"""G-050 静默吞错棘轮门禁的受控测试（体检 D-8/D-9/D-10）。

覆盖：三类识别、超基线阻断、基线可收紧告警、templates 排除。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check_g_050_silent_errors.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_g_050_silent_errors", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = _load()

SAMPLE = '''
import logging

logger = logging.getLogger(__name__)


def f():
    try:
        pass
    except Exception:
        pass


def g():
    try:
        pass
    except Exception:
        return None


def h():
    try:
        pass
    except Exception:
        logger.debug("failed")


def i():
    try:
        pass
    except Exception:
        return 1  # 有意义的返回值，不计入
'''


def _make_tree(tmp_path: Path) -> Path:
    target = tmp_path / "pilotstd" / "pkg"
    target.mkdir(parents=True)
    (target / "mod.py").write_text(SAMPLE, encoding="utf-8")
    return tmp_path


def test_scan_detects_three_kinds(tmp_path) -> None:
    counts = gate.scan(_make_tree(tmp_path))
    assert counts["pass"]["pilotstd/pkg/mod.py"] == 1
    assert counts["return"]["pilotstd/pkg/mod.py"] == 1
    assert counts["debug"]["pilotstd/pkg/mod.py"] == 1


def test_equal_baseline_passes(tmp_path) -> None:
    counts = gate.scan(_make_tree(tmp_path))
    exceeded, tightenable = gate.compare(counts, counts)
    assert exceeded == []
    assert tightenable == []


def test_increase_blocks(tmp_path) -> None:
    counts = gate.scan(_make_tree(tmp_path))
    baseline = {"pass": {}, "return": {}, "debug": {}}
    exceeded, _ = gate.compare(counts, baseline)
    assert len(exceeded) == 3


def test_decrease_reports_tightenable(tmp_path) -> None:
    counts = gate.scan(_make_tree(tmp_path))
    baseline = {
        "pass": {"pilotstd/pkg/mod.py": 2},
        "return": {"pilotstd/pkg/mod.py": 1},
        "debug": {"pilotstd/pkg/mod.py": 1},
    }
    exceeded, tightenable = gate.compare(counts, baseline)
    assert exceeded == []
    assert any("-1" in item for item in tightenable)


def test_templates_excluded(tmp_path) -> None:
    tpl = tmp_path / "pilotstd" / "templates"
    tpl.mkdir(parents=True)
    (tpl / "x.py").write_text("try:\n    pass\nexcept Exception:\n    pass\n", encoding="utf-8")
    counts = gate.scan(tmp_path)
    assert all(not f.startswith("pilotstd/templates") for f in counts["pass"])
