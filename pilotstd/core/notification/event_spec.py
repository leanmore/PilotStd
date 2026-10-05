# 模块：项目/核心//事件规格脚本
"""事件规格（SSOT）——41 个通知事件的唯一声明源（设计见 notification-system-design/06 §一）。

本模块只做声明：**D1 起由 `mapping` 接入**（`EVENT_MAPPINGS` 由其派生）；其余消费方
（`manager` 构建器注册 / `defaults` 订阅规则）按 D2 / D3 逐步接入。四条硬约束：

1. **单向依赖**：只 import 标准库与 ``.events``（该模块零内部依赖、10 个消费方，
   不能被拖重）。**不 import 构建器实现模块**——构建器位置以 ``builder_ref``
   字符串登记、运行期由 ``builder_callable()`` 延迟解析，以免 ``mapping`` /
   ``defaults`` 这类轻消费方在取规格时被动加载渲染链路。
2. **静态字面量**：门禁以 ``ast.parse`` 读取本文件，不做运行期推导；每条声明的
   15 个字段一律写字面量。
3. **15 字段**：``key`` / ``notify_event`` / ``content_type`` / ``task_kind`` /
   ``builder_ref`` / ``i18n_category`` / ``default_channels`` / ``levels`` /
   ``module_key`` / ``trigger_file`` / ``payload_keys`` / ``security`` /
   ``branch_by`` / ``subscribable`` / ``aggregation``。取值来自映射表、端到端契约、
   默认配置与语言包；构建器文件与函数名不入规格（由 ``builder`` 反射派生）。
4. **级别有序**：``levels`` 按 ``LEVEL_ORDER`` 的严重度升序书写，与既有端到端
   契约的斜杠连接字面值完全同序。

**字段值一律机器可读，不写展示文案**（决策者 2026-10-03 裁决方案 c）：

- 业务模块名改用 i18n 键（``module_key``）——文案本体在 ``pilotstd/i18n/*.json``
  的 ``notification.module.*`` 键族里，本模块只登记键；中文模块名不可出现在此。
- 聚合策略改用 ASCII 枚举（``aggregate`` / ``bypass``）——它是系统内部状态标识，
  **不进 i18n**（不展示给用户，做成键反而增加一层无意义的间接）。
- **不登记互斥说明**：互斥关系是设计文档里的说明，不是数据；需要时查设计文档，
  不在此复制一份中文散文（e2e 契约自留该字段用于自身比对，与本模块无关）。

留待后续批次：``branch_by`` 一律为 ``None``（4 个待分支事件尚无分支实现）；
``subscribable``（用户可勾选）与 ``default_channels``（出厂默认订阅）不同轴；
``security`` 判定**是否强制审计留痕**，与 ``notify_event`` 是否为安全告警不同轴。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .events import ALL_EVENTS

# 级别的**唯一排序口径**（设计 06 §三 2 遗留项 1，2026-10-05 落地）。
# 为什么用严重度序而非字母序：级别是给人看、给策略判定的语义标签，字母序
# （error/info/warning）会误导读者，也与端到端契约的斜杠连接字面值（"info/warning/error"）不同序。
# 为什么允许"跳级"：`("info", "error")` 是真实业务事实（该事件不产生 warning）⇒
# 校验只要求**保序**，不要求连续覆盖——统一的是**顺序口径**，不是**值集合**。
# 校验位置：`tests/test_notification_e2e.py` 的 D4 契约测试类（该文件是计划内的规格消费方；
# 新建独立测试文件会被 `test_event_spec.py` 的"接入白名单"守卫正确拦截）。
LEVEL_ORDER: tuple[str, ...] = ("info", "warning", "error")

__all__ = [
    "AGGREGATION_VALUES",
    "EVENT_SPECS",
    "EVENT_SPEC_KEYS",
    "LEVEL_ORDER",
    "EventSpec",
    "builder_callable",
    "spec_for",
]

# 聚合策略值域闭集（纯英文枚举，非展示文案）：与端到端契约的 38 聚合 + 3 绕过同义
AGGREGATION_VALUES: tuple[str, ...] = ("aggregate", "bypass")

# 级别值域闭集，按严重度升序——声明里的级别序列必须按本次序书写


@dataclass(frozen=True)
class EventSpec:
    """单个通知事件的声明（`builder_ref` 是静态指针，`builder` 按需解析）。"""

    key: str
    notify_event: str
    content_type: str
    task_kind: str
    builder_ref: str
    i18n_category: str
    default_channels: tuple[str, ...]
    levels: tuple[str, ...]
    module_key: str
    trigger_file: str
    payload_keys: frozenset[str]
    security: bool
    branch_by: Callable[[dict[str, Any]], str] | None
    subscribable: bool
    aggregation: str

    @property
    def builder(self) -> Callable[[dict[str, Any]], Any]:
        """本事件的构建器函数（延迟解析，见模块说明第 1 条）。"""
        return builder_callable(self)


def builder_callable(spec: EventSpec) -> Callable[[dict[str, Any]], Any]:
    """把静态指针解析为构建器函数；模块名或函数名有误时抛导入类异常。"""
    import importlib

    module_name, _, func_name = spec.builder_ref.partition(":")
    resolved: Callable[[dict[str, Any]], Any] = getattr(importlib.import_module(module_name), func_name)
    return resolved


def spec_for(key: str) -> EventSpec:
    """按键取规格；未登记的键视为契约违背（调用方应先做键集校验）。"""
    for spec in EVENT_SPECS:
        if spec.key == key:
            return spec
    raise KeyError(key)


# ── 声明（41 条；按业务模块分组，分组与顺序对齐既有端到端契约，便于逐条比对）──

EVENT_SPECS: tuple[EventSpec, ...] = (
    # ── 时效性检查（6）──
    EventSpec(key="standard_status_changed", notify_event="schedule_reminder", content_type="status_change",
        task_kind="validity_check",
        builder_ref="pilotstd.core.notification._builders_validity:_build_standard_status_changed_message",
        i18n_category="notification.validity", default_channels=("wechat",), levels=("info", "warning", "error"),
        module_key="notification.module.validity", trigger_file="pilotstd/core/validity_checker.py",
        payload_keys=frozenset({"changed_at", "is_expired", "new_status", "old_status", "standard_number"}),
        security=False, branch_by=None, subscribable=True, aggregation="aggregate",
    ),
    EventSpec(key="standard_first_registered", notify_event="task_result", content_type="list",
        task_kind="validity_check",
        builder_ref="pilotstd.core.notification._builders_validity:_build_standard_first_registered_message",
        i18n_category="notification.validity", default_channels=(), levels=("info",),
        module_key="notification.module.validity", trigger_file="pilotstd/core/validity_checker.py",
        payload_keys=frozenset({"detail_url", "elapsed_ms", "name", "standard_number", "standards"}), security=False,
        branch_by=None, subscribable=True, aggregation="aggregate",
    ),
    EventSpec(key="validity_batch_report", notify_event="batch_summary", content_type="list",
        task_kind="validity_check",
        builder_ref="pilotstd.core.notification._builders_validity:_build_validity_batch_report_message",
        i18n_category="notification.validity", default_channels=("wechat",), levels=("info", "warning"),
        module_key="notification.module.validity", trigger_file="pilotstd/core/_validity_pipeline.py",
        payload_keys=frozenset({"adapter_status", "changed", "count", "failed"}), security=False, branch_by=None,
        subscribable=True, aggregation="aggregate",
    ),
    EventSpec(key="validity_round_summary", notify_event="batch_summary", content_type="list",
        task_kind="validity_check",
        builder_ref="pilotstd.core.notification._builders_validity:_build_validity_round_summary_message",
        i18n_category="notification.validity", default_channels=("wechat",), levels=("info",),
        module_key="notification.module.validity", trigger_file="pilotstd/core/_validity_pipeline.py",
        payload_keys=frozenset({"change_list", "round", "total_changes", "total_checks", "total_failures"}),
        security=False, branch_by=None, subscribable=True, aggregation="aggregate",
    ),
    EventSpec(key="validity_standard_failed", notify_event="anomaly_alert", content_type="text",
        task_kind="validity_check",
        builder_ref="pilotstd.core.notification._builders_validity:_build_validity_standard_failed_message",
        i18n_category="notification.validity", default_channels=("wechat",), levels=("error",),
        module_key="notification.module.validity", trigger_file="pilotstd/core/_validity_pipeline.py",
        payload_keys=frozenset({"error", "standard_number"}), security=False, branch_by=None, subscribable=True,
        aggregation="aggregate",
    ),
    EventSpec(key="validity_system_failed", notify_event="anomaly_alert", content_type="text",
        task_kind="validity_check",
        builder_ref="pilotstd.core.notification._builders_validity:_build_validity_system_failed_message",
        i18n_category="notification.validity", default_channels=("wechat",), levels=("error",),
        module_key="notification.module.validity", trigger_file="pilotstd/core/_validity_pipeline.py",
        payload_keys=frozenset({"error"}), security=False, branch_by=None, subscribable=True, aggregation="aggregate",
    ),

    # ── 用户交互（1）──
    EventSpec(key="date_reminder", notify_event="schedule_reminder", content_type="field_list", task_kind="",
        builder_ref="pilotstd.core.notification._builders_task_results:_build_date_reminder_message",
        i18n_category="notification.validity", default_channels=("wechat",), levels=("info",),
        module_key="notification.module.interaction", trigger_file="pilotstd/tasks/date_reminder.py",
        payload_keys=frozenset({"days_before", "remind_type", "standard_number", "std_name"}), security=False,
        branch_by=None, subscribable=True, aggregation="aggregate",
    ),

    # ── 扫描/导入（3）──
    EventSpec(key="scan_complete", notify_event="task_result", content_type="list", task_kind="scan",
        builder_ref="pilotstd.core.notification._builders_task_results:_build_scan_complete_message",
        i18n_category="notification.scan", default_channels=(), levels=("info", "warning"),
        module_key="notification.module.scan", trigger_file="pilotstd/manager/facade/_scan.py",
        payload_keys=frozenset({"count", "failed"}), security=False, branch_by=None, subscribable=True,
        aggregation="aggregate",
    ),
    EventSpec(key="scan_empty", notify_event="task_result", content_type="text", task_kind="scan",
        builder_ref="pilotstd.core.notification._builders_task_results:_build_scan_empty_message",
        i18n_category="notification.scan", default_channels=(), levels=("info",),
        module_key="notification.module.scan", trigger_file="pilotstd/manager/facade/_scan.py",
        payload_keys=frozenset(), security=False, branch_by=None, subscribable=True, aggregation="aggregate",
    ),
    EventSpec(key="auto_scan_failed", notify_event="batch_summary", content_type="text", task_kind="scan",
        builder_ref="pilotstd.core.notification._builders_batch:_build_auto_scan_failed_message",
        i18n_category="notification.scan", default_channels=("wechat",), levels=("error",),
        module_key="notification.module.scan", trigger_file="pilotstd/manager/facade/_scan.py",
        payload_keys=frozenset({"error", "path"}), security=False, branch_by=None, subscribable=True,
        aggregation="aggregate",
    ),

    # ── 查询（3）──
    EventSpec(key="batch_query_summary", notify_event="batch_summary", content_type="list", task_kind="query",
        builder_ref="pilotstd.core.notification._builders_batch:_build_batch_query_summary_message",
        i18n_category="notification.query", default_channels=(), levels=("info", "warning"),
        module_key="notification.module.query", trigger_file="pilotstd/manager/facade/_query_subsystem.py",
        payload_keys=frozenset({"failed_items", "found", "pending", "results", "total"}), security=False,
        branch_by=None,
        subscribable=True, aggregation="aggregate",
    ),
    EventSpec(key="query_failed", notify_event="task_failure", content_type="text", task_kind="query",
        builder_ref="pilotstd.core.notification._builders_task_results:_build_query_failed_message",
        i18n_category="notification.query", default_channels=(), levels=("error",),
        module_key="notification.module.query", trigger_file="pilotstd/manager/facade/_query_subsystem.py",
        payload_keys=frozenset({"error", "standard_number"}), security=False, branch_by=None, subscribable=True,
        aggregation="aggregate",
    ),
    EventSpec(key="query_empty", notify_event="batch_summary", content_type="text", task_kind="query",
        builder_ref="pilotstd.core.notification._builders_task_results:_build_query_empty_message",
        i18n_category="notification.query", default_channels=(), levels=("warning",),
        module_key="notification.module.query", trigger_file="pilotstd/manager/facade/_query_subsystem.py",
        payload_keys=frozenset({"total"}), security=False, branch_by=None, subscribable=True,
        aggregation="aggregate",
    ),

    # ── 下载（2）──
    EventSpec(key="batch_download_complete", notify_event="batch_summary", content_type="list",
        task_kind="favorite_download",
        builder_ref="pilotstd.core.notification._builders_batch:_build_batch_download_complete_message",
        i18n_category="notification.download", default_channels=("wechat",), levels=("info", "warning"),
        module_key="notification.module.download", trigger_file="pilotstd/download/engine.py",
        payload_keys=frozenset({"failed", "failed_items", "skipped", "success"}), security=False, branch_by=None,
        subscribable=True,
        aggregation="aggregate",
    ),
    EventSpec(key="download_failed", notify_event="task_failure", content_type="text",
        task_kind="favorite_download",
        builder_ref="pilotstd.core.notification._builders_batch:_build_download_failed_message",
        i18n_category="notification.download", default_channels=(), levels=("error",),
        module_key="notification.module.download", trigger_file="pilotstd/tasks/favorite_download.py",
        # 名称：载荷携带「当前最高可得阶段名」（③决策→②查询→①解析，见 core/name_resolution.py）。
        # 生产方 favorite_download.py::_fetch_std_meta 已按该链取值 ⇒ 此声明须与生产方同批，
        # 否则 tests/test_notification_e2e.py 的正向断言（builder ⊆ trigger）会失败。
        payload_keys=frozenset(
            {"error", "standard_name", "standard_number"}
        ), security=False, branch_by=None, subscribable=True,
        aggregation="aggregate",
    ),

    # ── 规范化（2）──
    EventSpec(key="normalize_complete", notify_event="batch_summary", content_type="text", task_kind="normalize",
        builder_ref="pilotstd.core.notification._builders_batch:_build_normalize_complete_message",
        i18n_category="notification.archive", default_channels=(), levels=("info",),
        module_key="notification.module.normalize", trigger_file="pilotstd/manager/facade/_organize.py",
        payload_keys=frozenset({"failed", "failed_items", "success", "total"}), security=False, branch_by=None,
        subscribable=True,
        aggregation="aggregate",
    ),
    EventSpec(key="normalize_failed", notify_event="task_failure", content_type="text", task_kind="normalize",
        builder_ref="pilotstd.core.notification._builders_task_results:_build_normalize_failed_message",
        i18n_category="notification.archive", default_channels=(), levels=("error",),
        module_key="notification.module.normalize", trigger_file="pilotstd/manager/facade/_organize.py",
        payload_keys=frozenset({"error", "total"}), security=False, branch_by=None, subscribable=True,
        aggregation="aggregate",
    ),

    # ── 归档（3）──
    EventSpec(key="archive_complete", notify_event="batch_summary", content_type="list", task_kind="organize",
        builder_ref="pilotstd.core.notification._builders_system:_build_archive_complete_message",
        i18n_category="notification.archive", default_channels=("wechat",), levels=("info",),
        module_key="notification.module.archive", trigger_file="pilotstd/manager/facade/_organize.py",
        # 2026-10-05 B1-3：按**实现**对齐——`_organize.py::archive_standards` 实际只传
        # count / directories / category_stats（原声明的 elapsed_ms / standard_number / status / target_id 从未传入）；
        # 并追加 failed_items（批量导入失败明细，需求①）。
        payload_keys=frozenset({"category_stats", "count", "directories", "failed_items"}),
        security=False, branch_by=None, subscribable=True, aggregation="aggregate",
    ),
    EventSpec(key="archive_failed", notify_event="task_failure", content_type="text", task_kind="organize",
        builder_ref="pilotstd.core.notification._builders_task_results:_build_archive_failed_message",
        i18n_category="notification.archive", default_channels=(), levels=("error",),
        module_key="notification.module.archive", trigger_file="pilotstd/manager/organize/organizer.py",
        payload_keys=frozenset({"count", "error"}), security=False, branch_by=None, subscribable=True,
        aggregation="aggregate",
    ),
    EventSpec(key="archive_abandoned", notify_event="task_result", content_type="text",
        task_kind="favorite_download",
        builder_ref="pilotstd.core.notification._builders_batch:_build_archive_abandoned_message",
        i18n_category="notification.archive", default_channels=(), levels=("error",),
        module_key="notification.module.archive", trigger_file="pilotstd/services/favorite_chain_processor.py",
        payload_keys=frozenset({"error", "standard_info"}), security=False, branch_by=None, subscribable=True,
        aggregation="aggregate",
    ),

    # ── 废止处理（2）──
    EventSpec(key="expire_standard_moved", notify_event="task_result", content_type="text", task_kind="organize",
        builder_ref="pilotstd.core.notification._builders_task_results:_build_expire_standard_moved_message",
        i18n_category="notification.validity", default_channels=(), levels=("info",),
        module_key="notification.module.expire", trigger_file="pilotstd/manager/facade/_organize.py",
        payload_keys=frozenset({"standard_number", "target_path"}), security=False, branch_by=None, subscribable=True,
        aggregation="aggregate",
    ),
    EventSpec(key="replacement_not_found", notify_event="task_failure", content_type="text", task_kind="query",
        builder_ref="pilotstd.core.notification._builders_task_results:_build_replacement_not_found_message",
        i18n_category="notification.validity", default_channels=(), levels=("warning",),
        module_key="notification.module.expire", trigger_file="pilotstd/manager/classifier.py",
        payload_keys=frozenset({"searched_sources", "standard_number"}), security=False, branch_by=None,
        subscribable=True, aggregation="aggregate",
    ),

    # ── 公告抓取（4）──
    EventSpec(key="announcement_fetch_complete", notify_event="user_activity", content_type="list",
        task_kind="announce_fetch",
        builder_ref="pilotstd.core.notification._builders_batch:_build_announcement_fetch_complete_message",
        i18n_category="notification.announce", default_channels=("wechat",), levels=("info",),
        module_key="notification.module.announce", trigger_file="docker/api/announce.py",
        payload_keys=frozenset({"count", "source"}), security=False, branch_by=None, subscribable=True,
        aggregation="aggregate",
    ),
    EventSpec(key="announcement_check_complete", notify_event="user_activity", content_type="list",
        task_kind="announce_fetch",
        builder_ref="pilotstd.core.notification._builders_system:_build_announcement_check_complete_message",
        i18n_category="notification.announce", default_channels=("wechat",), levels=("info", "warning", "error"),
        module_key="notification.module.announce", trigger_file="pilotstd/announce/notifier.py",
        payload_keys=frozenset(
            {"db_count", "failures", "gb_count", "hb_count", "source", "total_announcements", "total_standards"}
        ),
         security=False, branch_by=None, subscribable=True, aggregation="aggregate",
    ),
    EventSpec(key="announcement_fetch_failed", notify_event="user_activity", content_type="text",
        task_kind="announce_fetch",
        builder_ref="pilotstd.core.notification._builders_system:_build_announcement_fetch_failed_message",
        i18n_category="notification.announce", default_channels=(), levels=("error",),
        module_key="notification.module.announce", trigger_file="pilotstd/announce/notifier.py",
        payload_keys=frozenset({"error", "source"}), security=False, branch_by=None, subscribable=True,
        aggregation="aggregate",
    ),
    EventSpec(key="announce_fetch_summary", notify_event="user_activity", content_type="list",
        task_kind="announce_fetch",
        builder_ref="pilotstd.core.notification._builders_task_results:_build_announce_fetch_summary_message",
        i18n_category="notification.announce", default_channels=(), levels=("info", "warning"),
        module_key="notification.module.announce", trigger_file="pilotstd/announce/notifier.py",
        payload_keys=frozenset({"adapters", "has_error", "total_count"}), security=False, branch_by=None,
        subscribable=True, aggregation="aggregate",
    ),

    # ── 系统运维（7）──
    EventSpec(key="auto_backup", notify_event="anomaly_alert", content_type="field_list", task_kind="backup",
        builder_ref="pilotstd.core.notification._builders_system:_build_auto_backup_message",
        i18n_category="notification.system", default_channels=("wechat",), levels=("info", "error"),
        module_key="notification.module.system", trigger_file="docker/scheduler.py",
        payload_keys=frozenset({"backup_path", "error", "size_mb", "success"}), security=False, branch_by=None,
        subscribable=True, aggregation="aggregate",
    ),
    EventSpec(key="image_update_available", notify_event="anomaly_alert", content_type="text",
        task_kind="image_update",
        builder_ref="pilotstd.core.notification._builders_system:_build_image_update_available_message",
        i18n_category="notification.system", default_channels=(), levels=("info", "error"),
        module_key="notification.module.system", trigger_file="docker/api/system.py",
        payload_keys=frozenset({"error", "new_digest", "old_digest", "release_notes"}), security=False,
        branch_by=None, subscribable=True, aggregation="aggregate",
    ),
    EventSpec(key="trust_ip_update", notify_event="security_alert", content_type="field_list", task_kind="",
        builder_ref="pilotstd.core.notification._builders_system:_build_trust_ip_update_message",
        i18n_category="notification.system", default_channels=(), levels=("info", "warning"),
        module_key="notification.module.system", trigger_file="pilotstd/manager/wechat_ip_service.py",
        payload_keys=frozenset({"body", "ip", "status", "title", "update_time"}), security=False, branch_by=None,
        subscribable=True, aggregation="aggregate",
    ),
    EventSpec(key="worker_error", notify_event="anomaly_alert", content_type="text", task_kind="",
        builder_ref="pilotstd.core.notification._builders_system:_build_worker_error_message",
        i18n_category="notification.system", default_channels=(), levels=("error",),
        module_key="notification.module.system", trigger_file="pilotstd/ui/pending_query_dialog.py",
        payload_keys=frozenset({"error", "traceback", "worker"}), security=False, branch_by=None, subscribable=True,
        aggregation="aggregate",
    ),
    EventSpec(key="task_execution_failed", notify_event="anomaly_alert", content_type="text", task_kind="",
        builder_ref="pilotstd.core.notification._builders_system:_build_task_execution_failed_message",
        i18n_category="notification.system", default_channels=(), levels=("error",),
        module_key="notification.module.system", trigger_file="docker/scheduler.py",
        payload_keys=frozenset({"error", "task_name"}), security=False, branch_by=None, subscribable=True,
        aggregation="aggregate",
    ),
    EventSpec(key="quota_exhausted", notify_event="anomaly_alert", content_type="text", task_kind="",
        builder_ref="pilotstd.core.notification._builders_system:_build_quota_exhausted_message",
        i18n_category="notification.system", default_channels=(), levels=("warning",),
        module_key="notification.module.system", trigger_file="pilotstd/query/daily_quota.py",
        payload_keys=frozenset({"quota_limit", "reset_time", "site_name"}), security=False, branch_by=None,
        subscribable=True, aggregation="aggregate",
    ),
    EventSpec(key="notification_delivery_failed", notify_event="system_health", content_type="text", task_kind="",
        builder_ref="pilotstd.core.notification._builders_batch:_build_notification_delivery_failed_message",
        i18n_category="notification.system", default_channels=("wechat",), levels=("error",),
        module_key="notification.module.system", trigger_file="pilotstd/core/notification/manager.py",
        payload_keys=frozenset({"channel", "consecutive", "failures", "reason", "samples"}), security=False,
        branch_by=None, subscribable=False, aggregation="aggregate",
    ),

    # ── 收藏链（4）──
    EventSpec(key="favorite_created", notify_event="user_activity", content_type="field_list",
        task_kind="favorite_download",
        builder_ref="pilotstd.core.notification._builders_batch:_build_favorite_created_message",
        i18n_category="notification.download", default_channels=(), levels=("info",),
        module_key="notification.module.favorite", trigger_file="docker/api/favorites.py",
        payload_keys=frozenset({"record_id", "standard_name", "standard_no", "user_id"}), security=False,
        branch_by=None, subscribable=True, aggregation="aggregate",
    ),
    EventSpec(key="download_started", notify_event="task_progress", content_type="field_list",
        task_kind="favorite_download",
        builder_ref="pilotstd.core.notification._builders_batch:_build_download_started_message",
        i18n_category="notification.download", default_channels=(), levels=("info",),
        module_key="notification.module.favorite", trigger_file="pilotstd/tasks/favorite_download.py",
        # 名称：同 download_failed——载荷带「最高可得阶段名」，与生产方 _fetch_std_meta 同批对齐。
        payload_keys=frozenset(
            {"favorite_id", "standard_name", "standard_number", "user_id"}
        ), security=False, branch_by=None,
        subscribable=True, aggregation="aggregate",
    ),
    EventSpec(key="download_complete", notify_event="task_result", content_type="field_list",
        task_kind="favorite_download",
        builder_ref="pilotstd.core.notification._builders_batch:_build_download_complete_message",
        i18n_category="notification.download", default_channels=(), levels=("info",),
        module_key="notification.module.favorite", trigger_file="pilotstd/tasks/favorite_download.py",
        payload_keys=frozenset(
            {"favorite_id", "local_path", "standard_name", "standard_number", "status", "user_id"}
        ), security=False,
        branch_by=None, subscribable=True, aggregation="aggregate",
    ),
    EventSpec(key="favorite_abandoned_summary", notify_event="user_activity", content_type="list",
        task_kind="favorite_download",
        builder_ref="pilotstd.core.notification._builders_batch:_build_favorite_abandoned_summary_message",
        i18n_category="notification.download", default_channels=("wechat",), levels=("warning",),
        module_key="notification.module.favorite", trigger_file="pilotstd/services/favorite_chain_processor.py",
        payload_keys=frozenset({"details", "reasons", "retryable", "total"}), security=False, branch_by=None,
        subscribable=False, aggregation="aggregate",
    ),

    # ── 安全告警（4）──
    EventSpec(key="notification_credential_changed", notify_event="security_alert", content_type="list", task_kind="",
        builder_ref="pilotstd.core.notification._builders_system:_build_notification_credential_changed_message",
        i18n_category="notification.system", default_channels=(), levels=("warning",),
        module_key="notification.module.security", trigger_file="docker/api/notification_config.py",
        payload_keys=frozenset({"changed_keys", "from_ip", "rules_changed", "services"}), security=True,
        branch_by=None, subscribable=False, aggregation="bypass",
    ),
    EventSpec(key="security_password_changed", notify_event="security_alert", content_type="list", task_kind="",
        builder_ref="pilotstd.core.notification._builders_system:_build_security_password_changed_message",
        i18n_category="notification.system", default_channels=(), levels=("warning",),
        module_key="notification.module.security", trigger_file="docker/api/users.py",
        payload_keys=frozenset({"from_ip", "sessions_revoked", "user_id"}), security=True, branch_by=None,
        subscribable=False, aggregation="bypass",
    ),
    EventSpec(key="security_token_refreshed", notify_event="security_alert", content_type="text", task_kind="",
        builder_ref="pilotstd.core.notification._builders_system:_build_security_token_refreshed_message",
        i18n_category="notification.system", default_channels=(), levels=("warning",),
        module_key="notification.module.security", trigger_file="docker/api/settings.py",
        payload_keys=frozenset({"db_synced", "from_ip", "rotated_at"}), security=True, branch_by=None,
        subscribable=False, aggregation="bypass",
    ),
    EventSpec(key="security_login_failed", notify_event="security_alert", content_type="field_list", task_kind="",
        builder_ref="pilotstd.core.notification._builders_system:_build_security_login_failed_message",
        i18n_category="notification.system", default_channels=("wechat",), levels=("warning",),
        module_key="notification.module.security", trigger_file="docker/auth.py",
        payload_keys=frozenset({"failures", "from_ip", "username", "window_seconds"}), security=True, branch_by=None,
        subscribable=False, aggregation="aggregate",
    ),
)

# 派生视图（非第二份声明）：只需键集的消费方不必遍历规格对象
EVENT_SPEC_KEYS: tuple[str, ...] = tuple(s.key for s in EVENT_SPECS)

# 护栏：规格集合必须与事件注册表一一对应（设计 §1.1.2 要求；单测同口径复核）
assert set(EVENT_SPEC_KEYS) == {e.key for e in ALL_EVENTS}
