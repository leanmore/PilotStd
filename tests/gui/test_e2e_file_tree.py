# tests/gui/test_e2e_file_tree.py
"""E2E 测试 — FileTreeHandler。

FileTreeHandler 不在 MainWindowCore 中初始化。
文件树操作由 MainWindow 的 _file_tree_ops.py 直接处理
（旧 Mixin 路径，尚未迁移到 Handler 组合模式）。

跳过独立 E2E 测试：文件树交互由 test_file_tree.py 间接覆盖。
"""

from __future__ import annotations

import pytest


@pytest.mark.e2e
@pytest.mark.skip(
    reason="FileTreeHandler 不在 MainWindowCore 中（_file_tree_ops.py 旧路径）。"
    "文件树操作由 test_file_tree.py 覆盖。"
)
def test_file_tree_handler_not_in_core(window, qtbot):
    pass
