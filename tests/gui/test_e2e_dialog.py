# tests/gui/test_e2e_dialog.py
"""E2E 测试 — DialogHandler。

DialogHandler 不在 MainWindowCore 中初始化。
其方法（question_dlg / stage_prereq_dialog / show_stage_dialog / register_task）
均作为回调注入其他 Handler（如 QueryUIHandler、ArchiveUIHandler），
通过 self._deps.dialog.xxx() 间接调用。

独立实例化需要完整的 _parent / _config / _mgr 上下文，
跳过独立 E2E 测试：DialogHandler 的行为由其他 Handler 的 E2E 测试间接覆盖。
"""

from __future__ import annotations

import pytest


@pytest.mark.e2e
@pytest.mark.skip(
    reason="DialogHandler 不在 MainWindowCore 中（方法通过回调注入其他 Handler）。"
    "其行为由 test_e2e_query / test_e2e_scan 等测试间接覆盖。"
)
def test_dialog_handler_not_in_core(window, qtbot):
    pass
