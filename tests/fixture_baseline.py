"""tests/fixture_baseline.py — fixture 基线登记与守卫覆盖率（T-20 / R11-4，2026-09-27）。

R11-4 实测结论（已写入主簿 T-20）：
  ① `tests/` 里 `self.skipTest("Fixture not found…")` 有 **43 个静态调用点**（分布在 7 个测试文件）；
  ② 它们依赖的 **15 个 fixture 文件全部已入库**（`tests/fixtures/`），因此运行期**一次也不会触发**；
  ③ 所以「60 处 skipTest」是**静态口径**，运行期真实跳过数为 **14（本地）/ 44（CI）**。

本模块把「哪个测试文件依赖哪些 fixture」显式登记，并提供两条判定：
  · `missing_fixtures()` —— 登记的 fixture 里哪些真的缺失或为空（只有缺失才会触发那些守卫）；
  · `uncovered_guards()` —— 源码里的 fixture 守卫哪些**未被登记**（新增测试若引入缺 fixture 的守卫，此处立刻暴露）。

用途：T-20「可治理部分识别」的基线。本模块**只做识别与登记**，不做任何 skip 的批量删除或替换。
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
FIXTURE_DIR = TESTS_DIR / "fixtures"
REPO_ROOT = TESTS_DIR.parent

# ── 登记表：测试文件 → fixture 文件（相对 tests/fixtures/） ──────────────────────


@dataclass(frozen=True)
class FixtureRequirement:
    """一条 fixture 依赖登记。"""

    test_file: str  # 相对仓库根的测试文件路径
    fixture: str  # 相对 tests/fixtures/ 的文件名
    purpose: str  # 用途（人类可读，便于评审时判断是否仍需要）


REQUIREMENTS: tuple[FixtureRequirement, ...] = (
    FixtureRequirement("tests/test_adapters.py", "ccsn_initial.html", "CCSN 首页（HTML 结构解析）"),
    FixtureRequirement("tests/test_adapters.py", "ccsn_search_gbt.html", "CCSN GB/T 搜索结果页"),
    FixtureRequirement("tests/test_adapters.py", "jjg_api_search.json", "JJG API 搜索响应"),
    FixtureRequirement("tests/test_adapters.py", "jtst_search_gbt_iframe.html", "JTST GB/T 搜索 iframe"),
    FixtureRequirement("tests/test_adapters.py", "mee_search_gbt.html", "MEE GB/T 搜索结果页"),
    FixtureRequirement("tests/test_adapters.py", "nrsis_search_gbt.html", "NRSIS GB/T 搜索结果页"),
    FixtureRequirement("tests/test_adapters.py", "sppt_8087_search2.html", "SPPT 8087 搜索页"),
    FixtureRequirement("tests/test_adapters.py", "sppt_api_gb2760.json", "SPPT API GB 2760 响应"),
    FixtureRequirement("tests/test_cssn.py", "cssn_sample.json", "CSSN 单条结果（_parse_result）"),
    FixtureRequirement("tests/test_energy.py", "energy_sample.json", "能源标准单条结果"),
    FixtureRequirement("tests/test_gongbiaoku.py", "gongbiaoku_free_list.html", "工标库免费列表页"),
    FixtureRequirement("tests/test_miit.py", "miit_sample.json", "MIIT 单条结果"),
    FixtureRequirement("tests/test_ncha.py", "ncha_gbt_sample.json", "NCHA GB/T 单条结果"),
    FixtureRequirement("tests/test_ncha.py", "ncha_wwt_sample.json", "NCHA 其它类单条结果"),
    FixtureRequirement("tests/test_tdpress.py", "tdpress_sample.json", "中国标准出版社单条结果"),
)

# ── 判定一：登记的 fixture 是否真的就位 ───────────────────────────────────────


def fixture_path(fixture: str) -> Path:
    """fixture 名 → 绝对路径。"""
    return FIXTURE_DIR / fixture


def missing_fixtures(requirements: tuple[FixtureRequirement, ...] = REQUIREMENTS) -> list[FixtureRequirement]:
    """返回缺失或为空的 fixture 登记项（非空即意味着对应守卫会在运行期触发）。"""

    def _absent(req: FixtureRequirement) -> bool:
        path = fixture_path(req.fixture)
        return not path.exists() or path.stat().st_size == 0

    return [r for r in requirements if _absent(r)]


def registered_test_files(requirements: tuple[FixtureRequirement, ...] = REQUIREMENTS) -> set[str]:
    """登记过的测试文件集合（相对仓库根）。"""
    return {r.test_file for r in requirements}


# ── 判定二：源码里的 fixture 守卫是否都被登记 ─────────────────────────────────


@dataclass(frozen=True)
class FixtureGuard:
    """一个 `self.skipTest("Fixture not found…")` 静态调用点。"""

    test_file: str  # 相对仓库根
    line: int
    owner: str  # 所在函数/方法名
    message: str


def _iter_test_files() -> list[Path]:
    """tests/ 下所有 `test_*.py`（跳过缓存与 fixtures 目录内的模板）。"""
    out: list[Path] = []
    for path in sorted(TESTS_DIR.rglob("test_*.py")):
        if "__pycache__" in path.parts:
            continue
        out.append(path)
    return out


def scan_guards() -> list[FixtureGuard]:
    """AST 扫描全部 fixture 守卫（消息含 fixture 字样的 `skipTest` 调用）。"""
    guards: list[FixtureGuard] = []
    for path in _iter_test_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        owners = [
            (node.lineno, node.end_lineno or node.lineno, node.name)
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (isinstance(func, ast.Attribute) and func.attr == "skipTest"):
                continue
            if not node.args or not isinstance(node.args[0], ast.Constant):
                continue
            message = str(node.args[0].value)
            if "fixture" not in message.lower():
                continue
            owner = next((name for start, end, name in owners if start <= node.lineno <= end), "")
            guards.append(FixtureGuard(rel, node.lineno, owner, message))
    return guards


def uncovered_guards() -> list[FixtureGuard]:
    """未被登记表覆盖的 fixture 守卫（空集 = 基线完整；非空 = 新增测试引入了缺 fixture 的守卫）。"""
    covered = registered_test_files()
    return [g for g in scan_guards() if g.test_file not in covered]


def baseline_report() -> dict:
    """基线汇总（供受控测试与文档引用）。"""
    guards = scan_guards()
    missing = missing_fixtures()
    uncovered = uncovered_guards()
    return {
        "requirements": len(REQUIREMENTS),
        "missing": [r.fixture for r in missing],
        "guard_sites": len(guards),
        "guarded_files": sorted({g.test_file for g in guards}),
        "registered_files": sorted(registered_test_files()),
        "uncovered": [f"{g.test_file}:{g.line}" for g in uncovered],
    }


if __name__ == "__main__":  # pragma: no cover - 人工排查入口
    import json

    print(json.dumps(baseline_report(), ensure_ascii=False, indent=2))
