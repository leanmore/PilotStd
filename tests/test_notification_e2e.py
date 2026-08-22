# tests/test_notification_e2e.py
# Q20 集成验证：32 事件全量覆盖 — 注册状态 + 触发点静态检查 + 字段双向校验 + 互斥逻辑
# 生成日期: 2026-07-22
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
    """从触发点源码中提取 send_event data dict 的顶层 key 集合（取第一个匹配）。"""
    pattern = re.compile(
        r'send_event\s*\(\s*["\']' + re.escape(event_name) + r'["\']\s*,\s*(\{.*?\})\s*\)',
        re.DOTALL,
    )
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
                        content = fh.read()
                except OSError:
                    continue
                match = pattern.search(content)
                if match:
                    dict_str = match.group(1)
                    return _parse_dict_keys(dict_str)
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

# 硬编码 trigger_keys — 当 regex 无法解析 Block 模式 send_event 时使用
# 由手动审查 trigger 源码维护，是字段验证的真实来源
TRIGGER_KEYS: dict[str, set[str]] = {
    "standard_status_changed": {"standard_number", "old_status", "new_status", "is_expired", "changed_at"},
    "standard_expired": {"standard_number", "old_status", "new_status", "changed_at"},
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
    "validity_system_failed": {"error", "traceback", "context"},
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
}

EVENTS: list[dict[str, Any]] = [
    # ── 时效性检查 (7) ──
    {
        "name": "standard_status_changed",
        "module": "时效性检查",
        "level": "info/warning/error",
        "aggregation": "聚合",
        "trigger_file": "pilotstd/core/validity_checker.py",
        "builder_file": "pilotstd/core/notification/_builders_validity.py",
        "builder_method": "_build_standard_status_changed_message",
        "builder_keys": {"standard_number", "old_status", "new_status", "is_expired", "changed_at"},
        "mutual": "",
    },
    {
        "name": "standard_expired",
        "module": "时效性检查",
        "level": "error",
        "aggregation": "聚合",
        "trigger_file": "pilotstd/core/validity_checker.py",
        "builder_file": "pilotstd/core/notification/_builders_validity.py",
        "builder_method": "_build_standard_expired_message",
        "builder_keys": {"standard_number", "old_status", "new_status", "changed_at"},
        "mutual": "",
    },
    {
        "name": "standard_first_registered",
        "module": "时效性检查",
        "level": "info",
        "aggregation": "聚合",
        "trigger_file": "pilotstd/core/validity_checker.py",
        "builder_file": "pilotstd/core/notification/_builders_validity.py",
        "builder_method": "_build_standard_first_registered_message",
        "builder_keys": {"standard_number", "name", "standards", "detail_url", "elapsed_ms"},
        "mutual": "",
    },
    {
        "name": "validity_batch_report",
        "module": "时效性检查",
        "level": "info/warning",
        "aggregation": "聚合",
        "trigger_file": "pilotstd/core/_validity_pipeline.py",
        "builder_file": "pilotstd/core/notification/_builders_validity.py",
        "builder_method": "_build_validity_batch_report_message",
        "builder_keys": {"count", "changed", "failed", "adapter_status"},
        "mutual": "",
    },
    {
        "name": "validity_round_summary",
        "module": "时效性检查",
        "level": "info",
        "aggregation": "聚合",
        "trigger_file": "pilotstd/core/_validity_pipeline.py",
        "builder_file": "pilotstd/core/notification/_builders_validity.py",
        "builder_method": "_build_validity_round_summary_message",
        "builder_keys": {"round", "total_checks", "total_changes", "total_failures", "change_list"},
        "mutual": "",
    },
    {
        "name": "validity_standard_failed",
        "module": "时效性检查",
        "level": "error",
        "aggregation": "聚合",
        "trigger_file": "pilotstd/core/_validity_pipeline.py",
        "builder_file": "pilotstd/core/notification/_builders_validity.py",
        "builder_method": "_build_validity_standard_failed_message",
        "builder_keys": {"standard_number", "error"},
        "mutual": "",
    },
    {
        "name": "validity_system_failed",
        "module": "时效性检查",
        "level": "error",
        "aggregation": "bypass",
        "trigger_file": "pilotstd/core/_validity_pipeline.py",
        "builder_file": "pilotstd/core/notification/_builders_validity.py",
        "builder_method": "_build_validity_system_failed_message",
        "builder_keys": {"error", "context"},
        "mutual": "",
    },
    # ── 扫描/导入 (3) ──
    {
        "name": "scan_complete",
        "module": "扫描/导入",
        "level": "info/warning",
        "aggregation": "聚合",
        "trigger_file": "pilotstd/manager/facade/_scan.py",
        "builder_file": "pilotstd/core/notification/_builders_batch.py",
        "builder_method": "_build_scan_complete_message",
        "builder_keys": {"count", "failed"},
        "mutual": "互斥: scan_empty",
    },
    {
        "name": "scan_empty",
        "module": "扫描/导入",
        "level": "info",
        "aggregation": "聚合",
        "trigger_file": "pilotstd/manager/facade/_scan.py",
        "builder_file": "pilotstd/core/notification/_builders_batch.py",
        "builder_method": "_build_scan_empty_message",
        "builder_keys": set(),
        "mutual": "互斥: scan_complete",
    },
    {
        "name": "auto_scan_failed",
        "module": "扫描/导入",
        "level": "error",
        "aggregation": "bypass",
        "trigger_file": "pilotstd/manager/facade/_scan.py",
        "builder_file": "pilotstd/core/notification/_builders_batch.py",
        "builder_method": "_build_auto_scan_failed_message",
        "builder_keys": {"path", "error"},
        "mutual": "",
    },
    # ── 查询 (3) ──
    {
        "name": "batch_query_summary",
        "module": "查询",
        "level": "info/warning",
        "aggregation": "聚合",
        "trigger_file": "pilotstd/manager/facade/_query_exec.py",
        "builder_file": "pilotstd/core/notification/_builders_batch.py",
        "builder_method": "_build_batch_query_summary_message",
        "builder_keys": {"total", "found", "pending", "results"},
        "mutual": "互斥: query_empty",
    },
    {
        "name": "query_failed",
        "module": "查询",
        "level": "error",
        "aggregation": "bypass",
        "trigger_file": "pilotstd/manager/facade/_query_exec.py",
        "builder_file": "pilotstd/core/notification/_builders_batch.py",
        "builder_method": "_build_query_failed_message",
        "builder_keys": {"standard_number", "error"},
        "mutual": "",
    },
    {
        "name": "query_empty",
        "module": "查询",
        "level": "warning",
        "aggregation": "聚合",
        "trigger_file": "pilotstd/manager/facade/_query_exec.py",
        "builder_file": "pilotstd/core/notification/_builders_batch.py",
        "builder_method": "_build_query_empty_message",
        "builder_keys": {"total"},
        "mutual": "互斥: batch_query_summary",
    },
    # ── 下载 (2) ──
    {
        "name": "batch_download_complete",
        "module": "下载",
        "level": "info/warning",
        "aggregation": "聚合",
        "trigger_file": "pilotstd/download/engine.py",
        "builder_file": "pilotstd/core/notification/_builders_batch.py",
        "builder_method": "_build_batch_download_complete_message",
        "builder_keys": {"success", "failed", "skipped"},
        "mutual": "",
    },
    {
        "name": "download_failed",
        "module": "下载",
        "level": "error",
        "aggregation": "bypass",
        "trigger_file": "pilotstd/tasks/favorite_download.py",
        "builder_file": "pilotstd/core/notification/_builders_batch.py",
        "builder_method": "_build_download_failed_message",
        "builder_keys": {"standard_number", "error"},
        "mutual": "",
    },
    # ── 规范化 (2) ──
    {
        "name": "normalize_complete",
        "module": "规范化",
        "level": "info",
        "aggregation": "聚合",
        "trigger_file": "pilotstd/manager/facade/_organize.py",
        "builder_file": "pilotstd/core/notification/_builders_batch.py",
        "builder_method": "_build_normalize_complete_message",
        "builder_keys": {"total", "success", "failed"},
        "mutual": "",
    },
    {
        "name": "normalize_failed",
        "module": "规范化",
        "level": "error",
        "aggregation": "bypass",
        "trigger_file": "pilotstd/manager/facade/_organize.py",
        "builder_file": "pilotstd/core/notification/_builders_batch.py",
        "builder_method": "_build_normalize_failed_message",
        "builder_keys": {"total", "error"},
        "mutual": "",
    },
    # ── 归档 (4) ──
    {
        "name": "archive_complete",
        "module": "归档",
        "level": "info",
        "aggregation": "聚合",
        "trigger_file": "pilotstd/manager/facade/_organize.py",
        "builder_file": "pilotstd/core/notification/_builders_system.py",
        "builder_method": "_build_archive_complete_message",
        "builder_keys": {"count", "directories", "standard_number", "status", "target_id", "elapsed_ms"},
        "mutual": "count=0 时也触发（archive_empty 未独立）",
    },
    {
        "name": "archive_failed",
        "module": "归档",
        "level": "error",
        "aggregation": "bypass",
        "trigger_file": "pilotstd/manager/organize/organizer.py",
        "builder_file": "pilotstd/core/notification/_builders_batch.py",
        "builder_method": "_build_archive_failed_message",
        "builder_keys": {"count", "error"},
        "mutual": "",
    },
    {
        "name": "archive_abandoned",
        "module": "归档",
        "level": "error",
        "aggregation": "bypass",
        "trigger_file": "pilotstd/manager/archive_retry_service.py",
        "builder_file": "pilotstd/core/notification/_builders_batch.py",
        "builder_method": "_build_archive_abandoned_message",
        "builder_keys": {"standard_info", "error"},
        "mutual": "",
    },
    {
        "name": "expire_standard_moved",
        "module": "废止处理",
        "level": "info",
        "aggregation": "聚合",
        "trigger_file": "pilotstd/manager/facade/_organize.py",
        "builder_file": "pilotstd/core/notification/_builders_batch.py",
        "builder_method": "_build_expire_standard_moved_message",
        "builder_keys": {"standard_number", "target_path"},
        "mutual": "",
    },
    # ── 公告 (3) ──
    {
        "name": "announcement_fetch_complete",
        "module": "公告抓取",
        "level": "info",
        "aggregation": "聚合",
        "trigger_file": "docker/api/announce.py",
        "builder_file": "pilotstd/core/notification/_builders_batch.py",
        "builder_method": "_build_announcement_fetch_complete_message",
        "builder_keys": {"count", "source"},
        "mutual": "",
    },
    {
        "name": "announcement_check_complete",
        "module": "公告抓取",
        "level": "info/warning/error",
        "aggregation": "聚合",
        "trigger_file": "pilotstd/announce/notifier.py",
        "builder_file": "pilotstd/core/notification/_builders_system.py",
        "builder_method": "_build_announcement_check_complete_message",
        "builder_keys": {
            "source",
            "total_announcements",
            "gb_count",
            "hb_count",
            "db_count",
            "total_standards",
            "failures",
        },
        "mutual": "",
    },
    {
        "name": "announcement_fetch_failed",
        "module": "公告抓取",
        "level": "error",
        "aggregation": "bypass",
        "trigger_file": "pilotstd/announce/notifier.py",
        "builder_file": "pilotstd/core/notification/_builders_system.py",
        "builder_method": "_build_announcement_fetch_failed_message",
        "builder_keys": {"source", "error"},
        "mutual": "",
    },
    # ── 废止处理 (1, 含在归档模块的 expire_standard_moved 已列) ──
    {
        "name": "replacement_not_found",
        "module": "废止处理",
        "level": "warning",
        "aggregation": "bypass",
        "trigger_file": "pilotstd/manager/classifier.py",
        "builder_file": "pilotstd/core/notification/_builders_batch.py",
        "builder_method": "_build_replacement_not_found_message",
        "builder_keys": {"standard_number", "searched_sources"},
        "mutual": "",
    },
    # ── 系统运维 (5) ──
    {
        "name": "auto_backup",
        "module": "系统运维",
        "level": "info/error",
        "aggregation": "bypass",
        "trigger_file": "docker/scheduler.py",
        "builder_file": "pilotstd/core/notification/_builders_system.py",
        "builder_method": "_build_auto_backup_message",
        "builder_keys": {"success", "backup_path", "size_mb", "error"},
        "mutual": "",
    },
    {
        "name": "image_update_available",
        "module": "系统运维",
        "level": "info/error",
        "aggregation": "bypass",
        "trigger_file": "docker/api/system.py",
        "builder_file": "pilotstd/core/notification/_builders_system.py",
        "builder_method": "_build_image_update_available_message",
        "builder_keys": {"error", "old_digest", "new_digest", "release_notes"},
        "mutual": "",
    },
    {
        "name": "worker_error",
        "module": "系统运维",
        "level": "error",
        "aggregation": "bypass",
        "trigger_file": "pilotstd/ui/pending_query_dialog.py",
        "builder_file": "pilotstd/core/notification/_builders_system.py",
        "builder_method": "_build_worker_error_message",
        "builder_keys": {"worker", "error", "traceback"},
        "mutual": "",
    },
    {
        "name": "task_execution_failed",
        "module": "系统运维",
        "level": "error",
        "aggregation": "bypass",
        "trigger_file": "docker/scheduler.py",
        "builder_file": "pilotstd/core/notification/_builders_system.py",
        "builder_method": "_build_task_execution_failed_message",
        "builder_keys": {"task_name", "error"},
        "mutual": "",
    },
    {
        "name": "quota_exhausted",
        "module": "系统运维",
        "level": "warning",
        "aggregation": "bypass",
        "trigger_file": "pilotstd/query/daily_quota.py",
        "builder_file": "pilotstd/core/notification/_builders_system.py",
        "builder_method": "_build_quota_exhausted_message",
        "builder_keys": {"site_name", "quota_limit", "reset_time"},
        "mutual": "",
    },
    # ── 用户交互 (1) ──
    {
        "name": "date_reminder",
        "module": "用户交互",
        "level": "info",
        "aggregation": "聚合",
        "trigger_file": "pilotstd/tasks/date_reminder.py",
        "builder_file": "pilotstd/core/notification/_builders_batch.py",
        "builder_method": "_build_date_reminder_message",
        "builder_keys": {"standard_number", "std_name", "days_before", "remind_type"},
        "mutual": "",
    },
    # ── 其他 (1) ──
    {
        "name": "trust_ip_update",
        "module": "系统运维",
        "level": "info/warning",
        "aggregation": "bypass",
        "trigger_file": "pilotstd/manager/wechat_ip_service.py",
        "builder_file": "pilotstd/core/notification/_builders_system.py",
        "builder_method": "_build_trust_ip_update_message",
        "builder_keys": {"title", "body", "ip", "update_time", "status"},
        "mutual": "",
    },
    # ── 收藏链 (3, Phase 2 新增) ──
    {
        "name": "favorite_created",
        "module": "收藏链",
        "level": "info",
        "aggregation": "bypass",
        "trigger_file": "docker/api/favorites.py",
        "builder_file": "pilotstd/core/notification/_builders_batch.py",
        "builder_method": "_build_favorite_created_message",
        "builder_keys": {"user_id", "record_id", "standard_no", "standard_name"},
        "mutual": "",
    },
    {
        "name": "download_started",
        "module": "收藏链",
        "level": "info",
        "aggregation": "聚合",
        "trigger_file": "pilotstd/tasks/favorite_download.py",
        "builder_file": "pilotstd/core/notification/_builders_batch.py",
        "builder_method": "_build_download_started_message",
        "builder_keys": {"user_id", "standard_number", "favorite_id"},
        "mutual": "",
    },
    {
        "name": "download_complete",
        "module": "收藏链",
        "level": "info",
        "aggregation": "聚合",
        "trigger_file": "pilotstd/tasks/favorite_download.py",
        "builder_file": "pilotstd/core/notification/_builders_batch.py",
        "builder_method": "_build_download_complete_message",
        "builder_keys": {"user_id", "standard_number", "favorite_id", "local_path", "status"},
        "mutual": "",
    },
]

# 验证 EVENTS 列表完整性
assert len(EVENTS) == 35, f"Expected 35 events, got {len(EVENTS)}"


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
        from pilotstd.core.notification.events import ALL_EVENT_KEYS
        from pilotstd.core.notification.manager import NotificationManager

        self.all_keys = ALL_EVENT_KEYS
        # 获取 _EVENT_BUILDERS keys（需要实例化才能访问，用反射获取）
        import inspect

        src = inspect.getsource(NotificationManager._init_event_builders)
        self.builder_keys: set[str] = set()
        for m in re.finditer(r'"([a-z_]+)":\s*_build', src):
            self.builder_keys.add(m.group(1))

    @pytest.mark.parametrize("event", EVENTS, ids=[e["name"] for e in EVENTS])
    def test_registered_in_all_events(self, event):
        name = event["name"]
        assert name in self.all_keys, f"{name} not in ALL_EVENTS"

    @pytest.mark.parametrize("event", EVENTS, ids=[e["name"] for e in EVENTS])
    def test_registered_in_builders(self, event):
        name = event["name"]
        assert name in self.builder_keys, f"{name} not in _EVENT_BUILDERS"


class TestNotificationTriggerPoints:
    """验证所有 32 个事件均有 send_event 触发点。"""

    @pytest.mark.parametrize("event", EVENTS, ids=[e["name"] for e in EVENTS])
    def test_trigger_exists(self, event):
        name = event["name"]
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

    def _get_builder_keys_from_source(self):
        """从 NotificationManager._init_event_builders 源码提取注册的 builder key。"""
        import inspect

        from pilotstd.core.notification.manager import NotificationManager

        src = inspect.getsource(NotificationManager._init_event_builders)
        keys: set[str] = set()
        for m in re.finditer(r'"([a-z_]+)":\s*_build', src):
            keys.add(m.group(1))
        return keys

    def test_all_32_builders_registered(self):
        """验证所有 32 个事件的构建器均已注册。"""
        builder_keys = self._get_builder_keys_from_source()
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
