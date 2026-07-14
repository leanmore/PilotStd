# pilotstd/manager/facade/_base.py
"""BaseFacade：构建 ManagerCore，初始化各子系统，组合 Handler。"""

from __future__ import annotations

import logging
from typing import List, Optional

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
from ...query.adapters.csres import CsresAdapter
from ...query.adapters.dbba import DbbaAdapter
from ...query.adapters.hbba import HbbaAdapter
from ...query.adapters.iso_gov import IsoGovAdapter
from ...query.adapters.njbz365 import Njbz365Adapter
from ...query.adapters.std_gov import StdGovAdapter
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
    """依赖组装层 — 构造函数 + 生命周期管理。"""

    def __init__(
        self,
        config: Optional[ConfigManager] = None,
        db: Optional[Database] = None,
        query_adapters: Optional[List[BaseAdapter]] = None,
        download_adapters: Optional[List[BaseDownloadAdapter]] = None,
    ) -> None:
        # ---- 1. 初始化 _core 容器（先占位，后面逐步填充） ----
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

        # ---- 2. 初始化各子系统（填充 _core） ----
        self._init_config_and_scanner(config)
        self._init_query_subsystem(query_adapters)
        self._init_download(download_adapters)
        self._init_services()

        # ---- 3. 初始化 Handler（注入 _core） ----
        self._query_handler = QueryHandler(self._core)
        self._download_handler = DownloadHandler(self._core)
        self._scan_handler = ScanHandler(self._core)
        self._organize_handler = OrganizeHandler(self._core)
        self._file_index_handler = FileIndexHandler(self._core)
        self._download_handler._set_organize_handler(self._organize_handler)
        self._auto_pipeline = AutoPipeline(
            self._core,
            self._scan_handler,
            self._query_handler,
            self._download_handler,
            self._organize_handler,
        )

        # ---- 4. 绑定方法到 self（对外 API 不变） ----
        self._bind_methods()

        # ---- 5. 初始化运行时状态列表（原 Mixin 中定义的） ----
        self._parsed_results = []
        self._queried_items = []
        self._query_results = []
        self._download_list = []
        self._expire_list = []
        self._pending_list = []
        self._download_tasks = []

    def _init_config_and_scanner(self, config: Optional[ConfigManager]) -> None:
        """初始化配置、数据库、扫描子系统。"""
        self._core.cfg = config or ConfigManager()
        self._core.db = Database(get_db_path())
        code_mapping = build_code_mapping()
        self._core.parser = StandardParser(code_mapping)
        self._core.scanner = FileScanner(self._core.cfg)

    def _init_query_subsystem(self, query_adapters: Optional[List[BaseAdapter]]) -> None:
        """初始化查询子系统：适配器、站点轮转器、配额追踪、缓存、QueryEngine。"""
        from ...query.adapters.ahbz import AhbzAdapter

        csres = CsresAdapter()
        adapters = query_adapters or [
            AhbzAdapter(),
            Njbz365Adapter(),
            StdGovAdapter(),
            HbbaAdapter(),
            IsoGovAdapter(),
            DbbaAdapter(),
            csres,
        ]
        self._core._query_adapters = adapters  # type: ignore[attr-defined]

        from ...query.site_config import create_default_sites

        sites = create_default_sites()
        rotator = SiteRotator(sites, db=self._core.db)
        csres.set_rotator(rotator)

        daily_limits = {s.name: s.daily_limit for s in sites if s.daily_limit > 0}
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

        # 兼容旧代码：外部可能直接访问 self._announce_svc
        self._announce_svc = announce_svc
        self._announce_svc._mgr = self  # type: ignore[attr-defined]

        from ..user_service import UserService
        from ..validity_service import ValidityService

        self._core.validity_checker = ValidityChecker(self._core.db)
        self._core.notification_mgr = NotificationManager(self._core.cfg, self._core.db, user_id=1)
        self._core.pipeline_store = PipelineRunStore(self._core.db)

        self._validity_service = ValidityService(self)
        self._user_service = UserService(self)

    def _init_notification(self) -> None:
        """重新初始化通知模块（配置变更后调用）。"""
        self._core.notification_mgr = NotificationManager(self._core.cfg, self._core.db, user_id=1)

    def _bind_methods(self) -> None:
        """将 Handler 方法绑定到 self，保持对外 API 不变。"""
        # ---- ScanHandler ----
        self.scan_directory = self._scan_handler.scan_directory
        self.scan_directory_stream = self._scan_handler.scan_directory_stream
        self.scan_stream = self._scan_handler.scan_stream
        self.scan_and_index = self._scan_handler.scan_and_index
        self.start_watching = self._scan_handler.start_watching
        self.stop_watching = self._scan_handler.stop_watching

        # ---- QueryHandler ----
        self.query = self._query_handler.query
        self.query_stream = self._query_handler.query_stream
        self.set_pause_event = self._query_handler.set_pause_event
        self.get_quota_info = self._query_handler.get_quota_info
        self.plan_batch = self._query_handler.plan_batch
        self.get_stage_queue = self._query_handler.get_stage_queue
        self.get_stage_summary = self._query_handler.get_stage_summary
        self.record_pending = self._query_handler.record_pending
        self.resolve_pending = self._query_handler.resolve_pending
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

        # ---- DownloadHandler ----
        self.download = self._download_handler.download
        self.download_stream = self._download_handler.download_stream
        self.download_by_numbers = self._download_handler.download_by_numbers
        self.enqueue_download_wait = self._download_handler.enqueue_download_wait
        self.get_due_downloads = self._download_handler.get_due_downloads
        self.remove_download_queue = self._download_handler.remove_download_queue

        # ---- OrganizeHandler ----
        self.archive_standards = self._organize_handler.archive_standards
        self.organize_skipped_dirs = self._organize_handler.organize_skipped_dirs
        self.organize_fallback = self._organize_handler.organize_fallback
        self.handle_expired = self._organize_handler.handle_expired
        self.merge_expire_from_source = self._organize_handler.merge_expire_from_source
        self.organize_files = self._organize_handler.organize_files
        self.expire_files = self._organize_handler.expire_files
        self.normalize_files = self._organize_handler.normalize_files
        self.normalize_files_stream = self._organize_handler.normalize_files_stream

        # ---- FileIndexHandler ----
        self.upsert_file_index = self._file_index_handler.upsert_file_index
        self.get_file_index = self._file_index_handler.get_file_index
        self.get_file_index_full_info = self._file_index_handler.get_file_index_full_info
        self.parse_standard_number = self._file_index_handler.parse_standard_number
        self.restore_parsed_from_index = self._file_index_handler.restore_parsed_from_index

        # ---- AutoPipeline ----
        self.auto_run = self._auto_pipeline.auto_run
        self.auto_run_stream = self._auto_pipeline.auto_run_stream

        # ---- 兼容旧代码：_classifier、_organizer_svc 等（通过 @property 代理到 _core） ----
        self._classifier = self._core.classifier

    # ===== 兼容旧代码的属性代理 =====

    @property
    def cfg(self):
        return self._core.cfg

    @property
    def db(self):
        return self._core.db

    @property
    def parser(self):
        return self._core.parser

    @property
    def scanner(self):
        return self._core.scanner

    @property
    def query_engine(self):
        return self._core.query_engine

    @query_engine.setter
    def query_engine(self, value):
        self._core.query_engine = value

    @property
    def cache(self):
        return self._core.cache

    @property
    def quota_tracker(self):
        return self._core.quota_tracker

    @property
    def adapter_manager(self):
        return self._core.adapter_manager

    @property
    def file_index(self):
        return self._core.file_index

    @property
    def download_engine(self):
        return self._core.download_engine

    @download_engine.setter
    def download_engine(self, value):
        self._core.download_engine = value

    @property
    def router(self):
        return self._core.router

    @property
    def task_queue(self):
        return self._core.task_queue

    @property
    def _query_adapters(self):
        return self._core._query_adapters  # type: ignore[attr-defined]

    @property
    def notification_mgr(self):
        return self._core.notification_mgr

    @property
    def validity_checker(self):
        return self._core.validity_checker

    @property
    def _announce_svc(self):
        return self._core.announce_svc

    @_announce_svc.setter
    def _announce_svc(self, value):
        self._core.announce_svc = value

    @property
    def _organizer_svc(self):
        return self._core.organizer_svc

    @property
    def _pending_svc(self):
        return self._core.pending_svc

    @_pending_svc.setter
    def _pending_svc(self, value):
        self._core.pending_svc = value

    @property
    def user_service(self):
        return self._user_service

    @property
    def _scheduled_svc(self):
        return self._core.scheduled_svc

    @_scheduled_svc.setter
    def _scheduled_svc(self, value):
        self._core.scheduled_svc = value

    @property
    def _classifier(self):
        return self._core.classifier

    @_classifier.setter
    def _classifier(self, value):
        self._core.classifier = value

    # ===== 运行时状态列表的属性代理 =====

    @property
    def _parsed_results(self):
        return self._core.parsed_results

    @_parsed_results.setter
    def _parsed_results(self, value):
        self._core.parsed_results = value

    @property
    def _queried_items(self):
        return self._core.queried_items

    @_queried_items.setter
    def _queried_items(self, value):
        self._core.queried_items = value

    @property
    def _query_results(self):
        return self._core.query_results

    @_query_results.setter
    def _query_results(self, value):
        self._core.query_results = value

    @property
    def _download_list(self):
        return self._core.download_list

    @_download_list.setter
    def _download_list(self, value):
        self._core.download_list = value

    @property
    def _expire_list(self):
        return self._core.expire_list

    @_expire_list.setter
    def _expire_list(self, value):
        self._core.expire_list = value

    @property
    def _pending_list(self):
        return self._core.pending_list

    @_pending_list.setter
    def _pending_list(self, value):
        self._core.pending_list = value

    @property
    def _download_tasks(self):
        return self._core.download_tasks

    @_download_tasks.setter
    def _download_tasks(self, value):
        self._core.download_tasks = value

    @property
    def _last_skipped_dirs(self):
        return self._core.last_skipped_dirs

    @_last_skipped_dirs.setter
    def _last_skipped_dirs(self, value):
        self._core.last_skipped_dirs = value

    @property
    def _file_watcher(self):
        return self._core._file_watcher

    @_file_watcher.setter
    def _file_watcher(self, value):
        self._core._file_watcher = value

    def shutdown(self) -> None:
        """关闭数据库连接，应用退出时调用。"""
        if self._core.db:
            self._core.db.close_all()
