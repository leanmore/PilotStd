# pilotstd/manager/facade/_base.py
# StandardManager 核心 — 依赖组装 + 生命周期
"""BaseFacade：构造函数、子系统初始化、关闭。"""

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
from ...models import ParsedStdInfo
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
from ...task.queue import TaskQueue
from ..export_service import ExportService
from ..monitor_service import MonitorService
from ..quality_service import QualityService
from ..standard_service import StandardService
from ..system_service import SystemService
from ..wechat_ip_service import WechatIPService

logger = logging.getLogger(__name__)


class BaseFacade:
    """依赖组装层 — 构造函数 + 生命周期管理。"""

    def _init_config_and_scanner(self, config: ConfigManager | None) -> None:
        """初始化配置、数据库、扫描子系统。"""
        self.cfg = config or ConfigManager()
        self.db = Database(get_db_path())
        code_mapping = build_code_mapping()
        self.parser = StandardParser(code_mapping)
        self.scanner = FileScanner(self.cfg)

    def _init_query_subsystem(self, query_adapters: list[BaseAdapter] | None) -> None:
        """初始化查询子系统：适配器、站点轮转器、配额追踪、缓存、QueryEngine。"""
        from ...query.adapters.ahbz import AhbzAdapter

        csres = CsresAdapter()
        self._query_adapters = query_adapters or [
            AhbzAdapter(),
            Njbz365Adapter(),
            StdGovAdapter(),
            HbbaAdapter(),
            IsoGovAdapter(),
            DbbaAdapter(),
            csres,
        ]
        adapters = self._query_adapters
        from ...query.site_config import create_default_sites

        sites = create_default_sites()
        rotator = SiteRotator(sites, db=self.db)
        csres.set_rotator(rotator)
        daily_limits = {s.name: s.daily_limit for s in sites if s.daily_limit > 0}
        self.quota_tracker = DailyQuotaTracker(self.db, limits=daily_limits)
        self.cache = CacheRepository(self.db)
        self.file_index = FileIndexRepository(self.db)

        from ..adapter_manager import AdapterManager

        self.adapter_manager = AdapterManager(db=self.db, rotator=rotator, quota_tracker=self.quota_tracker)

        qi_cfg = self.cfg.get("query.query_interval", None)
        query_interval = tuple(qi_cfg) if qi_cfg and len(qi_cfg) == 2 else None
        self.query_engine = QueryEngine(
            adapters, self.cache, use_cache=self.cfg.get("query.use_cache", True),
            rotator=rotator, quota_tracker=self.quota_tracker,
            query_interval=query_interval, parser=self.parser,
        )

    def _init_download(self, download_adapters: list[BaseDownloadAdapter] | None) -> None:
        """初始化下载子系统 + 任务队列 + 文件监控。"""
        self.session_mgr = SessionManager(default_timeout=self.cfg.get("network.timeout", 30))
        dl_adapter = download_adapters or [OpenstdDownloadAdapter(self.session_mgr.create_session())]
        save_root = get_library_root(self.cfg)
        self.download_engine = DownloadEngine(dl_adapter, self.session_mgr, save_root=save_root)
        self.task_queue = TaskQueue(self.db)

        from ...pipeline.router import PipelineRouter

        self.router = PipelineRouter()
        self._file_watcher = None
        self._last_skipped_dirs: list[Any] = []

    def _init_services(self) -> None:
        """初始化子服务、校验器、通知模块。"""
        from ..service_factory import create_services

        (self._classifier, self._organizer_svc, self._announce_svc, self._pending_svc, self._scheduled_svc) = (
            create_services(self)
        )
        self._announce_svc._mgr = self
        self.announce_service = self._announce_svc

        from ..user_service import UserService
        from ..validity_service import ValidityService

        self.validity_service = ValidityService(self)
        self.user_service = UserService(self)
        self.standard_service = StandardService(self)
        self.export_service = ExportService(self)
        self.system_service = SystemService(self)
        self.monitor_service = MonitorService(self)
        self.wechat_ip_service = WechatIPService(self)
        self.quality_service = QualityService(self)
        self.validity_checker = ValidityChecker(self.db)
        self.notification_mgr = NotificationManager(self.cfg, self.db)

    def __init__(
        self,
        config: Optional[ConfigManager] = None,
        db: Optional[Database] = None,
        query_adapters: Optional[List[BaseAdapter]] = None,
        download_adapters: Optional[List[BaseDownloadAdapter]] = None,
    ) -> None:
        self._init_config_and_scanner(config)
        self._init_query_subsystem(query_adapters)
        self._init_download(download_adapters)
        self._init_services()

        self._parsed_results: List[ParsedStdInfo] = []
        self._queried_items: List[ParsedStdInfo] = []
        self._query_results: List[Any] = []
        self._download_list: List[ParsedStdInfo] = []
        self._expire_list: List[ParsedStdInfo] = []
        self._pending_list: List[ParsedStdInfo] = []
        self._download_tasks: List[Any] = []

    def _init_notification(self) -> None:
        """重新初始化通知模块（配置变更后调用）。"""
        self.notification_mgr = NotificationManager(self.cfg, self.db)

    def shutdown(self) -> None:
        """关闭数据库连接，应用退出时调用。"""
        if self.db:
            self.db.close_all()
