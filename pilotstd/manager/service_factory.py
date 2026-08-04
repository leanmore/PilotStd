# 模块：项目/管理器/服务_工厂脚本
# 服务工厂—从实例创建所有子服务

from typing import Any

from ..core.config import get_library_root
from ..organizer.dir_builder import DirBuilder
from ..organizer.mover import FileMover
from .announce_service import AnnounceService
from .classifier import QueryClassifier
from .organizer_service import OrganizerService
from .pending_service import PendingService
from .scheduled_service import ScheduledService


def create_services(mgr: Any) -> tuple[Any, Any, Any, Any, Any]:
    """从 StandardManager 实例创建所有子服务并返回元组。

    StandardManager.__init__ 中调用：
        (self._classifier, self._organizer_svc, self._announce_svc,
         self._pending_svc, self._scheduled_svc) = service_factory.create_services(self)

    返回:
        (QueryClassifier, OrganizerService, AnnounceService, PendingService, ScheduledService)
    """
    # ── 归类子系统依赖 ──
    root = get_library_root(mgr.cfg)
    dir_builder = DirBuilder(root)
    file_mover = FileMover(dir_builder)

    # ── 查询分类服务 ──
    classifier = QueryClassifier(
        router=mgr.router,
        query_adapters=mgr._query_adapters,
        quota_tracker=mgr.quota_tracker,
        query_engine=mgr.query_engine,
    )

    # ── 归类服务 ──
    organizer_svc = OrganizerService(
        cfg=mgr.cfg,
        file_index=mgr.file_index,
        dir_builder=dir_builder,
        file_mover=file_mover,
    )

    # ── 公告服务 ──
    ocr_config = {
        "provider": mgr.cfg.get("ocr.provider", ""),
        # 百度云（新键优先，旧键兼容）
        "baidu_api_key": mgr.cfg.get("ocr.baidu_api_key", ""),
        "baidu_secret_key": mgr.cfg.get("ocr.baidu_secret_key", ""),
        # 腾讯云
        "tencent_secret_id": mgr.cfg.get("ocr.tencent_secret_id", ""),
        "tencent_secret_key": mgr.cfg.get("ocr.tencent_secret_key", ""),
        # 阿里云
        "aliyun_access_key_id": mgr.cfg.get("ocr.aliyun_access_key_id", ""),
        "aliyun_access_key_secret": mgr.cfg.get("ocr.aliyun_access_key_secret", ""),
        # 旧键兼容（单模式时可能存了值）
        "api_key": mgr.cfg.get("ocr.api_key", ""),
        "secret_key": mgr.cfg.get("ocr.secret_key", ""),
        "secret_id": mgr.cfg.get("ocr.secret_id", ""),
        "access_key_id": mgr.cfg.get("ocr.access_key_id", ""),
        "access_key_secret": mgr.cfg.get("ocr.access_key_secret", ""),
    }
    announce_svc = AnnounceService(file_index=mgr.file_index, ocr_config=ocr_config)

    # ── 待确认/下载队列服务 ──
    pending_svc = PendingService(
        db=mgr.db,
        file_index=mgr.file_index,
    )

    # ── 定时任务服务 ──
    scheduled_svc = ScheduledService(
        cfg=mgr.cfg,
        scanner=mgr.scanner,
        parser=mgr.parser,
        query_engine=mgr.query_engine,
        file_index=mgr.file_index,
        quota_tracker=mgr.quota_tracker,
        download_engine=mgr.download_engine,
    )

    return (classifier, organizer_svc, announce_svc, pending_svc, scheduled_svc)
