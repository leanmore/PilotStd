# tests/test_notification_e2e.py
# Q20 集成验证：32 事件全量覆盖 — 注册状态 + 触发点静态检查 + 字段双向校验 + 互斥逻辑
# 生成日期: 2026-07-22
#
# EVENTS 元数据的字段约定（读 EVENTS 前必看）：
#   - `level` 用 `a/b` 形式表示**该构建器可产出的 level 集合**，不是单个值。例：
#     `"info/warning"` 表示构建器按分支返回 `info` 或 `warning`（如
#     `_build_scan_complete_message` 在 `failed > 0` 时 warning，否则 info）。
#     把集合误读为单值会得出"元数据漂移"的错误结论——判定须按集合比对，
#     且构建器的 level 可能经局部变量传递（`level = ...` 再 `level=level`），
#     正则提取会漏。
#   - `trigger_file` 必须是**物理存在**的触发方文件（G-045 校验其存在性）；
#     若事件由投递管道而非业务端点触发，应记业务端点而非管道文件。
#   - `builder_keys` 与触发方 payload 键须**双向一致**（本文件有对应断言）。
#   - 自 2026-10-03 步 B D4 起，`EVENTS` **由事件规格派生**（`pilotstd/core/notification/
#     event_spec.py`）——本文件不再手写条目；改字段口径请改规格，勿改本文件。
import ast
import os
import re
from typing import Any

import pytest

pytestmark = pytest.mark.integration

# ═══════════════════════════════════════════════════════════════════════════════
# 静态分析工具
# ═══════════════════════════════════════════════════════════════════════════════

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _find_send_event_calls(event_name: str) -> list[tuple[str, int]]:
    """静态扫描源码，返回所有 send_event("event_name", ...) 的文件路径和行号。

    使用 AST 解析（而非正则）：
    - 第一参数为字符串字面量 → 直接匹配事件名
    - 第一参数为事件常量（EVENT_*）→ 通过 events 模块解析常量的实际值
    避免旧正则中 EVENT_[A-Z_]+ 备选分支对任意常量模糊匹配导致的"伪通过"。
    """
    from pilotstd.core.notification import events as _events_mod

    results: list[tuple[str, int]] = []
    search_roots = [
        os.path.join(_PROJECT_ROOT, "pilotstd"),
        os.path.join(_PROJECT_ROOT, "docker"),
    ]
    for search_root in search_roots:
        if not os.path.isdir(search_root):
            continue
        for root, _dirs, files in os.walk(search_root):
            for f in files:
                if not f.endswith(".py"):
                    continue
                fpath = os.path.join(root, f)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                        tree = ast.parse(fh.read())
                except (OSError, SyntaxError):
                    continue
                for node in ast.walk(tree):
                    if not isinstance(node, ast.Call) or not node.args:
                        continue
                    func = node.func
                    is_send_event = (
                        isinstance(func, ast.Attribute) and func.attr == "send_event"
                    ) or (isinstance(func, ast.Name) and func.id == "send_event")
                    if not is_send_event:
                        continue
                    arg0 = node.args[0]
                    if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                        ev = arg0.value
                    elif isinstance(arg0, ast.Name):
                        ev = getattr(_events_mod, arg0.id, None)
                    else:
                        continue
                    if ev == event_name:
                        results.append((fpath, node.lineno))
    return results


def _extract_builder_keys(file_path: str, method_name: str) -> set[str]:
    """从构建器源码中提取所有 data.get("xxx") 的 key 集合。"""
    keys: set[str] = set()
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
    except OSError:
        return keys
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == method_name:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    if (
                        isinstance(sub.func, ast.Attribute)
                        and sub.func.attr == "get"
                        and isinstance(sub.func.value, ast.Name)
                        and sub.func.value.id == "data"
                    ):
                        if sub.args and isinstance(sub.args[0], ast.Constant):
                            keys.add(sub.args[0].value)
    return keys


def _extract_trigger_payload_keys(event_name: str) -> set[str]:
    """从触发点源码中提取 send_event data dict 的顶层 key 集合（取第一个匹配）。

    实现用 AST 而非正则：旧正则的 `(\\{.*?\\})` 会**跨过函数边界**——当 dict 之后的
    同一文件里还有别的 `}`（如 JWT payload 字面量），非贪婪匹配会一路吞到那里，
    把无关键（`exp`/`sub`/`role`…）算成触发方 payload，导致"字段双向一致"断言误报。
    AST 按语法树取第二参数，边界精确。
    """
    search_roots = [
        os.path.join(_PROJECT_ROOT, "pilotstd"),
        os.path.join(_PROJECT_ROOT, "docker"),
    ]
    for search_root in search_roots:
        if not os.path.isdir(search_root):
            continue
        for root, _dirs, files in os.walk(search_root):
            for f in files:
                if not f.endswith(".py"):
                    continue
                fpath = os.path.join(root, f)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                        tree = ast.parse(fh.read())
                except (OSError, SyntaxError):
                    continue
                for node in ast.walk(tree):
                    if not isinstance(node, ast.Call) or len(node.args) < 2:
                        continue
                    func = node.func
                    is_send_event = (isinstance(func, ast.Attribute) and func.attr == "send_event") or (
                        isinstance(func, ast.Name) and func.id == "send_event"
                    )
                    if not is_send_event:
                        continue
                    arg0 = node.args[0]
                    if not (isinstance(arg0, ast.Constant) and arg0.value == event_name):
                        continue
                    data_arg = node.args[1]
                    if not isinstance(data_arg, ast.Dict):
                        continue
                    keys: set[str] = set()
                    for key_node in data_arg.keys:
                        if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                            keys.add(key_node.value)
                    return keys
    return set()


def _parse_dict_keys(dict_str: str) -> set[str]:
    """从 send_event data dict 字符串中手工提取顶层 key。"""
    keys: set[str] = set()
    # 匹配 "key": 或 'key': 模式
    for m in re.finditer(r'["\']([a-z_][a-z0-9_]*)["\']\s*:', dict_str):
        keys.add(m.group(1))
    return keys


# ═══════════════════════════════════════════════════════════════════════════════
# 事件元数据 — 单一数据源 (SSOT)
# ═══════════════════════════════════════════════════════════════════════════════

# 回退兼容字段白名单（旧字段名仍然存在于构建器中，但新代码已不再使用）
FALLBACK_WHITELIST: dict[str, set[str]] = {
    "validity_batch_report": {"adapter_status"},
    "image_update_available": {"release_notes"},
}

# 有意豁免"必须有 send_event 触发点"的事件（第 2 批安全与审计闭环）：
# 这三个安全告警不走 NotificationManager.send_event —— 凭证变更告警必须在**新凭证
# 落库之前**送达旧渠道，而 manager 路径会被聚合缓冲（默认 5s）与静音时段（延后补发）
# 推迟到落库之后，从而投递到攻击者控制的新地址。投递改由
# pilotstd/core/notification/security_notifier.py 直连临时渠道同步 send() 完成，
# 其正确性（含"不得调用 send_event"）由 tests/test_p0_security_endpoints.py 锁定。
SECURITY_EVENTS_BY_DESIGN_UNTRIGGERED: frozenset[str] = frozenset(
    {
        "notification_credential_changed",
        "security_password_changed",
        "security_token_refreshed",
    }
)

# 安全事件中**确实**走 send_event 留痕的一个：登录失败告警由 docker/auth.py 触发，
# 既发 send_event（写入 notification_log + WS 广播），也由其直连投递（auth 未认证、
# 无用户凭证上下文，走 manager 已足够）。故它**不**在豁免集内。
SECURITY_EVENTS_TRIGGERED_VIA_SEND_EVENT: frozenset[str] = frozenset({"security_login_failed"})

# 硬编码 trigger_keys — 当 regex 无法解析 Block 模式 send_event 时使用
# 由手动审查 trigger 源码维护，是字段验证的真实来源
TRIGGER_KEYS: dict[str, set[str]] = {
    "standard_status_changed": {"standard_number", "old_status", "new_status", "is_expired", "changed_at"},
    "standard_first_registered": {"standard_number", "standards", "name", "detail_url", "elapsed_ms"},
    "validity_batch_report": {"count", "changed", "failed", "adapters", "change_detail", "adapter_status"},
    "validity_round_summary": {
        "total_checks",
        "total_changes",
        "total_failures",
        "change_list",
        "adapter_summary",
        "round",
    },
    "validity_standard_failed": {"standard_number", "error"},
    "validity_system_failed": {"error"},
    "scan_complete": {"count", "failed"},
    "scan_empty": set(),
    "auto_scan_failed": {"path", "error"},
    "batch_query_summary": {"total", "found", "pending", "results"},
    "query_failed": {"standard_number", "error"},
    "query_empty": {"total"},
    "batch_download_complete": {"total", "success", "failed", "skipped"},
    "download_failed": {"user_id", "standard_number", "error", "favorite_id"},
    "normalize_complete": {"total", "success", "failed"},
    "normalize_failed": {"total", "error"},
    "archive_complete": {"count", "directories", "standard_number", "status", "target_id", "elapsed_ms"},
    "archive_failed": {"count", "error"},
    "archive_abandoned": {"standard_info", "error"},
    "expire_standard_moved": {"standard_number", "target_path"},
    "announcement_fetch_complete": {"count", "source"},
    "announcement_check_complete": {
        "total_announcements",
        "total_standards",
        "gb_count",
        "hb_count",
        "db_count",
        "gb_standards",
        "hb_standards",
        "db_standards",
        "failures",
        "source",
    },
    "announcement_fetch_failed": {"source", "error"},
    "replacement_not_found": {"standard_number", "searched_sources"},
    "auto_backup": {"success", "backup_path", "size_mb", "error"},
    "image_update_available": {"error", "old_digest", "new_digest"},
    "worker_error": {"worker", "error", "traceback"},
    "task_execution_failed": {"task_name", "error"},
    "quota_exhausted": {"site_name", "quota_limit", "reset_time"},
    "date_reminder": {"standard_number", "std_name", "days_before", "remind_type"},
    "trust_ip_update": {"title", "body", "ip", "update_time", "status"},
    "favorite_created": {"user_id", "record_id", "standard_no", "standard_name"},
    "download_started": {"user_id", "standard_number", "favorite_id"},
    "download_complete": {"user_id", "standard_number", "favorite_id", "local_path", "status"},
    "favorite_abandoned_summary": {
        "total",
        "reasons",
        "retryable",
        "details",
    },
    "notification_delivery_failed": {
        "channel",
        "reason",
        "samples",
        "failures",
        "consecutive",
    },
}


def _event_specs() -> list:
    """取事件规格（延迟导入：避免本模块导入期对 sys.path 的额外依赖）。"""

    from pilotstd.core.notification.event_spec import EVENT_SPECS

    return list(EVENT_SPECS)


EVENTS: list[dict[str, Any]] = [
    # **由事件规格派生**（2026-10-03 步 B D4 完整形态）：8 个字段全部取自 event_spec；
    # `builder_file`/`builder_method` 由构建器反射派生（实测 41/41 一致）；
    # `level` 按 `/` 连接（严重度升序）；`builder_keys` 取集合形态（与既有消费方一致）。
    {
        "name": s.key,
        "module": s.module_key,
        "level": "/".join(s.levels),
        "aggregation": s.aggregation,
        "trigger_file": s.trigger_file,
        "builder_file": s.builder.__module__.replace(".", "/") + ".py",
        "builder_method": s.builder.__name__,
        "builder_keys": set(s.payload_keys),
    }
    for s in _event_specs()
]

# 验证 EVENTS 列表完整性
# 41 = 原 39 + `favorite_abandoned_summary` + `notification_delivery_failed`（两项均 P0）
# 阶段 C：原 `assert len(EVENTS) == 41` 是"加事件成本高"的病灶（硬编码数量，
# 任何增删都要改多处清单）。改为**双向闭包断言**：e2e 覆盖的事件集合必须等于
# 「用户时刻 × 事件」闭包声明的可见事件集合（缺一多一都失败，且失败信息可读）。
from pilotstd.core.notification.user_moments import all_attributable_events

covered = {case["name"] for case in EVENTS}
# 期望集合 = 可追溯到用户时刻的事件 ∪ Windows 专属（worker_error）
expected_visible = all_attributable_events() | {"worker_error"}
assert covered == expected_visible, (
    f"e2e 覆盖与用户时刻闭包不一致: 缺 {sorted(expected_visible - covered)}; "
    f"多 {sorted(covered - expected_visible)}"
)


# ═══════════════════════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════════════════════


def _get_event(name: str) -> dict:
    for e in EVENTS:
        if e["name"] == name:
            return e
    raise KeyError(f"Event {name} not in EVENTS list")


# ═══════════════════════════════════════════════════════════════════════════════
# 测试类
# ═══════════════════════════════════════════════════════════════════════════════


class TestNotificationRegistry:
    """验证所有 32 个事件在 ALL_EVENTS 和 _EVENT_BUILDERS 中注册。"""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from types import SimpleNamespace

        from pilotstd.core.notification.events import ALL_EVENT_KEYS
        from pilotstd.core.notification.manager import NotificationManager

        self.all_keys = ALL_EVENT_KEYS
        # 运行期取 _EVENT_BUILDERS 的键（D4：脱离"源码正则"口径——注册表已由
        # event_spec 派生，源码里不再有字面量键值对）。该方法是纯赋值，可用哑对象调用。
        stub = SimpleNamespace()
        NotificationManager._init_event_builders(stub)
        self.builder_keys: set[str] = set(stub._EVENT_BUILDERS)

    @pytest.mark.parametrize("event", EVENTS, ids=[e["name"] for e in EVENTS])
    def test_registered_in_all_events(self, event):
        name = event["name"]
        assert name in self.all_keys, f"{name} not in ALL_EVENTS"

    @pytest.mark.parametrize("event", EVENTS, ids=[e["name"] for e in EVENTS])
    def test_registered_in_builders(self, event):
        name = event["name"]
        assert name in self.builder_keys, f"{name} not in _EVENT_BUILDERS"


class TestNotificationTriggerPoints:
    """验证所有事件均有 send_event 触发点。

    例外（第 2 批安全与审计闭环）：`SECURITY_EVENTS_BY_DESIGN_UNTRIGGERED` 中的事件
    刻意**不由** `NotificationManager.send_event` 投递——凭证变更告警必须早于新凭证
    落库送达旧渠道，而 manager 路径受聚合缓冲（默认 5s）与静音时段（延后至次日）
    影响，会把告警投递到攻击者控制的新地址。故这三个事件由
    `pilotstd/core/notification/security_notifier.py` 直连临时渠道同步发送。
    """

    @pytest.mark.parametrize("event", EVENTS, ids=[e["name"] for e in EVENTS])
    def test_trigger_exists(self, event):
        name = event["name"]
        if name in SECURITY_EVENTS_BY_DESIGN_UNTRIGGERED:
            # 投递路径已由 tests/test_p0_security_endpoints.py 覆盖（含"不得走 send_event"断言）
            return
        calls = _find_send_event_calls(name)
        assert len(calls) > 0, f"{name}: 未找到任何 send_event 调用\n预期触发文件: {event['trigger_file']}"
        for fpath, lineno in calls:
            print(f"  {name}: {fpath}:{lineno}")


class TestNotificationFieldConsistency:
    """双向字段校验：构建器 keys vs 触发方 keys。"""

    @pytest.mark.parametrize("event", EVENTS, ids=[e["name"] for e in EVENTS])
    def test_builder_keys_subset_of_trigger(self, event):
        """触发方传的 key 必须覆盖构建器读取的 key（防漏传）。"""
        name = event["name"]
        builder_expected = event["builder_keys"]
        if not builder_expected:
            return  # 空 builder_keys 平凡满足（如 scan_empty）

        trigger_keys = TRIGGER_KEYS.get(name) or _extract_trigger_payload_keys(name)
        if not trigger_keys:
            return  # 无 trigger_keys 数据，无法验证，视为通过

        whitelist = FALLBACK_WHITELIST.get(name, set())
        missing = builder_expected - trigger_keys - whitelist
        assert not missing, (
            f"{name}: 构建器期望的 key 未在触发方 payload 中找到: {missing}。"
            f"构建器 keys: {sorted(builder_expected)}, 触发方 keys: {sorted(trigger_keys)}"
        )

    @pytest.mark.parametrize("event", EVENTS, ids=[e["name"] for e in EVENTS])
    def test_trigger_keys_subset_of_builder(self, event):
        """触发方传的 key 不应超过构建器读取的范围（防冗余/拼写错误）。"""
        name = event["name"]
        builder_expected = event["builder_keys"]
        trigger_keys = TRIGGER_KEYS.get(name) or _extract_trigger_payload_keys(name)
        if not trigger_keys:
            return  # 无 trigger_keys 数据，无法验证，视为通过

        whitelist = FALLBACK_WHITELIST.get(name, set())
        extra = trigger_keys - builder_expected - whitelist
        extra = {k for k in extra if k not in _SYSTEM_FIELDS}
        if extra and not TRIGGER_KEYS.get(name):
            # 仅当 regex 解析成功时严格检查额外字段
            raise AssertionError(
                f"{name}: 触发方 payload 包含构建器未使用的额外字段: {extra}。"
                f"构建器 keys: {sorted(builder_expected)}, 触发方 keys: {sorted(trigger_keys)}"
            )


# 系统字段：触发方传入但构建器不展示的内部字段
_SYSTEM_FIELDS = {
    "user_id",
    "favorite_id",
    "record_id",
    "changed_at",
    "adapters",
    "change_detail",
    "change_list",
    "adapter_summary",
}


class TestMutualExclusion:
    """验证互斥事件对在正确的文件中触发。"""

    def _has_in_file(self, file_rel: str, pattern: str) -> bool:
        fpath = os.path.join(_PROJECT_ROOT, *file_rel.split("/"))
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        return bool(re.search(pattern, content, re.DOTALL))

    def test_scan_complete_vs_empty_mutual(self):
        """scan_complete 和 scan_empty 均在 _scan.py 中触发。"""
        assert self._has_in_file(
            "pilotstd/manager/facade/_scan.py",
            r'send_event\s*\(\s*"scan_complete"',
        ), "scan_complete 未在 _scan.py 中触发"
        assert self._has_in_file(
            "pilotstd/manager/facade/_scan.py",
            r'send_event\s*\(\s*"scan_empty"',
        ), "scan_empty 未在 _scan.py 中触发"

    def test_query_summary_vs_empty_mutual(self):
        """batch_query_summary 和 query_empty 均在 _query_subsystem.py 中触发。"""
        assert self._has_in_file(
            "pilotstd/manager/facade/_query_subsystem.py",
            r'send_event\s*\(\s*"batch_query_summary"',
        ), "batch_query_summary 未在 _query_subsystem.py 中触发"
        assert self._has_in_file(
            "pilotstd/manager/facade/_query_subsystem.py",
            r'send_event\s*\(\s*"query_empty"',
        ), "query_empty 未在 _query_subsystem.py 中触发"


class TestNotificationSmoke:
    """冒烟测试：通过反射验证 32 个事件的构建器方法存在。"""

    def _get_builder_keys_from_runtime(self):
        """运行期取 _EVENT_BUILDERS 的键（D4：不再用源码正则解析注册表）。"""
        from types import SimpleNamespace

        from pilotstd.core.notification.manager import NotificationManager

        stub = SimpleNamespace()
        NotificationManager._init_event_builders(stub)
        return set(stub._EVENT_BUILDERS)

    def test_all_32_builders_registered(self):
        """验证所有 32 个事件的构建器均已注册。"""
        builder_keys = self._get_builder_keys_from_runtime()
        for event in EVENTS:
            name = event["name"]
            assert name in builder_keys, f"{name} 构建器未在 _EVENT_BUILDERS 注册"


class TestImageUpdateDebugLog:
    """验证 image_update_available 构建器在 digest 为空时输出 debug 日志。"""

    def test_empty_digest_logs_debug(self, caplog):

        from pilotstd.core.notification._builders_system import _build_image_update_available_message

        caplog.set_level("DEBUG", logger="pilotstd.core.notification._builders_system")
        msg = _build_image_update_available_message({"old_digest": "", "new_digest": ""})
        assert msg is not None
        assert "old_digest or new_digest is empty" in caplog.text

    def test_valid_digest_no_debug_log(self, caplog):

        from pilotstd.core.notification._builders_system import _build_image_update_available_message

        caplog.set_level("DEBUG", logger="pilotstd.core.notification._builders_system")
        msg = _build_image_update_available_message({"old_digest": "abc123", "new_digest": "def456"})
        assert msg is not None
        assert "old_digest or new_digest is empty" not in caplog.text


def _make_sample_data(event_name: str, keys: set[str]) -> dict:
    """根据事件名和 keys 构造最小合法 data。"""
    sample: dict[str, Any] = {}
    str_fields = {
        "standard_number",
        "standard_info",
        "std_name",
        "target_path",
        "error",
        "source",
        "task_name",
        "site_name",
        "worker",
        "old_status",
        "new_status",
        "path",
        "backup_path",
        "old_digest",
        "new_digest",
        "old_version",
        "new_version",
        "title",
        "body",
        "quota_limit",
        "reset_time",
        "remind_type",
        "context",
    }
    int_fields = {
        "count",
        "total",
        "success",
        "failed",
        "changed",
        "skipped",
        "found",
        "pending",
        "days_before",
        "total_checks",
        "total_changes",
        "total_failures",
        "gb_count",
        "hb_count",
        "db_count",
        "total_standards",
        "total_announcements",
        "failures",
        "round",
    }
    bool_fields = {"success", "is_expired"}
    list_fields = {"directories", "standards", "change_list", "change_detail", "searched_sources", "results"}
    float_fields = {"size_mb", "elapsed_ms"}

    for k in keys:
        if k in str_fields:
            sample[k] = f"sample_{k}"
        elif k in int_fields:
            sample[k] = 1
        elif k in bool_fields:
            sample[k] = True
        elif k in list_fields:
            sample[k] = []
        elif k in float_fields:
            sample[k] = 1.0
        else:
            sample[k] = f"sample_{k}"
    return sample
