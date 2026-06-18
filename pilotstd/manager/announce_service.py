# pilotstd/manager/announce_service.py
# AnnounceService — 公告检查，从各公告源抓取新公告并匹配本地标准

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Optional

from ..announcement.adapters import SamrDbAdapter, SamrGbAdapter, SamrHbAdapter
from ..announcement.engine import AnnounceEngine
from ..announcement.matcher import AnnouncementMatcher
from ..core.config import get_data_dir

logger = logging.getLogger(__name__)


class AnnounceService:
    """公告检查服务：从 SAMR 公告源抓取 GB/HB/DB 新公告，与本地标准库匹配。

    引擎 + 适配器 + OCR provider 实例级复用，避免每次调用重建。
    支持用户通过 ConfigManager 配置 OCR 提供商（baidu/tencent/aliyun）。
    """

    def __init__(self, file_index, ocr_config: dict | None = None):
        """注入依赖。

        Args:
            file_index: FileIndexRepository 实例（提供 _db 访问和 fetch_log 表）
            ocr_config: 可选，OCR 提供商配置
                {"provider": "baidu", "api_key": "...", "secret_key": "..."}
        """
        self._file_index = file_index
        self._engine: Optional[AnnounceEngine] = None
        self._ocr_config = ocr_config or {}
        self._ocr_provider = None  # 懒加载

    def _get_ocr_provider(self):
        """懒加载 OCR provider，首次调用时从配置创建。"""
        if self._ocr_provider is None and self._ocr_config:
            from ..announcement.ocr import create_ocr_provider

            self._ocr_provider = create_ocr_provider(self._ocr_config)
        return self._ocr_provider

    def _get_or_create_engine(self) -> AnnounceEngine:
        """获取或创建引擎实例（复用）。"""
        if self._engine is None:
            adapters = [SamrGbAdapter(), SamrHbAdapter(), SamrDbAdapter()]
            matcher = AnnouncementMatcher(self._file_index._db)
            self._engine = AnnounceEngine(adapters=adapters, matcher=matcher)
        return self._engine

    def check_announcements(self) -> dict:
        """检查各公告源的新公告，匹配本地标准，返回 {matched: int, error: str}。"""

        data_dir = get_data_dir()
        for std_type in ("gb", "hb", "db"):
            os.makedirs(
                os.path.join(data_dir, "announcements", std_type), exist_ok=True
            )

        engine = self._get_or_create_engine()
        ocr = self._get_ocr_provider()
        total_matched = 0

        for adapter in engine.adapters:
            log_row = self._file_index._db.fetchone(
                "SELECT * FROM fetch_log WHERE source_site=?", (adapter.source_site,)
            )
            since = log_row["last_notice_date"] if log_row else ""

            result = engine.check_one(
                adapter.standard_type, since_date=since, ocr_provider=ocr
            )
            if "error" in result:
                logger.warning(
                    "公告适配器 %s 异常: %s",
                    adapter.source_site,
                    result.get("error", ""),
                )
                continue
            total_matched += result.get("matched", 0)

            now = datetime.now().isoformat()
            latest_date = result.get("last_notice_date", "")
            log_row = self._file_index._db.fetchone(
                "SELECT * FROM fetch_log WHERE source_site=?", (adapter.source_site,)
            )
            if log_row:
                self._file_index._db.execute(
                    "UPDATE fetch_log SET last_fetched_at=?, last_notice_date=? "
                    "WHERE source_site=?",
                    (now, latest_date, adapter.source_site),
                )
            else:
                self._file_index._db.execute(
                    "INSERT INTO fetch_log "
                    "(source_site, last_fetched_at, last_notice_date) "
                    "VALUES (?, ?, ?)",
                    (adapter.source_site, now, latest_date),
                )

        return {"matched": total_matched, "error": ""}

    def check_announcements_filtered(
        self, std_type: str | None = None, since_date: str = "", progress_callback=None
    ) -> dict:
        """带类型过滤和日期筛选的公告检查。供 CLI 调用。"""
        engine = self._get_or_create_engine()
        ocr = self._get_ocr_provider()

        if std_type:
            result = engine.check_one(
                std_type,
                since_date=since_date,
                ocr_provider=ocr,
                progress_callback=progress_callback,
            )
            return {std_type: result}

        results = {}
        for adapter in engine.adapters:
            result = engine.check_one(
                adapter.standard_type,
                since_date=since_date,
                ocr_provider=ocr,
                progress_callback=progress_callback,
            )
            results[adapter.standard_type] = result
        return results
