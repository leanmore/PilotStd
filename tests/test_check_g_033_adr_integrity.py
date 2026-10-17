"""tests/test_check_g_033_adr_integrity.py — G-033 ADR 编号唯一性断言的受控测试。

覆盖：
  1. 真实仓库 ADR 编号唯一（无重复）；
  2. 造两个同号文件 → 被检出为重复；
  3. 重号即使"无架构变更"也 FAIL（旧逻辑会走跳过分支，故断言先行）；
  4. 干净临时树 → validate_adr 通过；
  5. 真实仓库 CLI → exit 0。
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check_g_033_adr_integrity.py"


def _load_module():
    """以文件路径加载门禁脚本模块（scripts/ 不是包）。"""
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("check_g_033_adr_integrity", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_adr(directory: Path, name: str) -> None:
    """写一个状态可被 parse_adr_status 识别为有效的 ADR 文件。"""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(
        f"# {name}\n\n- 状态：Accepted\n", encoding="utf-8"
    )


def test_real_tree_numbers_are_unique() -> None:
    """真实 docs/adr/ 中每个 ADR-0NN 只对应一个文件。"""
    gate = _load_module()
    assert gate.find_duplicate_adr_numbers() == {}


def test_duplicate_number_is_detected(tmp_path: Path) -> None:
    """同号两个文件 + 一个正常文件 → 只报同号那组。"""
    gate = _load_module()
    _write_adr(tmp_path, "ADR-008-alpha.md")
    _write_adr(tmp_path, "ADR-008-beta.md")
    _write_adr(tmp_path, "ADR-009-gamma.md")

    duplicates = gate.find_duplicate_adr_numbers(tmp_path)

    assert list(duplicates) == ["008"]
    assert duplicates["008"] == ["ADR-008-alpha.md", "ADR-008-beta.md"]


def test_duplicate_fails_even_without_arch_changes(tmp_path: Path, capsys) -> None:
    """重号在 git diff 为空时也必须 FAIL（这是旧门禁的缺口）。"""
    gate = _load_module()
    _write_adr(tmp_path, "ADR-008-alpha.md")
    _write_adr(tmp_path, "ADR-008-beta.md")
    gate.get_changed_files = lambda: []

    assert gate.validate_adr(tmp_path) is False

    out = capsys.readouterr().out
    assert "编号唯一性校验失败" in out
    assert "ADR-008" in out


def test_clean_tree_passes(tmp_path: Path) -> None:
    """编号唯一 + 有有效 ADR → 通过。"""
    gate = _load_module()
    _write_adr(tmp_path, "ADR-001-only.md")
    gate.get_changed_files = lambda: ["docs/adr/ADR-001-only.md"]

    assert gate.validate_adr(tmp_path) is True


def test_parse_adr_status_accepts_list_item_bold_format() -> None:
    """ADR 的实际 Status 写法是列表项 + 加粗 ⇒ 必须能解析（2026-10-17 修正）。

    回归：原正则集只有 `## Status` / `**Status**:` / `状态：` / `> **状态**：`，
    而真实文件写 `- **状态**：✅ Accepted`——中间夹着 `**` 使 `状态[：:]` 匹配不到、
    `>` 分支又只认引用块 ⇒ ADR-001/009/010/017 被误判"无法解析 Status、视为无效"
    （有效 ADR 被少算 4 个）。
    """
    gate = _load_module()
    assert gate.parse_adr_status("- **状态**：✅ Accepted\n") is not None, "列表项加粗写法必须可解析"
    assert gate.parse_adr_status("* **状态**：Accepted\n") == "accepted"
    # 引用块写法仍要兼容（既有分支）
    assert gate.parse_adr_status("> **状态**：Deprecated\n") == "deprecated"
    # 真正解析不到时仍返回 None（不得因放宽而"什么都能过"）
    assert gate.parse_adr_status("本文没有状态字段\n") is None


def test_cli_real_tree_exit_zero() -> None:
    """真实仓库跑 CLI → exit 0。"""
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
