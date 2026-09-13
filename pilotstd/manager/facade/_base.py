# 模块：项目/管理器/门面/_脚本
"""BaseFacade：构建 ManagerCore，初始化各子系统，组合 Handler。"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from ...core.config import ConfigManager, get_db_path, get_library_root
from ...core.db import Database
from ...core.file_index import FileIndexRepository
from ...core.notification import NotificationManager
from ...core.validity_checker import ValidityChecker
from ...download.adapters.base import BaseDownloadAdapter
from ...download.adapters.openstd_download import OpenstdDownloadAdapter
from ...download.engine import DownloadEngine
from ...download.session import SessionManager
from ...organizer.industry_lookup import build_code_mapping
from ...query.adapters.base import BaseAdapter
from ...query.cache import CacheRepository
from ...query.daily_quota import DailyQuotaTracker
from ...query.engine import QueryEngine
from ...query.rotator import SiteRotator
from ...scan.parser import StandardParser
from ...scan.scanner import FileScanner
from ...task.pipeline_store import PipelineRunStore
from ...task.queue import TaskQueue
from ._auto import AutoPipeline
from ._core import ManagerCore
from ._download import DownloadHandler
from ._file_index import FileIndexHandler
from ._organize import OrganizeHandler
from ._query import QueryHandler
from ._scan import ScanHandler

logger = logging.getLogger(__name__)


class BaseFacade:
    """依赖组装层 — 构造函数 + 生命周期管理。

    属性代理：_CORE_PROXY_WHITELIST 中的属性自动委托到 self._core（替代原 _BasePropertiesMixin）。
    """

    # 原_的42个@委托，压缩为白名单+____/____
    _CORE_PROXY_WHITELIST: frozenset[str] = frozenset({
        # 核心组件
        "cfg", "db", "parser", "scanner", "query_engine", "cache", "quota_tracker",
        "adapter_manager", "file_index", "download_engine", "router", "task_queue",
        "_query_adapters", "notification_mgr", "validity_checker",
        # 服务层
        "_announce_svc", "_organizer_svc", "_pending_svc", "_scheduled_svc", "_classifier", "_archive_retry_svc",
        # 运行时状态列表
        "parsed_results", "queried_items", "query_results",
        "download_list", "expire_list", "pending_list",
        "download_tasks", "last_skipped_dirs", "_file_watcher",
    })

    # 自身属性（非_核心代理，由__服务直接设置）
    @property
    def validity_service(self):
        return self._validity_service

    @property
    def standard_service(self):
        return self._standard_service

    @property
    def user_service(self):
        return self._user_service

    def __getattr__(self, name: str):
        """白名单内的属性 → 委托给 self._core。"""
        if name in self._CORE_PROXY_WHITELIST:
            return getattr(self._core, name)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def __setattr__(self, name: str, value) -> None:
        """白名单内的属性写入 → 委托给 self._core；否则走标准流程。"""
        cls = type(self)
        if name in getattr(cls, "_CORE_PROXY_WHITELIST", frozenset()):
            setattr(self._core, name, value)
        else:
            super().__setattr__(name, value)


    def __init__(
        self,
        config: Optional[ConfigManager] = None,
        db: Optional[Database] = None,
        query_adapters: Optional[List[BaseAdapter]] = None,
        download_adapters: Optional[List[BaseDownloadAdapter]] = None,
    ) -> None:
        # 1.初始化_核心容器（先占位，后面逐步填充）
        self._core = ManagerCore(
            cfg=None,  # type: ignore[arg-type]
            db=None,  # type: ignore[arg-type]
            parser=None,  # type: ignore[arg-type]
            scanner=None,  # type: ignore[arg-type]
            query_engine=None,  # type: ignore[arg-type]
            cache=None,  # type: ignore[arg-type]
            quota_tracker=None,  # type: ignore[arg-type]
            adapter_manager=None,  # type: ignore[arg-type]
            file_index=None,  # type: ignore[arg-type]
            download_engine=None,  # type: ignore[arg-type]
            session_mgr=None,  # type: ignore[arg-type]
            task_queue=None,  # type: ignore[arg-type]
            router=None,  # type: ignore[arg-type]
            validity_checker=None,  # type: ignore[arg-type]
            notification_mgr=None,  # type: ignore[arg-type]
            pipeline_store=None,  # type: ignore[arg-type]
        )

        # 2.初始化各子系统（填充_核心）
        self._init_config_and_scanner(config)
        self._init_query_subsystem(query_adapters)
        self._init_download(download_adapters)
        self._init_services()

        # 3.初始化（注入_核心）
        self._query_handler = QueryHandler(self._core)
        self._download_handler = DownloadHandler(self._core)
        self._scan_handler = ScanHandler(self._core)
        self._organize_handler = OrganizeHandler(self._core)
        self._file_index_handler = FileIndexHandler(self._core)
        self._auto_pipeline = AutoPipeline(
            self._core,
            self._scan_handler,
            self._query_handler,
            self._download_handler,
            self._organize_handler,
        )

        # 4.绑定方法到（对外接口不变）
        self._bind_methods()

        # 5.初始化运行时状态列表
        self._parsed_results: list[Any] = []
        self._queried_items: list[Any] = []
        self._query_results: list[Any] = []
        self._download_list: list[Any] = []
        self._expire_list: list[Any] = []
        self._pending_list: list[Any] = []
        self._download_tasks: list[Any] = []

    def _init_config_and_scanner(self, config: Optional[ConfigManager]) -> None:
        """初始化配置、数据库、扫描子系统。"""
        self._core.cfg = config or ConfigManager()
        self._core.db = Database(get_db_path())
        code_mapping = build_code_mapping()
        self._core.parser = StandardParser(code_mapping)
        self._core.scanner = FileScanner(self._core.cfg)

    def _init_query_subsystem(self, query_adapters: Optional[List[BaseAdapter]]) -> None:
        """初始化查询子系统：适配器、站点轮转器、配额追踪、缓存、QueryEngine。"""
        from ...query.adapters.registry import instantiate_all

        if query_adapters:
            adapters = query_adapters
        else:
            adapters, _disabled = instantiate_all()

        csres = next((a for a in adapters if a.site_name == "csres"), None)
        self._core._query_adapters = adapters  # type: ignore[attr-defined]

        from ...query.site_config import create_default_sites

        sites = create_default_sites()
        rotator = SiteRotator(sites, db=self._core.db)
        if csres is not None:
            csres.set_rotator(rotator)  # type: ignore[attr-defined]  # csres 子类动态注入

        daily_limits = {s.name: s.daily_limit for s in sites if s.daily_limit > 0}
        logger.debug("配额追踪器日限额来自 create_default_sites() 统一出口（含 config.json UI 覆盖）")
        self._core.quota_tracker = DailyQuotaTracker(self._core.db, limits=daily_limits)
        self._core.cache = CacheRepository(self._core.db)
        self._core.file_index = FileIndexRepository(self._core.db)

        from ..adapter_manager import AdapterManager

        self._core.adapter_manager = AdapterManager(
            db=self._core.db, rotator=rotator, quota_tracker=self._core.quota_tracker
        )

        qi_cfg = self._core.cfg.get("query.query_interval", None)
        query_interval = tuple(qi_cfg) if qi_cfg and len(qi_cfg) == 2 else None

        self._core.query_engine = QueryEngine(
            adapters,
            self._core.cache,
            use_cache=self._core.cfg.get("query.use_cache", True),
            rotator=rotator,
            quota_tracker=self._core.quota_tracker,
            query_interval=query_interval,
            parser=self._core.parser,
        )

    def _init_download(self, download_adapters: Optional[List[BaseDownloadAdapter]]) -> None:
        """初始化下载子系统 + 任务队列 + 文件监控。"""
        self._core.session_mgr = SessionManager(default_timeout=self._core.cfg.get("network.timeout", 30))
        dl_adapter = download_adapters or [OpenstdDownloadAdapter(self._core.session_mgr.create_session())]
        save_root = get_library_root(self._core.cfg)
        self._core.download_engine = DownloadEngine(dl_adapter, self._core.session_mgr, save_root=save_root)
        self._core.task_queue = TaskQueue(self._core.db)

        from ...pipeline.router import PipelineRouter

        self._core.router = PipelineRouter()
        self._core._file_watcher = None

    def _init_services(self) -> None:
        """初始化子服务、校验器、通知模块。"""
        from ..service_factory import create_services

        classifier, organizer_svc, announce_svc, pending_svc, scheduled_svc = create_services(self)

        self._core.classifier = classifier
        self._core.organizer_svc = organizer_svc
        self._core.announce_svc = announce_svc
        self._core.pending_svc = pending_svc
        self._core.scheduled_svc = scheduled_svc

        # 兼容旧代码：外部可能直接访问.__
        self._announce_svc = announce_svc
        self._announce_svc._mgr = self  # type: ignore[attr-defined]

        from ..archive_retry_service import ArchiveRetryService

        self._archive_retry_svc = ArchiveRetryService(self)

        from ..standard_service import StandardService
        from ..system_service import SystemService
        from ..user_service import UserService
        from ..validity_service import ValidityService

        self._core.validity_checker = ValidityChecker(self._core.db)
        self._core.notification_mgr = NotificationManager(self._core.cfg, self._core.db, user_id=1)
        self._core.quota_tracker.set_notification_mgr(self._core.notification_mgr)
        self._core.pipeline_store = PipelineRunStore(self._core.db)

        self._validity_service = ValidityService(self)
        self._standard_service = StandardService(self)
        self._user_service = UserService(self)
        # 系统状态服务：docker/api/system.py::system_health 依赖 mgr.system_service，
        # 此前未接线导致该端点恒 500（AttributeError）
        self.system_service = SystemService(self)

        from ..wechat_ip_service import WechatIPService

        self.wechat_ip_service = WechatIPService(self)

        from ..monitor_service import MonitorService

        self.monitor_service = MonitorService(self)

    def _init_notification(self) -> None:
        """重新初始化通知模块（配置变更后调用）。"""
        self._core.notification_mgr = NotificationManager(self._core.cfg, self._core.db, user_id=1)

    def _bind_methods(self) -> None:
        """将 Handler 方法绑定到 self，保持对外 API 不变。"""
        # ---- 扫描处理器 ----
        self.scan_directory = self._scan_handler.scan_directory
        self.scan_directory_stream = self._scan_handler.scan_directory_stream
        self.scan_stream = self._scan_handler.scan_stream
        self.scan_and_index = self._scan_handler.scan_and_index
        self.start_watching = self._scan_handler.start_watching
        self.stop_watching = self._scan_handler.stop_watching

        # ---- 查询处理器 ----
        self.query = self._query_handler.query
        self.query_stream = self._query_handler.query_stream
        self.set_pause_event = self._query_handler.set_pause_event
        self.get_quota_info = self._query_handler.get_quota_info
        self.plan_batch = self._query_handler.plan_batch
        self.get_stage_queue = self._query_handler.get_stage_queue
        self.get_stage_summary = self._query_handler.get_stage_summary
        self.record_pending = self._query_handler.record_pending
        self.resolve_pending = self._query_handler.resolve_pending
        self.resolve_pending_by_numbers = self._query_handler.resolve_pending_by_numbers
        self.get_pending_items = self._query_handler.get_pending_items
        self.increment_requery_count = self._query_handler.increment_requery_count
        self.is_requery_exhausted = self._query_handler.is_requery_exhausted
        self.mark_manual_required = self._query_handler.mark_manual_required
        self.get_requery_count = self._query_handler.get_requery_count
        self.query_local_cache = self._query_handler.query_local_cache
        self.query_by_numbers = self._query_handler.query_by_numbers
        self.get_query_sites = self._query_handler.get_query_sites
        self.get_site_adapter = self._query_handler.get_site_adapter
        self.get_site_cooldown = self._query_handler.get_site_cooldown
        self.get_query_status = self._query_handler.get_query_status
        self.get_adapter_report = self._query_handler.get_adapter_report

        # ---- 下载处理器 ----
        self.download = self._download_handler.download
        self.download_stream = self._download_handler.download_stream
        self.download_by_numbers = self._download_handler.download_by_numbers
        self.enqueue_download_wait = self._download_handler.enqueue_download_wait
        self.get_due_downloads = self._download_handler.get_due_downloads
        self.remove_download_queue = self._download_handler.remove_download_queue

        # ---- 归档处理器 ----
        self.archive_standards = self._organize_handler.archive_standards
        self.organize_skipped_dirs = self._organize_handler.organize_skipped_dirs
        self.organize_fallback = self._organize_handler.organize_fallback
        self.merge_expire_from_source = self._organize_handler.merge_expire_from_source
        self.organize_files = self._organize_handler.organize_files
        self.expire_files = self._organize_handler.expire_files
        self.normalize_files = self._organize_handler.normalize_files
        self.normalize_files_stream = self._organize_handler.normalize_files_stream

        # ---- 文件索引处理器 ----
        self.upsert_file_index = self._file_index_handler.upsert_file_index
        self.get_file_index = self._file_index_handler.get_file_index
        self.get_file_index_full_info = self._file_index_handler.get_file_index_full_info
        self.parse_standard_number = self._file_index_handler.parse_standard_number
        self.restore_parsed_from_index = self._file_index_handler.restore_parsed_from_index

        # ---- 自动流水线 ----
        self.auto_run = self._auto_pipeline.auto_run
        self.auto_run_stream = self._auto_pipeline.auto_run_stream

        # 兼容旧代码：_分类器已由____代理到_核心

    def shutdown(self) -> None:
        """关闭数据库连接，应用退出时调用。"""
        if self._core.db:
            self._core.db.close_all()
