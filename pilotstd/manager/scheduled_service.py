# 模块：项目/管理器/_服务脚本
# 定时任务专用方法：扫描入库、更新检测、批量查询/下载

import logging
import os
from typing import Any, Dict, List

from ..core.config import get_library_root
from ..core.file_utils import ensure_dot_ext, hash_file_content
from ..download.models import DownloadTask

logger = logging.getLogger(__name__)

# 6-1:扫描排除规则
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

    # ════════════════════════════════════════════════════════════════ 分隔
    # 扫描入库
    # ════════════════════════════════════════════════════════════════ 分隔

    def scan_and_index(self) -> Dict[str, int]:
        """Q6-1: 扫描标准库根目录，四要素精确匹配后 UPDATE standards 表。
        仅对 scan_status='pending' 的记录执行 UPDATE，绝不 INSERT 新记录。
        未匹配文件保持 pending 状态，由人工或后续流程处置。

        ── 为什么要把 skipped 拆成多类（G-27，2026-11-23）──
        生产实测 `indexed=0 / skipped=825 / failed=0`，但原实现把三种**完全不同**的
        跳过原因都记进同一个 `skipped`：
          ① 文件名解析失败（`parse()` 返回 None）
          ② 四要素（sha256/code/name/size）查询无命中
          ③ 命中但 `scan_status != 'pending'`（已索引过）
        汇总日志只有 `skipped=825`，无法判断是哪一类 —— 排查只能靠猜。

        现在每类单独计数并在汇总日志里打出，同时给出**第一条**未匹配样本的
        四要素值（脱敏后只留 code/name/size），下次生产复跑即可直接定位断在哪一环。
        """
        result: Dict[str, int] = {
            "indexed": 0,
            "skipped": 0,
            "failed": 0,
            # 细分（合计 == skipped）——供生产排查定位
            "skip_parse_failed": 0,
            "skip_no_match": 0,
            "skip_not_pending": 0,
        }
        scan_root = get_library_root(self._cfg)
        # 记录第一条未匹配样本的四要素，用于定位「断在哪一环」
        first_miss: Dict[str, Any] | None = None

        if not os.path.isdir(scan_root):
            logger.error("scan_and_index: 根目录不存在 %s", scan_root)
            result["failed"] += 1
            return result

        for dirpath, dirnames, filenames in os.walk(scan_root):
            # 原地修改阻止递归进入排除目录
            dirnames[:] = [d for d in dirnames if d not in _EXCLUDED_DIRS and not d.startswith(".")]

            for filename in filenames:
                if filename.startswith(_EXCLUDED_PREFIXES) or filename.endswith(_EXCLUDED_SUFFIXES):
                    continue
                file_path = os.path.join(dirpath, filename)
                miss = self._index_one_file(file_path, result)
                if miss is not None and first_miss is None:
                    first_miss = miss

        self._log_scan_summary(result, first_miss)
        return result

    def _index_one_file(self, file_path: str, result: Dict[str, int]) -> Dict[str, Any] | None:
        """处理单个文件：解析 → 四要素匹配 → 条件更新，就地累加 `result` 计数。

        返回「首条未匹配样本」的四要素摘要（供调用方记录），其余情况返回 None。
        G-27：三类跳过原因分别累加 `skip_parse_failed` / `skip_no_match` / `skip_not_pending`。
        """
        try:
            # 计算哈希 + 文件大小
            file_hash = hash_file_content(file_path)
            file_size = os.path.getsize(file_path)

            # 解析（仅传文件名，与解析器约定一致）
            parsed = self._parser.parse(os.path.basename(file_path))
            if parsed is None:
                logger.warning("文件名解析失败，跳过: %s", file_path)
                result["skipped"] += 1
                result["skip_parse_failed"] += 1
                return None

            # 终点防御：确保带点号
            parsed.ext = ensure_dot_ext(parsed.ext)

            # 四要素精确查询
            row = self._file_index.db.execute(
                "SELECT id FROM standards WHERE sha256=? AND code=? AND name=? AND size=?",
                (file_hash, parsed.logical_code, parsed.std_name or "", file_size),
            ).fetchone()  # type: ignore[union-attr]

            if row is None:
                logger.debug("四要素未匹配，保持 pending: %s", file_path)
                result["skipped"] += 1
                result["skip_no_match"] += 1
                return {
                    "file": file_path,
                    "sha256": file_hash[:16],
                    "code": parsed.logical_code,
                    "name": parsed.std_name or "",
                    "size": file_size,
                }

            # 条件更新（仅 scan_status='pending'）
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
                result["skip_not_pending"] += 1
        except Exception as e:
            logger.error("scan_and_index 单文件异常: %s, error=%s", file_path, e)
            result["failed"] += 1
        return None

    @staticmethod
    def _log_scan_summary(result: Dict[str, int], first_miss: Dict[str, Any] | None) -> None:
        """输出 scan_and_index 汇总日志（含三类跳过细分 + 首条未匹配样本）。"""
        logger.info(
            "scan_and_index done: indexed=%d, skipped=%d(parse_failed=%d/no_match=%d/not_pending=%d), failed=%d",
            result["indexed"],
            result["skipped"],
            result["skip_parse_failed"],
            result["skip_no_match"],
            result["skip_not_pending"],
            result["failed"],
        )
        if first_miss is not None:
            # 只打第一条样本，避免刷屏；四要素值用于与 standards 表比对定位断点
            logger.warning(
                "scan_and_index 首条未匹配样本: code=%r name=%r size=%s sha256=%s... file=%s",
                first_miss["code"],
                first_miss["name"],
                first_miss["size"],
                first_miss["sha256"],
                first_miss["file"],
            )  # i18n-allow: 内部运维日志

    # ════════════════════════════════════════════════════════════════ 分隔
    # 批量查询/下载
    # ════════════════════════════════════════════════════════════════ 分隔

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
        results = self._query_engine.query_standards(
            items, use_parallel=True, force_refresh=force_refresh, preferred_site=preferred_site
        )
        # 统计口径统一由 BatchQueryStats.from_results 负责（勿再只填 total/found：
        # /api/query 会透出 downloadable/not_found，漏填即恒为 0，与逐条字段矛盾）。
        from ..query.models import BatchQueryStats

        return results, BatchQueryStats.from_results(results)

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
