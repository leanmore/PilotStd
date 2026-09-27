"""tests/test_fixture_baseline.py — fixture 基线的受控测试（T-20 / R11-4，2026-09-27）。

锁定三件事：
  ① 登记表里的每个 fixture **确实存在且非空**（存在 ⇒ 那些 `Fixture not found` 守卫运行期不触发）；
  ② 源码里的 fixture 守卫**全部被登记表覆盖**（新增测试若引入缺 fixture 的守卫，本测试立即失败）；
  ③ 静态口径的数量与 R11-4 实测一致（43 处 / 7 文件），数量变化时提示同步更新主簿 T-20。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests import fixture_baseline as fb  # noqa: E402

# R11-4 实测基线（2026-09-27）：fixture 守卫 43 处 / 7 文件；登记 fixture 15 个
BASELINE_GUARD_SITES = 43
BASELINE_GUARDED_FILES = 7


def test_all_registered_fixtures_exist_and_are_non_empty() -> None:
    """登记的 fixture 必须全部就位——缺一个就会让对应守卫在运行期触发 skip。"""
    for req in fb.REQUIREMENTS:
        path = fb.fixture_path(req.fixture)
        assert path.exists(), f"fixture 缺失: {req.fixture}（{req.test_file} 依赖）"
        assert path.stat().st_size > 0, f"fixture 为空: {req.fixture}"


def test_no_missing_fixtures() -> None:
    """missing_fixtures() 必须为空——这是「0 处因缺 fixture 而跳过」的直接判据。"""
    missing = [f"{r.test_file} → {r.fixture}" for r in fb.missing_fixtures()]
    assert missing == [], f"存在缺失 fixture: {missing}"


def test_every_fixture_guard_is_registered() -> None:
    """源码里的 fixture 守卫必须全部被登记表覆盖，防止将来悄悄引入缺 fixture 的守卫。"""
    uncovered = [f"{g.test_file}:{g.line} [{g.owner}]" for g in fb.uncovered_guards()]
    assert uncovered == [], f"存在未登记的 fixture 守卫: {uncovered}"


def test_static_guard_baseline_matches_documented_numbers() -> None:
    """静态守卫数量与主簿 T-20 记录一致（变化时须同批更新主簿）。"""
    report = fb.baseline_report()
    assert report["guard_sites"] == BASELINE_GUARD_SITES, (
        f"fixture 守卫数由 {BASELINE_GUARD_SITES} 变为 {report['guard_sites']}；请同步主簿 T-20 与常量"
    )
    assert len(report["guarded_files"]) == BASELINE_GUARDED_FILES, (
        f"含 fixture 守卫的文件数由 {BASELINE_GUARDED_FILES} 变为 {len(report['guarded_files'])}"
    )


def test_registry_covers_all_guarded_files() -> None:
    """登记表的文件集合 ⊇ 出现守卫的文件集合（反向多余登记也提示出来）。"""
    reported = fb.baseline_report()
    guarded = set(reported["guarded_files"])
    registered = set(reported["registered_files"])
    assert guarded <= registered, f"有守卫但未登记的文件: {sorted(guarded - registered)}"
