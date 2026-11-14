"""G-050 静默吞错棘轮门禁的受控测试（体检 D-8/D-9/D-10）。

覆盖：三类识别、超基线阻断、基线可收紧告警、templates 排除。
"""

from __future__ import annotations

import importlib.util
import json
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


# ── E2-batch2：scripts/ 纳入 + archive 排除 ─────────────────────────────

_SIMPLE_PASS = "try:\n    pass\nexcept Exception:\n    pass\n"


def _tree_at(tmp_path: Path, rel: str, code: str) -> Path:
    target = tmp_path / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(code, encoding="utf-8")
    return tmp_path


def test_scripts_dir_is_scanned(tmp_path) -> None:
    """scripts/ 下的 `except: pass` 必须计入（门禁自身也要受棘轮保护）。"""
    counts = gate.scan(_tree_at(tmp_path, "scripts/tool.py", _SIMPLE_PASS))
    assert counts["pass"]["scripts/tool.py"] == 1


def test_scripts_archive_is_excluded(tmp_path) -> None:
    """scripts/archive/ 是历史探针，按前缀排除，不计入。"""
    counts = gate.scan(_tree_at(tmp_path, "scripts/archive/old_probe.py", _SIMPLE_PASS))
    assert "scripts/archive/old_probe.py" not in counts["pass"]


# ── 基线口径自证：`_meta` 必须与三档合计一致（防止改了计数却不同步口径）──────


def test_baseline_meta_matches_counts() -> None:
    """`silent_errors_baseline.json` 的 `_meta` 是三档计数的口径声明，必须自洽。

    门禁本身只比较 pass/return/debug 三档（`compare()`），`_meta` 不参与判定；
    但它是"162 到底是什么"的唯一书面口径（迁移冻结 40 + 已 triage allowlist 122），
    所以用测试钉住：任何人改计数不同步 `_meta` 即红。
    """
    baseline = json.loads(gate.BASELINE.read_text(encoding="utf-8"))
    meta = baseline["_meta"]
    sums = {kind: sum(baseline[kind].values()) for kind in ("pass", "return", "debug")}
    assert meta["tiers"] == sums, meta["tiers"]
    assert meta["total"] == sum(sums.values()), meta["total"]
    assert meta["migration_frozen"] + meta["triaged_allowlist"] == meta["total"]


def test_review_due_overdue_only_warns(tmp_path, monkeypatch, capsys) -> None:
    """`_meta.review_due` 过期 → 只打 WARN，退出码仍 0（软提醒，不阻断 CI）。"""
    baseline = {"_meta": {"review_due": "2020-01-01"}, "pass": {}, "return": {}, "debug": {}}
    bpath = tmp_path / "baseline.json"
    bpath.write_text(json.dumps(baseline), encoding="utf-8")
    monkeypatch.setattr(gate, "BASELINE", bpath)
    scan_root = tmp_path / "scan"
    scan_root.mkdir()

    rc = gate.main(["--root", str(scan_root)])

    out = capsys.readouterr().out
    assert rc == 0
    assert "G-050 基线待复审" in out
    assert "review_due=2020-01-01" in out
