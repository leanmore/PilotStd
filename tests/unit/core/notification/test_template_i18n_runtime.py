# tests/unit/core/notification/test_template_i18n_runtime.py
"""模板硬编码 Tier1 修复回归。

两个缺陷类别：
1. 模块级 `t()` 求值把语言固化在 import 时刻 → 运行时 set_language 后失效；
2. 用 `t(...)` 的展示文案参与逻辑比较 → en/zh_TW 下判定漂移。
"""

from __future__ import annotations

import pytest

from pilotstd.core.notification._builders_batch import (
    _build_announcement_fetch_complete_message,
    _std_type_text,
)
from pilotstd.core.notification._builders_system import _build_task_execution_failed_message
from pilotstd.core.notification._builders_validity import _build_standard_status_changed_message
from pilotstd.core.notification._format_utils import is_abolished_status
from pilotstd.i18n import get_language, set_language


def _text(msg) -> str:
    """把消息的 title 与各 block 的可见字段摊平成文本，便于断言渲染内容。"""
    parts = [msg.title]
    for block in msg.blocks:
        for attr in ("text", "label", "old_value", "new_value", "title"):
            value = getattr(block, attr, None)
            if isinstance(value, str) and value:
                parts.append(value)
    return "\n".join(parts)


@pytest.fixture(autouse=True)
def _restore_language():
    """用例结束后恢复原语言（与 conftest 的 i18n 隔离同源）。"""
    before = get_language()
    yield
    set_language(before)


class TestStdTypeLabelRuntimeI18n:
    def test_follows_language_switch(self):
        """语言切换后标准类型名必须跟着变（import 期求值会两次返回同一值）。"""
        set_language("zh_CN")
        zh = _std_type_text("NationalStd")
        set_language("en")
        en = _std_type_text("NationalStd")
        assert zh and en
        assert zh != en

    def test_unknown_type_is_empty(self):
        assert _std_type_text("Unknown") == ""
        assert _std_type_text("") == ""


class TestTaskNameRuntimeI18n:
    def test_follows_language_switch(self):
        """任务名映射同样必须在调用期取 t()。"""
        set_language("zh_CN")
        zh = _text(_build_task_execution_failed_message({"task_name": "auto_scan", "error": "x"}))
        set_language("en")
        en = _text(_build_task_execution_failed_message({"task_name": "auto_scan", "error": "x"}))
        assert zh != en

    def test_unknown_job_id_falls_back_to_raw_name(self):
        msg = _build_task_execution_failed_message({"task_name": "some_new_job", "error": "x"})
        assert "some_new_job" in _text(msg)


class TestAbolishedStatusUsesDataToken:
    def test_token_membership(self):
        assert is_abolished_status("废止")
        assert is_abolished_status("已废止")
        assert is_abolished_status("作废")
        assert is_abolished_status("被代替")
        assert not is_abolished_status("现行")
        assert not is_abolished_status("")

    def test_level_warning_under_english(self):
        """en 下也必须判出废止 → warning；旧实现比较 t(...) 展示文案，恒为 info。"""
        set_language("en")
        msg = _build_standard_status_changed_message(
            {"standard_number": "GB/T 1-2020", "old_status": "x", "new_status": "废止"}
        )
        assert msg.level == "warning"

    def test_level_info_for_current_status(self):
        msg = _build_standard_status_changed_message(
            {"standard_number": "GB/T 1-2020", "old_status": "x", "new_status": "现行"}
        )
        assert msg.level == "info"


class TestAnnouncementFetchCompleteTitles:
    def test_no_titles_means_no_list_header(self):
        """新增 0 条时不得出现明细列表头（掩耳盗铃修复）。"""
        msg = _build_announcement_fetch_complete_message(
            {"count": 0, "source": "定时", "announcements": []}
        )
        assert "本次新增公告" not in _text(msg)

    def test_titles_render_with_header(self):
        msg = _build_announcement_fetch_complete_message(
            {
                "count": 1,
                "source": "定时",
                "announcements": [{"announce_no": "2026年第31号", "title": "公告甲"}],
            }
        )
        rendered = _text(msg)
        assert "本次新增公告" in rendered
        assert "公告甲" in rendered
