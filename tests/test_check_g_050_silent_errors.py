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


# ── U34-E1：剪枝与接收者识别 ─────────────────────────────────────────────


def _tree_with(tmp_path: Path, code: str) -> Path:
    target = tmp_path / "pilotstd" / "pkg"
    target.mkdir(parents=True, exist_ok=True)
    (target / "case.py").write_text(code, encoding="utf-8")
    return tmp_path


UMBRELLA_AND_RECEIVER = '''
import logging
logging.getLogger(__name__)


class C:
    def __init__(self):
        self.log = logging.getLogger(__name__)

    def f(self):
        try:
            pass
        except Exception:
            try:
                self.log.debug("inner")
            except ValueError:
                pass
'''


def test_umbrella_handler_counted_once_and_self_log_recognized(tmp_path) -> None:
    """伞形 handler 只算 1 次；`self.log.debug`（非 Name("logger")）也要识别。"""
    counts = gate.scan(_tree_with(tmp_path, UMBRELLA_AND_RECEIVER))
    # 内层 handler 计 1；外层不再重复 ⇒ 合计 1（若未剪枝=2，若未识别 self.log=0）
    assert counts["debug"]["pilotstd/pkg/case.py"] == 1


NESTED_FUNC = '''
import logging

logger = logging.getLogger(__name__)


def f():
    try:
        pass
    except Exception:
        def helper():
            logger.debug("inside helper")
        helper()
'''


def test_nested_function_debug_not_attributed_to_handler(tmp_path) -> None:
    """handler 内定义的函数体不属于该 handler 的执行路径 → 不计 debug。"""
    counts = gate.scan(_tree_with(tmp_path, NESTED_FUNC))
    assert counts["debug"].get("pilotstd/pkg/case.py", 0) == 0


EMPTY_CONSTRUCTORS = '''
def a():
    try:
        pass
    except Exception:
        return set()


def b():
    try:
        pass
    except Exception:
        return list()


def c():
    try:
        pass
    except Exception:
        return dict()
'''


def test_empty_constructor_returns_counted(tmp_path) -> None:
    """`return set()` / `list()` / `dict()` 与空字面量等价 → 计入 return 类。"""
    counts = gate.scan(_tree_with(tmp_path, EMPTY_CONSTRUCTORS))
    assert counts["return"]["pilotstd/pkg/case.py"] == 3
