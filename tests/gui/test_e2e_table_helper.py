# tests/gui/test_e2e_table_helper.py
"""E2E 测试 — TableHelperHandler。

TableHelperHandler 不在 MainWindowCore 中初始化。
右键菜单/行操作/列宽管理等由 _table_ops.py 直接处理
（旧 Mixin 路径，尚未迁移到 Handler 组合模式）。

跳过独立 E2E 测试。
"""

from __future__ import annotations

import pytest


@pytest.mark.e2e
@pytest.mark.skip(
    reason="TableHelperHandler 不在 MainWindowCore 中（_table_ops.py 旧路径）。"
)
def test_table_helper_handler_not_in_core(window, qtbot):
    pass
