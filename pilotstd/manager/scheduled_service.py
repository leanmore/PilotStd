# pilotstd/manager/scheduled_service.py
# ScheduledService — 定时任务专用方法：扫描入库、更新检测、批量查询/下载

import os
import logging
from typing import List

from ..core.config import get_library_root
from ..scan.scanner import FileScanner
from ..download.models import DownloadTask

logger = logging.getLogger(__name__)


class ScheduledService:
    """定时任务服务：提供扫描入库、版本更新检测、按号查询/下载等批量操作。

    这些方法供定时任务（scheduler）调用，不依赖 UI 交互，直接操作底层引擎。
    """

    def __init__(self, cfg, scanner, parser, query_engine, file_index,
                 quota_tracker, download_engine):
        """注入依赖。

        Args:
            cfg: ConfigManager 实例
            scanner: FileScanner 实例
            parser: StandardParser 实例
            query_engine: QueryEngine 实例
            file_index: FileIndexRepository 实例
            quota_tracker: DailyQuotaTracker 实例
            download_engine: DownloadEngine 实例
        """
        self._cfg = cfg
        self._scanner = scanner
        self._parser = parser
        self._query_engine = query_engine
        self._file_index = file_index
        self._quota_tracker = quota_tracker
        self._download_engine = download_engine

    # ════════════════════════════════════════════════════════════════
    # 扫描入库
    # ════════════════════════════════════════════════════════════════

    def scan_and_index(self, root_path: str = None) -> int:
        """定时任务专用：扫描目录 → 解析 → 写入 file_index。返回入库文件数。"""
        root = root_path or get_library_root(self._cfg)
        if not os.path.isdir(root):
            logger.warning(f"scan_and_index: 路径不存在 {root}")
            return 0
        scanner = FileScanner(self._cfg)
        result = scanner.scan([root])
        count = 0
        for f in result.files:
            info = self._parser.parse(f.filename)
            if info:
                self._file_index.upsert(f.full_path, info.logical_code, info.number,
                                        info.year, info.part, info.std_name, status="现行")
                count += 1
        logger.info(f"scan_and_index: {count} 文件入库")
        return count

    # ════════════════════════════════════════════════════════════════
    # 更新检测
    # ════════════════════════════════════════════════════════════════

    def recheck_updates(self) -> dict:
        """定时任务专用：重新查询 file_index 中的现行标准，检测是否有更新/废止。"""
        rows = self._file_index.get_recheck_candidates(limit=500)
        if not rows:
            return {"checked": 0, "updated": 0}
        updated = 0
        checked = 0
        for row in rows:
            lc = row.get("logical_code", "")
            num = row.get("number", 0)
            yr = row.get("year", 0)
            if not lc or not num:
                continue
            r = self._query_engine.query_parsed(lc, num, yr,
                num_prefix=row.get("num_prefix", ""))
            checked += 1
            if r and r.is_found() and r.status != row.get("status"):
                self._file_index.upsert(row["file_path"],
                    logical_code=lc, number=num, year=yr,
                    std_name=r.standard_name, status=r.status)
                updated += 1
        return {"checked": checked, "updated": updated}

    # ════════════════════════════════════════════════════════════════
    # 批量查询/下载
    # ════════════════════════════════════════════════════════════════

    def query_by_numbers(self, numbers: List[str], force_refresh: bool = False,
                          preferred_site: str = "") -> tuple:
        """直接按标准号字符串列表查询（跳过扫描步骤）。"""
        from ..core.std_utils import parse_std_number
        parsed = []
        for n in numbers:
            p = parse_std_number(n)
            if p:
                parsed.append((n, p))
        items = [(p["code"], p["number"], p.get("year", 0),
                  p.get("num_prefix", ""), p.get("part"), n) for n, p in parsed]
        results = self._query_engine.query_batch_parsed(
            items, preferred_site=preferred_site)
        # 构建兼容的 stats（旧调用方期望 tuple）
        total = len(results)
        found = sum(1 for r in results if r.is_found())
        from ..query.models import BatchQueryStats
        stats = BatchQueryStats(total=total, found=found)
        return results, stats

    def download_by_numbers(self, numbers: List[str]) -> tuple:
        """按标准号列表下载。先查询获取采标状态，采标标准给提示并跳过。"""
        from ..core.std_utils import parse_std_number
        parsed = []
        for n in numbers:
            p = parse_std_number(n)
            if p:
                parsed.append((n, p))
        items = [(p["code"], p["number"], p.get("year", 0),
                  p.get("num_prefix", ""), p.get("part"), n) for n, p in parsed]
        query_results = self._query_engine.query_batch_parsed(items)
        tasks = []
        adopted_skipped = []
        for n, r in zip(numbers, query_results):
            if r and getattr(r, 'is_adopted', False):
                adopted_skipped.append(n)
                logger.info("采标标准，跳过下载: %s", n)
            else:
                tasks.append(DownloadTask(standard_number=n, query_result=r,
                                           source_site=getattr(r, 'source_site', '')))

        if adopted_skipped:
            logger.warning("共 %d 条采标标准跳过下载: %s",
                           len(adopted_skipped), ", ".join(adopted_skipped[:10]))

        if not tasks:
            return [], type('obj', (object,), {
                'total': len(numbers), 'success': 0, 'failed': 0,
                'skipped_adopted': len(adopted_skipped),
                'skipped_exists': 0, 'errors': 0})()

        return self._download_engine.download_batch(tasks)
