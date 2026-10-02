# tests/test_check_i18n_hardcoded_python.py
"""G-047（Python 侧 i18n 硬编码门禁）的受控测试。

## 测试方式

把门禁模块的 `PROJECT_ROOT` / `DEFAULT_BASELINE` 指向**临时沙箱**，再调 `main([])` ——
走**与 CI 完全相同的默认代码路径**（`collect_files([])` → `rglob` → `is_scannable` →
`find_hardcoded` → 比基线 → 退出码），**仓库零改动**（R-010：临时文件写入系统临时目录）。

## 为什么必须有负向用例

正向只能证明"能报"；必须同时证明"不乱报"，否则门禁会被 `# i18n-allow` 淹没。
**最关键的一条**：`中文注释与 docstring 必须 PASS` —— `check_g_012_comment_density.py`
**强制要求注释/docstring 用中文**，若本门禁把它们判为违规就是**自我否证**（这也是本门禁
必须走 AST 而非行级正则的原因）。

## 判别力

`TestDiscriminativePermissions` 注入三种坏形态（漏报/全放过/单元判据失效）并断言对应
用例 FAIL；`test_empty_baseline_still_blocks_new_file` 锁定"空基线 ≠ 门禁失效"
（G-040 曾因此出过 CI 红，run 36293074107）。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GATE_PATH = ROOT / "scripts" / "check_i18n_hardcoded_python.py"


def _load_gate():
    """按文件路径加载门禁模块（scripts/ 不是包，不能用常规 import）。"""
    spec = importlib.util.spec_from_file_location("check_i18n_hardcoded_python", GATE_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_i18n_hardcoded_python"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    """构造沙箱：把门禁的扫描根与基线指向 tmp_path。

    返回 `(gate, src_dir, baseline_path, run)`；`run` 调 `main([])`（默认路径）。
    """
    gate = _load_gate()
    src = tmp_path / "pilotstd"
    src.mkdir()
    baseline = tmp_path / "baseline.txt"

    monkeypatch.setattr(gate, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(gate, "DEFAULT_BASELINE", baseline)
    monkeypatch.setattr(gate, "SCAN_DIRS", ("pilotstd",))

    def run() -> int:
        return gate.main([])

    return gate, src, baseline, run


class TestBasicDetection:
    """基本判定：新增硬编码 → FAIL；干净代码 → PASS。"""

    def test_new_hardcoded_string_fails(self, sandbox):
        gate, src, baseline, run = sandbox
        baseline.write_text("", encoding="utf-8")  # 空基线
        (src / "a.py").write_text('MSG = "保存成功"\n', encoding="utf-8")
        assert run() == 1, "空基线 + 新文件含中文 → 必须 FAIL"

    def test_clean_file_passes(self, sandbox):
        gate, src, baseline, run = sandbox
        baseline.write_text("", encoding="utf-8")
        (src / "a.py").write_text('MSG = "saved"\n', encoding="utf-8")
        assert run() == 0

    def test_pure_ascii_passes(self, sandbox):
        _, src, baseline, run = sandbox
        baseline.write_text("", encoding="utf-8")
        (src / "a.py").write_text("X = 1\nY = 'abc123'\n", encoding="utf-8")
        assert run() == 0


class TestReverseGateConstraint:
    """★ 核心负向约束：中文**注释与 docstring** 必须 PASS（G-012 强制其中文）。"""

    def test_chinese_comment_passes(self, sandbox):
        _, src, baseline, run = sandbox
        baseline.write_text("", encoding="utf-8")
        (src / "a.py").write_text("# 这是中文注释\nX = 1\n", encoding="utf-8")
        assert run() == 0, "中文注释必须 PASS（G-012 强制注释用中文）"

    def test_chinese_docstring_passes(self, sandbox):
        _, src, baseline, run = sandbox
        baseline.write_text("", encoding="utf-8")
        (src / "a.py").write_text('def f():\n    """中文文档字符串。"""\n    return 1\n', encoding="utf-8")
        assert run() == 0, "中文 docstring 必须 PASS（G-012 强制 docstring 用中文）"

    def test_multiline_docstring_passes(self, sandbox):
        _, src, baseline, run = sandbox
        baseline.write_text("", encoding="utf-8")
        (src / "a.py").write_text(
            'def f():\n    """第一行中文\n\n    第二行中文\n    """\n    return 1\n', encoding="utf-8"
        )
        assert run() == 0, "跨行 docstring 的**全部行**都必须被排除"

    def test_module_docstring_passes(self, sandbox):
        _, src, baseline, run = sandbox
        baseline.write_text("", encoding="utf-8")
        (src / "a.py").write_text('"""模块中文说明。"""\nX = 1\n', encoding="utf-8")
        assert run() == 0

    def test_code_string_after_docstring_still_reported(self, sandbox):
        """★ 判别力：docstring 排除**不得**顺带放过紧随其后的普通字符串。"""
        _, src, baseline, run = sandbox
        baseline.write_text("", encoding="utf-8")
        (src / "a.py").write_text(
            'def f():\n    """中文文档字符串。"""\n    return "中文值"\n', encoding="utf-8"
        )
        assert run() == 1, "docstring 之后的中文字符串必须仍被报出"


class TestAllowMarker:
    """`# i18n-allow` 行内豁免：本行或上一行。"""

    def test_same_line_allow_passes(self, sandbox):
        _, src, baseline, run = sandbox
        baseline.write_text("", encoding="utf-8")
        (src / "a.py").write_text('X = "中文"  # i18n-allow 理由\n', encoding="utf-8")
        assert run() == 0

    def test_previous_line_allow_passes(self, sandbox):
        _, src, baseline, run = sandbox
        baseline.write_text("", encoding="utf-8")
        (src / "a.py").write_text('# i18n-allow 理由\nX = "中文"\n', encoding="utf-8")
        assert run() == 0

    def test_without_allow_fails(self, sandbox):
        """判别力：去掉标记后必须转为 FAIL（证明豁免是标记带来的，而非漏报）。"""
        _, src, baseline, run = sandbox
        baseline.write_text("", encoding="utf-8")
        (src / "a.py").write_text('X = "中文"\n', encoding="utf-8")
        assert run() == 1


class TestBaselineMechanism:
    """基线：超出才报；低于仅提示；**空基线不等于失效**。"""

    def test_within_baseline_passes(self, sandbox):
        _, src, baseline, run = sandbox
        (src / "a.py").write_text('A = "甲"\nB = "乙"\n', encoding="utf-8")
        baseline.write_text("pilotstd/a.py::2\n", encoding="utf-8")
        assert run() == 0

    def test_exceeding_baseline_fails(self, sandbox):
        _, src, baseline, run = sandbox
        (src / "a.py").write_text('A = "甲"\nB = "乙"\nC = "丙"\n', encoding="utf-8")
        baseline.write_text("pilotstd/a.py::2\n", encoding="utf-8")
        assert run() == 1, "超出基线 1 处 → 必须 FAIL"

    def test_below_baseline_passes(self, sandbox):
        """低于基线：仅 `[STALE]` 提示，**不阻断**。"""
        _, src, baseline, run = sandbox
        (src / "a.py").write_text('A = "甲"\n', encoding="utf-8")
        baseline.write_text("pilotstd/a.py::5\n", encoding="utf-8")
        assert run() == 0

    def test_empty_baseline_still_blocks_new_file(self, sandbox):
        """★ 回归护栏：**空基线 ≠ 门禁失效**（G-040 曾因此出过 CI 红 run 36293074107）。"""
        _, src, baseline, run = sandbox
        baseline.write_text("", encoding="utf-8")
        (src / "brand_new.py").write_text('X = "新写的中文"\n', encoding="utf-8")
        assert run() == 1, "空基线下新文件含中文必须 FAIL"

    def test_missing_baseline_file_still_blocks(self, sandbox):
        """基线文件不存在（未生成）→ 同样必须拦，而非静默放过。"""
        _, src, _baseline, run = sandbox
        (src / "a.py").write_text('X = "中文"\n', encoding="utf-8")
        assert run() == 1

    def test_update_baseline_then_passes(self, sandbox):
        gate, src, baseline, run = sandbox
        (src / "a.py").write_text('X = "中文"\n', encoding="utf-8")
        assert run() == 1
        assert gate.main(["--update-baseline"]) == 0
        assert run() == 0, "--update-baseline 后应 PASS"


class TestScopeExclusions:
    """扫描面与排除规则（含 G-040 的缺口：显式文件参数也要过滤）。"""

    def test_non_python_not_scanned(self, sandbox):
        _, src, baseline, run = sandbox
        baseline.write_text("", encoding="utf-8")
        (src / "a.json").write_text('{"k": "中文"}\n', encoding="utf-8")
        assert run() == 0

    def test_pycache_excluded(self, sandbox):
        gate, src, baseline, run = sandbox
        baseline.write_text("", encoding="utf-8")
        cache = src / "__pycache__"
        cache.mkdir()
        (cache / "a.py").write_text('X = "中文"\n', encoding="utf-8")
        assert run() == 0

    def test_tests_dir_excluded(self, sandbox):
        gate, src, baseline, run = sandbox
        baseline.write_text("", encoding="utf-8")
        t = src / "tests"
        t.mkdir()
        (t / "a.py").write_text('X = "中文"\n', encoding="utf-8")
        assert run() == 0

    def test_explicit_target_also_filtered(self, sandbox):
        """★ 补 G-040 的缺口：**显式文件参数**也须过 `is_scannable`。

        G-040 的 `collect_files()` 对显式文件跳过 `is_scannable()`，使
        `check_i18n_hardcoded.py foo.py` 会真的扫 `.py`。本门禁不得继承该缺口。
        """
        gate, src, baseline, run = sandbox
        baseline.write_text("", encoding="utf-8")
        f = src / "a.py"
        f.write_text('X = "中文"\n', encoding="utf-8")
        assert gate.main([str(f)]) == 1, "显式目标含中文 → 应 FAIL"
        jsonf = src / "b.json"
        jsonf.write_text('{"k": "中文"}\n', encoding="utf-8")
        assert gate.main([str(jsonf)]) == 0, "显式目标非 .py → 应被 is_scannable 过滤掉、PASS"


class TestReportMode:
    """`--report` 只统计不判失败。"""

    def test_report_returns_zero_despite_hardcoded(self, sandbox):
        gate, src, baseline, run = sandbox
        baseline.write_text("", encoding="utf-8")
        (src / "a.py").write_text('X = "中文"\n', encoding="utf-8")
        assert gate.main(["--report"]) == 0, "--report 不判失败"


class TestRepositoryBaseline:
    """真实仓库：基线必须完整（首次运行 PASS）。"""

    def test_repo_baseline_is_complete(self):
        """★ 批次⑤的交付判据：对本仓库全量运行必须 **PASS**。

        若基线生成不全（扫描口径与写基线口径不一致）→ 首次运行即 FAIL，本用例捕获该问题。
        """
        gate = _load_gate()
        assert gate.DEFAULT_BASELINE.is_file(), "基线文件必须已生成并入库"
        assert gate.main([]) == 0, "仓库基线必须完整（PASS）"

    def test_repo_baseline_covers_all_hits(self):
        """基线中的文件集合 = 实际命中的文件集合（无遗漏、无多余条目）。"""
        gate = _load_gate()
        hits = gate.scan(gate.collect_files([]))
        baseline = gate.load_baseline(gate.DEFAULT_BASELINE)
        assert set(baseline) == set(hits), (
            f"基线文件集合与实际命中不一致：仅基线有 {sorted(set(baseline) - set(hits))[:5]}；"
            f"仅实际有 {sorted(set(hits) - set(baseline))[:5]}"
        )
        for name, rows in hits.items():
            assert baseline[name] >= len(rows), f"{name} 实际 {len(rows)} 处 > 基线 {baseline[name]}"
