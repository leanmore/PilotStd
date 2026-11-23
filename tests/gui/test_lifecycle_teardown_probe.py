"""tests/test_lifecycle_teardown_probe.py — teardown 存活探测的容错（2026-11-23）。

背景：NEW-39 在 `_window_lifecycle` 的 teardown 里加了 `sip.isdeleted(w)` 存活探测，
用于避免访问已被 `deleteLater()` 回收的 `DriveEnumerator` 包装对象。

但 `sip.isdeleted()` **只接受真正的 sip 包装对象**：
  - 传入 `MagicMock`（测试替身）→ `TypeError`
  - `sip` 不可用 → `ImportError` / `AttributeError`

CI 实测（run on 1378337b）：`test-gui-unit` 因这个 TypeError 红
（`test_coverage_final2.py::TestInitFinal::test_stop_workers_never_terminates`
的 teardown 用 MagicMock 替换 `_drive_thread`）。

修法：把 `TypeError` 一并纳入「不可探测」分支（跳过探测、继续正常清理）。

本测试用**源码结构断言**（而非运行时调用）：teardown 所在类是 Mixin，
构造它需要完整的主窗口上下文；而"是否捕获 TypeError"是纯结构问题，
源码断言更稳、更快、不会因类名/初始化变化而脆弱。
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "pilotstd" / "ui" / "main_window" / "_window_lifecycle.py"


def _source() -> str:
    return SRC.read_text(encoding="utf-8")


def test_isdeleted_probe_catches_type_error():
    """`sip.isdeleted` 探测的 except 子句必须捕获 TypeError。

    回归场景：`sip.isdeleted(MagicMock())` 抛
    `TypeError: isdeleted() argument 1 must be PyQt6.sip.simplewrapper, not MagicMock`。
    若不捕获，测试 teardown 会红（CI 实测）。
    """
    src = _source()
    idx = src.find("_sip.isdeleted(w)")
    assert idx > 0, "找不到 isdeleted 存活探测"

    # 取该 try 块之后的 except 子句（窗口 600 字符足够）
    tail = src[idx : idx + 600]
    m = re.search(r"except\s*\(([^)]*)\)", tail)
    assert m, f"isdeleted 探测后找不到 except 元组: {tail[:200]}"
    caught = m.group(1)
    assert "TypeError" in caught, (
        f"except 子句未捕获 TypeError（MagicMock 会触发）: except ({caught})"
    )


def test_isdeleted_probe_still_catches_import_errors():
    """原有的 ImportError / AttributeError 捕获不能丢（sip 不可用场景）。"""
    src = _source()
    idx = src.find("_sip.isdeleted(w)")
    assert idx > 0
    tail = src[idx : idx + 600]
    m = re.search(r"except\s*\(([^)]*)\)", tail)
    assert m
    caught = m.group(1)
    for expected in ("AttributeError", "ImportError"):
        assert expected in caught, f"except 子句丢了 {expected}: except ({caught})"


def test_probe_guarded_by_hasattr():
    """探测必须先用 hasattr 守卫（某些 sip 构建没有 isdeleted）。"""
    src = _source()
    assert 'hasattr(_sip, "isdeleted")' in src, "缺少 hasattr 守卫"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
