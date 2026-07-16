# tests/gui/test_e2e_table.py
"""E2E 测试 — TableHandler。

TableHandler 不在 MainWindowCore 中初始化。
表格列可见性/导出等操作由 MainWindow 的 _table_ops.py 直接处理
（旧 Mixin 路径，尚未迁移到 Handler 组合模式）。

跳过独立 E2E 测试：表格操作由 test_table.py 间接覆盖。
"""

from __future__ import annotations

import pytest


@pytest.mark.e2e
@pytest.mark.skip(
    reason="TableHandler 不在 MainWindowCore 中（_table_ops.py 旧路径）。"
    "表格操作由 test_table.py 覆盖。"
)
def test_table_handler_not_in_core(window, qtbot):
    pass
