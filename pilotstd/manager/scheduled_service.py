# pilotstd/manager/scheduled_service.py
# ScheduledService — 定时任务专用方法：扫描入库、更新检测、批量查询/下载

import logging
import os
from typing import Any, Dict, List

from ..core.config import get_library_root
from ..core.file_utils import ensure_dot_ext, hash_file_content
from ..download.models import DownloadTask

logger = logging.getLogger(__name__)

# Q6-1: 扫描排除规则
_EXCLUDED_DIRS = {"_unparseable"}
_EXCLUDED_PREFIXES = (".",)
_EXCLUDED_SUFFIXES = (".tmp", ".partial")


class ScheduledService:
    """定时任务服务：提供扫描入库、版本更新检测、按号查询/下载等批量操作。

    这些方法供定时任务（scheduler）调用，不依赖 UI 交互，直接操作底层引擎。
    """

    def __init__(
        self,
        cfg: Any,
        scanner: Any,
        parser: Any,
        query_engine: Any,
        file_index: Any,
        quota_tracker: Any,
        download_engine: Any,
    ):
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

    def scan_and_index(self) -> Dict[str, int]:
        """Q6-1: 扫描标准库根目录，四要素精确匹配后 UPDATE standards 表。
        仅对 scan_status='pending' 的记录执行 UPDATE，绝不 INSERT 新记录。
        未匹配文件保持 pending 状态，由人工或后续流程处置。
        """
        result: Dict[str, int] = {"indexed": 0, "skipped": 0, "failed": 0}
        scan_root = get_library_root(self._cfg)

        if not os.path.isdir(scan_root):
            logger.error("scan_and_index: 根目录不存在 %s", scan_root)
            result["failed"] += 1
            return result

        for dirpath, dirnames, filenames in os.walk(scan_root):
            # 原地修改 dirnames 阻止递归进入排除目录
            dirnames[:] = [d for d in dirnames if d not in _EXCLUDED_DIRS and not d.startswith(".")]

            for filename in filenames:
                if filename.startswith(_EXCLUDED_PREFIXES) or filename.endswith(_EXCLUDED_SUFFIXES):
                    continue

                file_path = os.path.join(dirpath, filename)

                try:
                    # 3a. 计算哈希 + 获取文件大小
                    file_hash = hash_file_content(file_path)
                    file_size = os.path.getsize(file_path)

                    # 3b. 解析 code + name（仅传文件名，与解析器约定一致）
                    parsed = self._parser.parse(os.path.basename(file_path))
                    if parsed is None:
                        logger.warning("文件名解析失败，跳过: %s", file_path)
                        result["skipped"] += 1
                        continue

                    # 终点防御：确保 ext 带点号
                    parsed.ext = ensure_dot_ext(parsed.ext)

                    # 3c. 四要素精确查询
                    row = self._file_index.db.execute(
                        "SELECT id FROM standards WHERE sha256=? AND code=? AND name=? AND size=?",
                        (file_hash, parsed.logical_code, parsed.std_name or "", file_size),
                    ).fetchone()  # type: ignore[union-attr]

                    if row is None:
                        logger.debug("四要素未匹配，保持 pending: %s", file_path)
                        result["skipped"] += 1
                        continue

                    # 3d. 条件更新（仅 scan_status='pending'）
                    cursor = self._file_index.db.execute(
                        """UPDATE standards
                           SET scan_status='indexed',
                               local_path=?,
                               updated_at=CURRENT_TIMESTAMP
                           WHERE id=? AND scan_status='pending'""",
                        (file_path, row[0]),
                    )  # type: ignore[union-attr]

                    if cursor.rowcount == 1:
                        result["indexed"] += 1
                    else:
                        logger.debug("已索引或状态非 pending，跳过: %s", file_path)
                        result["skipped"] += 1

                except Exception as e:
                    logger.error("scan_and_index 单文件异常: %s, error=%s", file_path, e)
                    result["failed"] += 1
                    continue

        logger.info(
            "scan_and_index 完成: indexed=%d, skipped=%d, failed=%d",
            result["indexed"],
            result["skipped"],
            result["failed"],
        )
        return result

    # ════════════════════════════════════════════════════════════════
    # 批量查询/下载
    # ════════════════════════════════════════════════════════════════

    def query_by_numbers(
        self, numbers: List[str], force_refresh: bool = False, preferred_site: str | None = None
    ) -> tuple[Any, Any]:
        """直接按标准号字符串列表查询（跳过扫描步骤）。"""
        from ..core.std_utils import parse_std_number

        parsed = []
        for n in numbers:
            p = parse_std_number(n)
            if p:
                parsed.append((n, p))
        items = [
            (
                p["code"],
                p["number"],
                p.get("year", 0),
                p.get("num_prefix", ""),
                p.get("part"),
                n,
            )
            for n, p in parsed
        ]
        results = self._query_engine.query_standards(items, use_parallel=True, preferred_site=preferred_site)
        # 构建兼容的 stats（旧调用方期望 tuple）
        total = len(results)
        found = sum(1 for r in results if r.is_found())
        from ..query.models import BatchQueryStats

        stats = BatchQueryStats(total=total, found=found)
        return results, stats

    def download_by_numbers(self, numbers: List[str]) -> tuple[Any, Any]:
        """按标准号列表下载。先查询获取采标状态，采标标准给提示并跳过。"""
        from ..core.std_utils import parse_std_number

        parsed = []
        for n in numbers:
            p = parse_std_number(n)
            if p:
                parsed.append((n, p))
        items = [
            (
                p["code"],
                p["number"],
                p.get("year", 0),
                p.get("num_prefix", ""),
                p.get("part"),
                n,
            )
            for n, p in parsed
        ]
        query_results = self._query_engine.query_standards(items, use_parallel=True)
        tasks = []
        adopted_skipped = []
        for n, r in zip(numbers, query_results):
            if r and getattr(r, "is_adopted", False):
                adopted_skipped.append(n)
                logger.info("采标标准，跳过下载: %s", n)
            else:
                tasks.append(
                    DownloadTask(
                        standard_number=n,
                        query_result=r,
                        source_site=getattr(r, "source_site", ""),
                    )
                )

        if adopted_skipped:
            logger.warning(
                "共 %d 条采标标准跳过下载: %s",
                len(adopted_skipped),
                ", ".join(adopted_skipped[:10]),
            )

        if not tasks:
            return [], type(
                "obj",
                (object,),
                {
                    "total": len(numbers),
                    "success": 0,
                    "failed": 0,
                    "skipped_adopted": len(adopted_skipped),
                    "skipped_exists": 0,
                    "errors": 0,
                },
            )()

        return self._download_engine.download_batch(tasks)  # type: ignore[no-any-return]  # 子引擎返回值类型委托
