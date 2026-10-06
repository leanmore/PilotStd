"""阶段 4 · P6 · 4c：`desktop_toast` 登记与"双清单生死线"的反向验证。

覆盖两件事：
1. **登记完整性**：`desktop_toast` 已进双清单（`events.ALL_EVENTS` 与 `event_spec.EVENT_SPECS`）、
   有独立构建器与三语 i18n 键、且**归平台层口径**（`system_health` / `subscribable=False` / `task_kind=""`）；
2. **反向验证（用户点名）**：**只改一侧即导入失败**——`event_spec.py` 的模块级护栏
   `assert set(EVENT_SPEC_KEYS) == {e.key for e in ALL_EVENTS}` 必须真的会把不一致挡在导入期。
   本用例在**子进程**里制造不一致（把 `ALL_EVENTS` 去掉一项后再导入 `event_spec`）并断言进程失败，
   从而证明护栏有效；用子进程而非 `importlib.reload` 是为了**不污染**当前进程的模块状态。
"""

from __future__ import annotations

import subprocess
import sys

from pilotstd.core.notification.event_spec import EVENT_SPEC_KEYS, EVENT_SPECS
from pilotstd.core.notification.events import ALL_EVENTS


def test_desktop_toast_registered_on_both_lists() -> None:
    """双清单同时登记（只改一侧会被 `event_spec` 的导入期断言拦下）。"""
    event_keys = {e.key for e in ALL_EVENTS}
    assert "desktop_toast" in event_keys
    assert "desktop_toast" in set(EVENT_SPEC_KEYS)
    assert event_keys == set(EVENT_SPEC_KEYS)


def test_desktop_toast_spec_is_platform_layer() -> None:
    """平台层口径：归 `system_health`、不可订阅（不进用户配置入口）、非任务（`task_kind` 为空）。"""
    entry = next(s for s in EVENT_SPECS if s.key == "desktop_toast")
    assert entry.notify_event == "system_health"
    assert entry.subscribable is False
    assert entry.task_kind == ""
    assert entry.trigger_file == "pilotstd/core/notification_aggregator.py"
    assert entry.payload_keys == frozenset(), "平台层直构消息，不经 send_event ⇒ 无 payload 键"


def test_desktop_toast_has_builder_and_i18n() -> None:
    """构建器可解析（`builder_ref` 是静态指针）+ 三语 i18n 键齐备。"""
    from pilotstd.i18n import t

    entry = next(s for s in EVENT_SPECS if s.key == "desktop_toast")
    msg = entry.builder({"title": "标题", "content": "正文", "level": "warning"})
    assert msg.title == "标题"
    assert msg.level == "warning"
    assert msg.event_type == "desktop_toast"
    # 缺字段时的兜底文案（不产空标题/空正文 ⇒ G-046 的"不得空文本"）
    fallback = entry.builder({})
    assert fallback.title and fallback.blocks
    assert t("notification.system.desktop_toast.title")
    assert t("notification.system.desktop_toast.body")


def test_one_sided_change_fails_at_import() -> None:
    """**反向验证**：只改一侧（`ALL_EVENTS` 少一项）⇒ 导入 `event_spec` 必须失败。

    这是"双清单生死线"的守门人：若后来有人删掉 `event_spec.py` 的护栏断言、或把两侧改成不同步，
    本用例会红——从而避免"只登记一半"的静默不一致。
    """
    code = (
        "import importlib\n"
        "import pilotstd.core.notification.events as ev\n"
        "import pilotstd.core.notification.event_spec as es\n"
        "ev.ALL_EVENTS = [e for e in ev.ALL_EVENTS if e.key != 'desktop_toast']\n"
        "importlib.reload(es)  # 重新执行 event_spec 模块体 ⇒ 导入期护栏应在此触发\n"
        "print('SHOULD_NOT_REACH_HERE')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=None
    )
    # 只依赖**退出码**与"未走到末尾"两项事实：stderr 在受限环境里可能是 None（管道不可用），
    # 断言 stderr 文本会让用例因环境而非因逻辑变红（首轮即踩到 TypeError）。
    assert proc.returncode != 0, "只改一侧竟然导入成功 ⇒ event_spec 的护栏失效"
    assert "SHOULD_NOT_REACH_HERE" not in (proc.stdout or "")
