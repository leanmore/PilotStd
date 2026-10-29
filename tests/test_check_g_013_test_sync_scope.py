"""G-013 的检查范围与测试同步判据（体检 D-6，2026-10-17）。

两个缺陷：
1. `is_business_file()` 把 git 路径**第一段**与 `BUSINESS_DIRS` 比较，而路径是
   `pilotstd/manager/...` ⇒ `pilotstd/` 下所有业务代码**从未被检查过**；
   白名单还缺 `docker` 与 `scan`。
2. 测试映射按 `tests/<父目录>/test_<文件名>.py` 推导，而本仓库测试按功能命名：
   实测 60 次提交里精确映射命中 **0/16**（docker 0/60），必然常红 ⇒ 改为
   "tests/ 下任一测试变更"（14/16 通过，剩余 2 例是改公开 API 却完全没动测试的真阳性）。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check_g_013_test_coverage.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_g_013_test_coverage", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = _load()


def test_pilotstd_business_dirs_are_recognized() -> None:
    """核心缺陷：pilotstd/ 下的业务文件过去全部被判为非业务文件。"""
    assert gate.is_business_file("pilotstd/manager/facade/_organize.py") is True
    assert gate.is_business_file("pilotstd/core/db/database.py") is True
    assert gate.is_business_file("pilotstd/scan/scanner.py") is True


def test_docker_and_scan_are_business_dirs() -> None:
    assert gate.is_business_file("docker/api/download.py") is True
    assert gate.is_business_file("docker/api/test_download.py") is False
    assert gate.is_business_file("tests/test_download.py") is False


def test_any_test_change_satisfies() -> None:
    assert gate.has_test_sync(["tests/test_download.py"]) is True
    assert gate.has_test_sync(["tests/unit/core/notification/test_x.py"]) is True
    assert gate.has_test_sync(["docs/index.md"]) is False


def test_test_file_detection_requires_tests_dir() -> None:
    """文件名含 test 的脚本不算测试（否则规则 0 与规则 1 都会被架空）。"""
    assert gate.is_test_file("tests/test_x.py") is True
    assert gate.is_test_file("scripts/check_g_013_test_coverage.py") is False


def test_frontend_vitest_counts_as_test_change() -> None:
    """B5/A-19：web/src 下的 .test.ts 也算测试变更，前端修复可用 fix 类型。"""
    assert gate.is_test_file("web/src/views/SettingsView.test.ts") is True
    assert gate.is_test_file("web/src/views/SettingsView.vue") is False
