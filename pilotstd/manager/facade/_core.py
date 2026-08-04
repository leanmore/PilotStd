# 模块：pilotstd/manager/facade/_core.py
"""ManagerCore 依赖容器 — 组合模式重构，消除 Mixin MRO 隐式依赖。"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from ...core.config import ConfigManager
    from ...core.db import Database
    from ...core.file_index import FileIndexRepository
    from ...core.notification import NotificationManager
    from ...core.validity_checker import ValidityChecker
    from ...download.engine import DownloadEngine
    from ...download.session import SessionManager
    from ...manager.adapter_manager import AdapterManager
    from ...pipeline.router import PipelineRouter
    from ...query.cache import CacheRepository
    from ...query.daily_quota import DailyQuotaTracker
    from ...query.engine import QueryEngine
    from ...scan.parser import StandardParser
    from ...scan.scanner import FileScanner
    from ...task.pipeline_store import PipelineRunStore
    from ...task.queue import TaskQueue


@dataclass
class ManagerCore:
    """所有依赖显式声明，替代 Mixin 通过 MRO 隐式访问的属性。"""

    # ---- 配置与基础 ----
    cfg: "ConfigManager"
    db: "Database"

    # ---- 扫描与解析 ----
    parser: "StandardParser"
    scanner: "FileScanner"

    # ---- 查询子系统 ----
    query_engine: "QueryEngine"
    cache: "CacheRepository"
    quota_tracker: "DailyQuotaTracker"
    adapter_manager: "AdapterManager"

    # ---- 文件索引 ----
    file_index: "FileIndexRepository"

    # ---- 下载子系统 ----
    download_engine: "DownloadEngine"
    session_mgr: "SessionManager"
    task_queue: "TaskQueue"
    router: "PipelineRouter"
    _file_watcher: Any = field(default=None)

    # ---- 服务层（由 BaseFacade._init_services 填充） ----
    classifier: Any = field(default=None)
    organizer_svc: Any = field(default=None)
    announce_svc: Any = field(default=None)
    pending_svc: Any = field(default=None)
    scheduled_svc: Any = field(default=None)

    # ---- 其他服务 ----
    validity_checker: Optional["ValidityChecker"] = field(default=None)
    notification_mgr: Optional["NotificationManager"] = field(default=None)
    pipeline_store: Optional["PipelineRunStore"] = field(default=None)

    # ---- 运行时状态（原 Mixin 中通过 self.xxx 访问的列表） ----
    parsed_results: list[Any] = field(default_factory=list)
    queried_items: list[Any] = field(default_factory=list)
    query_results: list[Any] = field(default_factory=list)
    download_list: list[Any] = field(default_factory=list)
    expire_list: list[Any] = field(default_factory=list)
    pending_list: list[Any] = field(default_factory=list)
    download_tasks: list[Any] = field(default_factory=list)
    last_skipped_dirs: list[Any] = field(default_factory=list)
