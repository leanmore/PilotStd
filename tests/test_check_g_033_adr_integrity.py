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
