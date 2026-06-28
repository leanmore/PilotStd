# pilotstd/manager.py
# StandardManager — 业务逻辑门面，统一 API 封装扫描→查询→下载→归类完整流程

from __future__ import annotations

import json
import logging
import os
import warnings
from typing import Any, Callable, List, Optional

import requests

from ..core.config import ConfigManager, get_db_path, get_library_root
from ..core.db import Database
from ..core.file_index import FileIndexRepository
from ..core.notification import EVENT_ARCHIVE_COMPLETE, NotificationManager  # v17 通知模块
from ..core.std_utils import GB_CODES, classify_std_code
from ..core.validity_checker import ValidityChecker  # v16 标准时效性检查
from ..download.adapters.base import BaseDownloadAdapter
from ..download.adapters.openstd_download import OpenstdDownloadAdapter
from ..download.engine import DownloadEngine
from ..download.models import BatchDownloadStats, DownloadTask
from ..download.session import SessionManager
from ..models import ParsedStdInfo
from ..organizer.industry_lookup import build_code_mapping
from ..query.adapters.base import BaseAdapter
from ..query.adapters.csres import CsresAdapter
from ..query.adapters.dbba import DbbaAdapter
from ..query.adapters.hbba import HbbaAdapter
from ..query.adapters.iso_gov import IsoGovAdapter
from ..query.adapters.njbz365 import Njbz365Adapter
from ..query.adapters.std_gov import StdGovAdapter
from ..query.cache import CacheRepository
from ..query.daily_quota import DailyQuotaTracker
from ..query.engine import QueryEngine
from ..query.models import BatchQueryStats, QueryResult
from ..query.rotator import SiteRotator
from ..scan.parser import StandardParser
from ..scan.scanner import FileScanner
from ..task.queue import TaskQueue
from .organizer_service import OrganizerService

logger = logging.getLogger(__name__)


class StandardManager:
    """标准管理统一 API — 业务逻辑门面。

    封装扫描→查询→下载→归类的完整流水线，
    同时管理所有子系统（配置、数据库、适配器、缓存、任务队列）的生命周期。
    """

    def __init__(
        self,
        config: Optional[ConfigManager] = None,
        db: Optional[Database] = None,
        query_adapters: Optional[List[BaseAdapter]] = None,
        download_adapters: Optional[List[BaseDownloadAdapter]] = None,
    ) -> None:
        # ── 配置 & 数据库 ──
        self.cfg = config or ConfigManager()
        self.db = db or Database(get_db_path())

        # ── 扫描子系统 ──
        code_mapping = build_code_mapping()  # 加载76类行业标准代号映射表
        self.parser = StandardParser(code_mapping)
        self.scanner = FileScanner(self.cfg)

        # ── 查询子系统 ──
        # 默认注册7个查询适配器：安徽标准平台(ahbz)/南京标准网/全国标准平台/行标平台/ISO平台/地方标准平台/工标网
        from ..query.adapters.ahbz import AhbzAdapter

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
        # 站点轮转器：控制请求频率，防止被网站封 IP
        from ..query.site_config import create_default_sites

        sites = create_default_sites()
        rotator = SiteRotator(sites, db=self.db)
        csres.set_rotator(rotator)
        # 每日配额跟踪——日上限从 site_config 统一读取
        daily_limits = {s.name: s.daily_limit for s in sites if s.daily_limit > 0}
        self.quota_tracker = DailyQuotaTracker(self.db, limits=daily_limits)
        self.cache = CacheRepository(self.db)  # 查询结果缓存
        self.file_index = FileIndexRepository(self.db)  # 本地文件索引
        # 查询间隔配置（含抖动）
        qi_cfg = self.cfg.get("query.query_interval", None)
        query_interval = tuple(qi_cfg) if qi_cfg and len(qi_cfg) == 2 else None
        self.query_engine = QueryEngine(
            adapters,
            self.cache,
            use_cache=self.cfg.get("query.use_cache", True),
            rotator=rotator,
            quota_tracker=self.quota_tracker,
            query_interval=query_interval,
            parser=self.parser,
        )

        # ── 下载子系统 ──
        self.session_mgr = SessionManager(default_timeout=self.cfg.get("network.timeout", 30))
        dl_adapter = download_adapters or [OpenstdDownloadAdapter(self.session_mgr.create_session())]
        save_root = get_library_root(self.cfg)
        self.download_engine = DownloadEngine(dl_adapter, self.session_mgr, save_root=save_root)

        # ── 任务队列 ──
        self.task_queue = TaskQueue(self.db)

        # ── 流水线路由调度器 ──
        from ..pipeline.router import PipelineRouter

        self.router = PipelineRouter()

        # ── 增量文件监控（watchdog，可选） ──
        self._file_watcher = None
        self._last_skipped_dirs: list[Any] = []  # 扫描跳过的目录列表

        # ── 子服务（拆分自本类，保持向后兼容） ──
        from .service_factory import create_services

        (
            self._classifier,
            self._organizer_svc,
            self._announce_svc,
            self._pending_svc,
            self._scheduled_svc,
        ) = create_services(self)

        # ── 时效性检查 ──
        self.validity_checker = ValidityChecker(self.db)

        # ── 通知模块 ──
        self.notification_mgr = NotificationManager(self.cfg, self.db)

        # ── 工作状态 ──
        self._parsed_results: List[ParsedStdInfo] = []  # 扫描结果缓存
        self._queried_items: List[ParsedStdInfo] = []  # 查询时实际传入的列表（与 _query_results 平行）
        self._query_results: List[QueryResult] = []  # 查询结果缓存
        self._download_list: List[ParsedStdInfo] = []  # 需下载列表（由 classify_after_query 填充）
        self._expire_list: List[ParsedStdInfo] = []  # 需过期处理列表
        self._pending_list: List[ParsedStdInfo] = []  # 需人工确认列表
        self._download_tasks: List[DownloadTask] = []  # 下载任务缓存

    def _init_notification(self) -> None:
        """重新初始化通知模块（配置变更后调用）。"""
        self.notification_mgr = NotificationManager(self.cfg, self.db)

    # ════════════════════════════════════════════════════════════════
    # 扫描
    # ════════════════════════════════════════════════════════════════

    def scan_directory(self, root_path: str) -> List[ParsedStdInfo]:
        """扫描目录，识别文件名中的标准号。

        流程：
          1. FileScanner 遍历目录收集所有文件
          2. StandardParser 从文件名中解析标准号、代号、年份等
          3. 解析成功的信息存入 _parsed_results
        """
        result = self.scanner.scan([root_path])
        self._last_skipped_dirs = result.skipped_dirs
        # 每次扫描前清空内容哈希缓存，避免同目录二次扫描被去重跳过
        self.scanner._seen_hashes.clear()
        parsed = []
        seen_std_numbers = set()  # 按标准号去重：同标准号多文件只保留第一条
        dup_count = 0
        for f in result.files:
            info = self.parser.parse(f.filename)
            if info:
                # 用 (代号, 序号, 年份, 部分号) 作为去重键
                key = (info.logical_code, info.number, info.year, info.part)
                if key not in seen_std_numbers:
                    seen_std_numbers.add(key)
                    info.source_path = f.full_path  # 记录源文件路径，供 organize 使用
                    parsed.append(info)
                else:
                    dup_count += 1

        if dup_count > 0:
            logger.info("扫描去重: %d 条重复标准号已合并", dup_count)
        # 补充文件扩展名统计（供下游阶段使用）
        ext_count = {"pdf": 0, "doc": 0, "docx": 0, "other": 0}
        for p in result.files:
            src = getattr(p, "full_path", "")
            ext = os.path.splitext(src)[1].lower().lstrip(".")
            ext_count[ext if ext in ext_count else "other"] += 1
        result.ext_stats = ext_count  # type: ignore[attr-defined]

        self._parsed_results = parsed
        logger.info(f"扫描完成: {len(parsed)}/{len(result.files)} 识别成功")

        # 文件扫描完成后标记缓存失效
        try:
            from pilotstd.core.cache_manager import CacheManager, DataSource

            CacheManager(self.db).invalidate_by_source(DataSource.FILE_INDEX)
        except Exception:
            pass

        return parsed

    def scan_directory_stream(
        self,
        root_path: str,
        on_progress: Any = None,
        on_batch: Any = None,
    ) -> list[ParsedStdInfo]:
        """流式扫描目录（线程安全）。通过回调通知进度，供 Worker 线程调用。
        回调签名: on_progress(current, total)  on_batch([(seq, ParsedStdInfo), ...])
        """
        result = self.scanner.scan([root_path])
        self._last_skipped_dirs = result.skipped_dirs  # 供 auto_run_stream 使用
        parsed = []
        seen_std_numbers = set()
        dup_count = 0
        total = len(result.files)
        batch = []
        for i, f in enumerate(result.files):
            info = self.parser.parse(f.filename)
            if info:
                key = (info.logical_code, info.number, info.year, info.part)
                if key not in seen_std_numbers:
                    seen_std_numbers.add(key)
                    info.source_path = f.full_path
                    parsed.append(info)
                    batch.append((i + 1, info))
                else:
                    dup_count += 1
            if on_batch and len(batch) >= 20:
                on_batch(batch)
                batch = []
            if on_progress:
                on_progress(i + 1, total)
        if on_batch and batch:
            on_batch(batch)
        if dup_count > 0:
            logger.info("扫描去重: %d 条重复标准号已合并", dup_count)
        ext_count = {"pdf": 0, "doc": 0, "docx": 0, "other": 0}
        for p in result.files:
            src = getattr(p, "full_path", "")
            ext = os.path.splitext(src)[1].lower().lstrip(".")
            ext_count[ext if ext in ext_count else "other"] += 1
        result.ext_stats = ext_count  # type: ignore[attr-defined]
        self._parsed_results = parsed
        logger.info(f"扫描完成: {len(parsed)}/{total} 识别成功")

        try:
            from pilotstd.core.cache_manager import CacheManager, DataSource

            CacheManager(self.db).invalidate_by_source(DataSource.FILE_INDEX)
        except Exception:
            pass

        return parsed

    # ════════════════════════════════════════════════════════════════
    # 查询
    # ════════════════════════════════════════════════════════════════

    def _query_announcement_match(self, standard_number: str) -> dict[str, Any] | None:
        """向 Web 端公告缓存服务查询单个标准号。
        返回 dict={"data":..., "cached_at":...} 或 None（未命中/不可达）。
        """
        base_url = self.cfg.get("query.announcement_url", "http://localhost:9028")
        timeout = self.cfg.get("network.timeout", 30)
        api_key = self.cfg.get("query.announcement_api_key", "")
        # 无有效 API Key 时跳过请求，避免无意义的 401 日志
        if not api_key or not api_key.strip():
            return None
        url = f"{base_url.rstrip('/')}/api/announce/lookup"
        headers = {"Authorization": f"Bearer {api_key}"}
        try:
            resp = requests.get(
                url,
                params={"number": standard_number},
                timeout=timeout,
                headers=headers,
            )
            resp.raise_for_status()
            body = resp.json()
        except requests.exceptions.Timeout:
            logger.info(
                "公告缓存查询：%s → 连接超时（%ss），降级到实时网络查询",
                standard_number,
                timeout,
            )
            return None
        except requests.exceptions.ConnectionError as e:
            logger.info(
                "公告缓存查询：%s → 连接失败（%s），降级到实时网络查询",
                standard_number,
                e,
            )
            return None
        except (requests.exceptions.RequestException, ValueError) as e:
            logger.info(
                "公告缓存查询：%s → 请求异常（%s），降级到实时网络查询",
                standard_number,
                e,
            )
            return None

        if body.get("found"):
            logger.info(
                "公告缓存查询：%s → 命中（cached_at=%s）",
                standard_number,
                body.get("cached_at", ""),
            )
            return {"data": body["data"], "cached_at": body.get("cached_at", "")}

        logger.info("公告缓存查询：%s → 未命中，降级到实时网络查询", standard_number)
        return None

    @staticmethod
    def _build_result_from_cache(standard_number: str, cache_data: dict[str, Any]) -> QueryResult:
        """从 Web 公告缓存数据构建 QueryResult。"""
        data = cache_data or {}
        return QueryResult(
            standard_number=standard_number,
            standard_name=data.get("standard_name", data.get("std_name", "")),
            status=data.get("status", data.get("effect_status", "")),
            replaces=data.get("replaces", data.get("replaces_code", "")),
            implementation_date=data.get("implementation_date", ""),
            responsible_dept=data.get("responsible_dept", ""),
            is_adopted=data.get("is_adopted", False),
            match_status=data.get("match_status", "exact"),
            source_site="web_announcement_match",
            source="web端公告缓存",
            publish_date=data.get("publish_date", ""),
            abolition_date=data.get("abolition_date", ""),
            hcno=data.get("hcno", ""),
            is_downloadable=data.get("is_downloadable", True),
        )

    def query(
        self,
        parsed_list: list[ParsedStdInfo] | None = None,
        force_refresh: bool = False,
        progress_callback: Callable[[int, int], None] | None = None,
        result_callback: Callable[[int, Any], None] | None = None,
    ) -> tuple[list[QueryResult], BatchQueryStats]:
        """批量查询标准的有效性状态，查询完成后自动分类路由。

        分类结果存入实例属性，供 download() 和 UI 读取：
          - _download_list: 需下载（GB类 + match_status=="newer"）
          - _expire_list:   需过期处理
          - _pending_list:  需人工确认

        Args:
            progress_callback: 每处理一条调用 callback(已处理数, 总数)
        """
        items = parsed_list or self._parsed_results
        self._queried_items = items  # 保存查询列表，供 download() 匹配索引

        # Web 端公告缓存优先模式：先查缓存，未命中再降级到本地适配器
        use_announcement_match = self.cfg.get("query.use_announcement_match", False)

        if use_announcement_match:
            # ── 分支A：缓存优先 + 自动降级 ──
            cache_hit_map: dict[int, QueryResult] = {}
            miss_indices: list[int] = []
            miss_items: list[ParsedStdInfo] = []

            for i, p in enumerate(items):
                part = getattr(p, "part", None)
                part_str = f".{part}" if part else ""
                std_num = f"{p.logical_code} {p.number}{part_str}-{p.year}"

                cache_hit = self._query_announcement_match(std_num)
                if cache_hit:
                    cache_hit_map[i] = self._build_result_from_cache(std_num, cache_hit["data"])
                    if result_callback:
                        result_callback(i, cache_hit_map[i])
                else:
                    miss_indices.append(i)
                    miss_items.append(p)

            # 合并结果：缓存命中 + 引擎降级查询
            # 用空占位 QueryResult 预填充，后续全部替换为实际结果
            _placeholder = QueryResult(standard_number="")
            results: list[QueryResult] = [_placeholder] * len(items)
            for i, r in cache_hit_map.items():
                results[i] = r

            if miss_items:
                miss_tuples = [
                    (
                        p.logical_code,
                        p.number,
                        p.year,
                        p.std_name or "",
                        getattr(p, "part", None),
                        getattr(p, "num_prefix", ""),
                        getattr(p, "num_suffix", ""),
                        getattr(p, "source_path", ""),
                    )
                    for p in miss_items
                ]

                # 降级回调：将 miss 结果映射回原始索引
                def _fallback_callback(miss_idx: int, r: QueryResult) -> None:
                    r.source = "live_fallback"
                    logger.info(
                        "实时网络查询（降级）：%s → %s",
                        r.standard_number,
                        "找到" if r.is_found() else "未找到",
                    )
                    orig_idx = miss_indices[miss_idx]
                    results[orig_idx] = r
                    if result_callback:
                        result_callback(orig_idx, r)

                engine_results = self.query_engine.query_standards(
                    miss_tuples,  # type: ignore[arg-type]  # 元组额外字段运行时兼容
                    result_callback=_fallback_callback,
                )
                # 兜底：回调未覆盖的用直接结果填充
                for j, r in enumerate(engine_results):
                    orig_idx = miss_indices[j]
                    if results[orig_idx] is _placeholder:
                        r.source = "live_fallback"
                        results[orig_idx] = r

            # None → 占位错误结果
            for i in range(len(results)):
                if results[i] is _placeholder:
                    p = items[i]
                    part_str = f".{getattr(p, 'part', '')}" if getattr(p, "part", None) else ""
                    results[i] = QueryResult(
                        standard_number=f"{p.logical_code} {p.number}{part_str}-{p.year}",
                        error_message="查询未执行",
                    )

        else:
            # ── 分支B：原有本地适配器查询逻辑（不变） ──
            parsed_tuples = [
                (
                    p.logical_code,
                    p.number,
                    p.year,
                    p.std_name or "",
                    p.part,
                    getattr(p, "num_prefix", ""),
                    getattr(p, "num_suffix", ""),
                    getattr(p, "source_path", ""),
                )
                for p in items
            ]

            def _parsed_progress(count: int) -> None:
                if progress_callback:
                    progress_callback(count, len(items))

            # result_callback 透传给引擎，每条查询就绪时立即回调（供 UI 实时更新）
            results = self.query_engine.query_standards(
                parsed_tuples,  # type: ignore[arg-type]  # 元组额外字段运行时兼容
                result_callback=result_callback,
            )
        self._query_results = results

        # 从结果计算统计
        stats = BatchQueryStats()
        stats.total = len(items)
        for r in results:
            if r.is_found():
                stats.found += 1
            if r.is_downloadable:
                stats.downloadable += 1
            if getattr(r, "is_adopted", False):
                stats.adopted_restricted += 1
            if getattr(r, "match_status", "") == "exact":
                stats.exact += 1

        # 查询后分类
        self._classify_after_query(items, results)

        # 持久化待确认条目（CLI/auto_run/UI 统一路径，record_pending 幂等防重）
        if self._pending_list:
            self.record_pending(self._pending_list)

        # 汇总汇报
        self._report_query_summary(stats, items, results)
        return results, stats

    # ── 查询汇报 ──────────────────────────────────────────────

    # classify_std_code() 返回值→中文标签映射
    _CAT_LABEL = {
        "gb": "国标",
        "industry": "行业标准",
        "db": "地方标准",
        "iso_iec": "国际标准",
        "foreign": "国外标准",
        "group": "团体标准",
        "enterprise": "企业标准",
    }

    # 待确认原因 → 人话映射
    _PENDING_REASONS = {
        "older": "站点仅有更旧版本，未找到对应年份",
        "newer": "站点版本比本地文件更新",
        "code_only": "站点仅匹配到代号，标准号/年份不一致",
        "mismatch": "站点返回的标准名称与文件名不匹配",
    }

    def _report_query_summary(
        self,
        stats: BatchQueryStats,
        items: list[ParsedStdInfo],
        results: list[QueryResult],
    ) -> None:
        """输出查询阶段汇总报告。按标准类型分组 + 待确认拆分 + 站点贡献 + 下载说明。"""
        n = len(items)

        # ── 1. 总分 ──
        logger.info(f"查询完成: {stats.found}/{n} 找到 ({stats.found / max(n, 1) * 100:.1f}%)")
        logger.info(f"{stats.exact} 精确匹配")

        # ── 2. 按标准类型分组 ──
        cats = {}  # {label: {"total": N, "found": N, "pending": N}}
        for p, r in zip(items, results):
            cat = self._CAT_LABEL.get(classify_std_code(p.logical_code), "未知")
            if cat not in cats:
                cats[cat] = {"total": 0, "found": 0, "pending": 0}
            cats[cat]["total"] += 1
            if r.is_found():
                cats[cat]["found"] += 1
        # 从已分类列表统计 pending
        pending_set = set(id(p) for p in self._pending_list)
        for p in items:
            cat = self._CAT_LABEL.get(classify_std_code(p.logical_code), "未知")
            if id(p) in pending_set:
                cats[cat]["pending"] += 1

        for cat in ("国标", "行业标准", "地方标准", "国际标准", "国外标准", "未知"):
            c = cats.pop(cat, None)
            if c is None:
                continue
            pct = c["found"] / max(c["total"], 1) * 100
            parts = [f"{cat}: {c['found']}/{c['total']} 找到 ({pct:.1f}%)"]
            if c["pending"]:
                parts.append(f"其中 {c['pending']} 待确认")
            logger.info("  " + ", ".join(parts))
        # 兜底未知
        for cat, c in cats.items():
            pct = c["found"] / max(c["total"], 1) * 100
            logger.info(
                f"  {cat}: {c['found']}/{c['total']} 找到 ({pct:.1f}%)"
                f"{'，其中 ' + str(c['pending']) + ' 待确认' if c['pending'] else ''}"
            )

        # ── 3. 待确认拆分 ──
        pending_by_reason: dict[str, int] = {}
        for r in results:
            ms = getattr(r, "match_status", "") or ""
            if ms == "exact" or not ms:
                continue
            pending_by_reason[ms] = pending_by_reason.get(ms, 0) + 1
        if pending_by_reason:
            logger.info(f"  待确认 {sum(pending_by_reason.values())} 条:")
            for ms, cnt in sorted(pending_by_reason.items(), key=lambda x: -x[1]):
                reason = self._PENDING_REASONS.get(ms, ms)
                logger.info(f"    {ms}: {cnt} 条  ({reason})")

        # ── 4. 站点贡献 ──
        site_count: dict[str, int] = {}
        for r in results:
            site = getattr(r, "source_site", "") or ""
            if site and r.is_found():
                site_count[site] = site_count.get(site, 0) + 1
        if site_count:
            parts = [f"{s}={c}" for s, c in sorted(site_count.items(), key=lambda x: -x[1])]
            logger.info(f"  站点贡献: {'  '.join(parts)}")

        # ── 5. 下载 ──
        dl = len(self._download_list)
        expire = len(self._expire_list)
        pending = len(self._pending_list)

        # 统计不能下载的原因
        adopted_skip = 0  # 采标
        foreign_skip = 0  # 国外/国际标准无下载源
        for p, r in zip(items, results):
            if not r.is_found():
                continue
            if getattr(r, "is_adopted", False):
                adopted_skip += 1
            else:
                cat = classify_std_code(p.logical_code)
                if cat in ("foreign", "iso_iec"):
                    foreign_skip += 1

        reason_parts = []
        if adopted_skip:
            reason_parts.append(f"{adopted_skip} 条因采标无法下载")
        if foreign_skip:
            reason_parts.append(f"{foreign_skip} 条因国外/国际标准无国内下载源")
        reason_str = "；".join(reason_parts) if reason_parts else "无可下载项"
        logger.info(f"  进入下载队列: {dl}, 标记废止: {expire}, 待确认: {pending}  ({reason_str})")

    # ════════════════════════════════════════════════════════════════
    # 查询后分类
    # ════════════════════════════════════════════════════════════════

    _GB_CODES = GB_CODES  # 向后兼容，定义见 pilotstd.core.std_utils
    _EXPIRE_STATUSES = frozenset({"废止", "已废止", "作废", "被代替"})

    @staticmethod
    def _parse_std_number(standard_number: str) -> tuple[str | None, int | None]:
        """从标准号字符串中提取代号和序号。如 'GB/T 713.1-2023' → ('GB/T', 713)。"""
        from .classifier import QueryClassifier

        return QueryClassifier.parse_std_number(standard_number)

    def _classify_after_query(self, parsed_list: list[ParsedStdInfo], query_results: list[QueryResult]) -> None:
        """查询后分类：回写状态 → 跨站补查替代关系 → 委托路由调度器分堆。

        分类规则统一由 PipelineRouter.classify_after_query() 定义。
        此方法负责：
          1. 将查询结果回写到 ParsedStdInfo（effect_status / match_status / found_replaces）
          2. 对废止但无替代信息的 GB 标准跨站补查（_resolve_replaces）
          3. 委托 router.apply_actions() 统一分堆

        分类结果存入: self._download_list / _expire_list / _pending_list
        """
        self._classifier.classify(
            query_results,
            parsed_list,
            self._download_list,
            self._expire_list,
            self._pending_list,
        )

    def _resolve_replaces(self, standard_number: str) -> str:
        """跨站点补查替代关系。当 std_gov 等无 replaces 的站点查到废止标准时，
        尝试用 njbz365 / csres / hbba 的详情页补查替代标准号。"""
        return self._classifier.resolve_replaces(standard_number)  # type: ignore[no-any-return]  # 子服务返回值类型委托

    # ════════════════════════════════════════════════════════════════
    # 下载
    # ════════════════════════════════════════════════════════════════

    def download(self, query_results: list[QueryResult] | None = None) -> tuple[list[DownloadTask], BatchDownloadStats]:
        """下载分类结果中的标准文件。

        不从 query_results 过滤——直接用 query() 阶段分类好的 _download_list。
        download() 只负责执行，不做决策。
        """
        results = query_results or self._query_results

        # 过期处理：废止标准移入 过期作废/
        if self._expire_list:
            self.handle_expired(self._expire_list)

        # 构建下载任务（用 _queried_items 匹配索引，而非 _parsed_results——查询时可能只传了子集）
        tasks = []
        queried = self._queried_items if self._queried_items else self._parsed_results
        for p in self._download_list:
            for i, r in enumerate(results):
                if i < len(queried) and queried[i] is p:
                    t = DownloadTask(
                        standard_number=r.standard_number,
                        query_result=r,
                        source_site=getattr(r, "source_site", ""),
                    )
                    tasks.append(t)
                    break

        completed, stats = self.download_engine.download_batch(tasks, notification_mgr=self.notification_mgr)
        self._download_tasks = completed

        # 回写下载路径：organize() 按 source_path 移动文件，下载入队时需补上
        for task in completed:
            if task.status.value == "success" and task.saved_path:
                for i, p in enumerate(self._download_list):
                    if i < len(tasks) and tasks[i] is task:
                        p.source_path = task.saved_path
                        # 下载成功回写缓存状态：新下载文件状态推导
                        old_status = getattr(p, "effect_status", "") or ""
                        old_match = getattr(p, "match_status", "") or ""
                        if old_status in ("废止", "已废止", "作废", "被代替"):
                            new_effect = "现行"
                        elif old_status == "现行" and old_match == "newer":
                            new_effect = "待实施"
                        else:
                            new_effect = ""
                        if new_effect:
                            # 更新缓存中的状态（QueryResult.status 对应 effect_status）
                            cached = self.cache.get(task.standard_number, getattr(task, "source_site", ""))
                            if cached:
                                cached.status = new_effect
                                self.cache.put(cached)
                        break

        logger.info(
            f"下载完成: 入队 {len(tasks)}, 成功 {stats.success}, "
            f"跳过(已存在) {stats.skipped_exists}, 失败 {stats.failed}"
        )
        return tasks, stats

    def download_stream(
        self, on_progress: Any = None, on_result: Any = None
    ) -> tuple[list[DownloadTask], BatchDownloadStats]:
        """流式下载（线程安全）。回调签名:
        on_progress(current, total)  on_result(idx, status, saved_path_or_None)
        """
        if self._expire_list:
            self.handle_expired(self._expire_list)
        tasks = []
        queried = self._queried_items if self._queried_items else self._parsed_results
        for p in self._download_list:
            for i, r in enumerate(self._query_results):
                if i < len(queried) and queried[i] is p:
                    t = DownloadTask(
                        standard_number=r.standard_number,
                        query_result=r,
                        source_site=getattr(r, "source_site", ""),
                    )
                    tasks.append((i, t, p))
                    break
        completed = []
        stats = BatchDownloadStats()
        total = len(tasks)
        for idx, (orig_idx, task, parsed) in enumerate(tasks):
            result = self.download_engine.download_single(task, skip_adopted=True)
            completed.append(result)
            status = (
                "已下载"
                if result.status.value == "success"
                else "下载失败"
                if result.status.value == "failed"
                else "采标受限"
                if result.status.value == "skipped"
                else result.status.value
            )
            if result.status.value == "success":
                stats.success += 1
                if result.saved_path:
                    parsed.source_path = result.saved_path
            elif result.status.value == "failed":
                stats.failed += 1
            else:
                stats.skipped_exists += 1
            if on_result:
                on_result(orig_idx, status)
            if on_progress:
                on_progress(idx + 1, total)
        self._download_tasks = completed
        return completed, stats

    # ════════════════════════════════════════════════════════════════
    # 归类移动
    # ════════════════════════════════════════════════════════════════

    def organize(
        self,
        parsed_list: list[ParsedStdInfo] | None = None,
        word_source_root: Optional[str] = None,
    ) -> dict[str, Any]:
        """[已废弃] 使用 archive_standards() 替代。
        迁移时间：2026-06-24，阶段一统一归档链路。
        """
        warnings.warn(
            "organize() 已废弃，请使用 archive_standards()",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._organizer_svc.organize(  # type: ignore[no-any-return]
            parsed_list or self._parsed_results, word_source_root
        )

    def _dedup_standard(self, parsed: ParsedStdInfo, new_path: str) -> None:
        """去重：同标准号旧路径残留（分类变化导致双份文件）。"""
        self._organizer_svc._dedup_standard(parsed, new_path)

    def organize_stream(
        self,
        parsed_list: Optional[list[ParsedStdInfo]] = None,
        word_source_root: Optional[str] = None,
        on_progress: Any = None,
        on_result: Any = None,
    ) -> dict[str, Any]:
        """[已废弃] 使用 archive_standards() 替代。
        迁移时间：2026-06-24，阶段一统一归档链路。
        """
        warnings.warn(
            "organize_stream() 已废弃，请使用 archive_standards()",
            DeprecationWarning,
            stacklevel=2,
        )
        items = parsed_list or self._parsed_results
        total = len(items)
        result = {
            "moved": 0,
            "failed": 0,
            "skipped_exists": 0,
            "word_mirrored": 0,
            "skipped_source": 0,
            "dedup_skipped": 0,
            "details": [],
        }
        for i, p in enumerate(items):
            try:
                single = self._organizer_svc.organize([p], word_source_root)
                status = (
                    "已归档"
                    if single.get("moved", 0) > 0
                    else ("跳过" if single.get("skipped_exists", 0) > 0 else "归档失败")
                )
                result["moved"] += single.get("moved", 0)
                result["skipped_exists"] += single.get("skipped_exists", 0)
                result["failed"] += single.get("failed", 0)
                if on_result:
                    on_result(i, status)
            except Exception:
                if on_result:
                    on_result(i, "归档失败")
                result["failed"] += 1  # type: ignore[operator]
            if on_progress:
                on_progress(i + 1, total)
        return result

    # ════════════════════════════════════════════════════════════════
    # 统一归档入口（阶段一新增）
    # ════════════════════════════════════════════════════════════════

    def _backfill_std_name(self, parsed: ParsedStdInfo) -> ParsedStdInfo:
        """回填单个 ParsedStdInfo 的 std_name。
        1. 已有 std_name → 直接返回
        2. 查 standard_info_cache → 命中则回填
        3. 缓存未命中 → 实时查询（QueryEngine）
        4. 查询失败 → 保持空，不阻塞
        """
        if parsed.std_name:
            return parsed
        # 构建标准号字符串用于缓存查询
        _std_no = f"{parsed.logical_code} {parsed.number}"
        if parsed.year:
            _std_no += f"-{parsed.year}"
        # 从 standard_info_cache 查询（不限 source_site）
        try:
            _row = self.db.fetchone(
                "SELECT result_json FROM standard_info_cache WHERE standard_number = ? LIMIT 1",
                (_std_no,),
            )
            if _row:
                try:
                    _raw = _row["result_json"]
                    _data = json.loads(_raw) if isinstance(_raw, str) else _raw
                    _name = _data.get("standard_name", "") if isinstance(_data, dict) else ""
                    if _name:
                        parsed.std_name = _name
                        logger.info("[CACHE] std_name 命中: %s -> %s", _std_no, _name)
                        return parsed
                except (json.JSONDecodeError, TypeError):
                    pass
        except Exception:
            pass
        # 缓存未命中 → 实时查询（不阻塞，查询失败静默跳过）
        logger.info("[CACHE] std_name 未命中: %s，尝试实时查询", _std_no)
        try:
            _results = self.query_engine.query_standards(
                [
                    (
                        parsed.logical_code,
                        parsed.number,
                        parsed.year,
                        parsed.std_name,
                        getattr(parsed, "part", None),
                        getattr(parsed, "num_prefix", ""),
                    )
                ]
            )
            _result = _results[0] if _results else None
            if _result and _result.standard_name:
                parsed.std_name = _result.standard_name
                logger.info("[CACHE] 实时查询成功: %s -> %s，已写入缓存", _std_no, _result.standard_name)
            else:
                logger.info("[CACHE] 实时查询失败: %s", _std_no)
        except Exception:
            logger.info("[CACHE] 实时查询异常: %s", _std_no)
            pass
        return parsed

    def archive_standards(
        self,
        parsed_list: list[ParsedStdInfo] | None = None,
        word_source_root: str | None = None,
        progress_callback: Any = None,
        on_result: Any = None,
    ) -> dict[str, Any]:
        """统一归档入口：所有端（CLI/Web/WinUI）均通过此方法归档。

        内部流程：
        1. 对 std_name 为空的条目执行 _backfill_std_name() 回填
        2. 调用 OrganizerService.organize() 执行实际归档
        3. 返回归档结果字典
        """
        _items = parsed_list if parsed_list is not None else self._parsed_results
        _total = len(_items)
        _backfilled = 0
        for _i, _p in enumerate(_items):
            _orig = _p.std_name
            self._backfill_std_name(_p)
            if not _orig and _p.std_name:
                _backfilled += 1
            if progress_callback:
                progress_callback(_i + 1, _total)
        if _backfilled:
            logger.info("archive_standards: 回填 std_name %d/%d 条", _backfilled, _total)
        result = self._organizer_svc.organize(_items, word_source_root)
        # 归档成功后注册新标准到时效性检查表 + 发送通知
        if result.get("moved", 0) > 0:
            for _p in _items:
                _std_no = f"{_p.logical_code} {_p.number}"
                if _p.year:
                    _std_no += f"-{_p.year}"
                try:
                    self.validity_checker.register_new_standard(_std_no, self.notification_mgr)
                except Exception:
                    pass
            try:
                self.notification_mgr.send_event(EVENT_ARCHIVE_COMPLETE, {"count": result["moved"]})
            except Exception:
                pass
        return result

    # ════════════════════════════════════════════════════════════════
    # GUI 桥接方法（替代 mixin 直接访问子组件）
    # ════════════════════════════════════════════════════════════════

    def get_quota_info(self) -> dict[str, int]:
        """各站点剩余配额，供 GUI 查询前展示。"""
        return self.query_engine.get_quota_info()

    def plan_batch(self, total: int) -> list[tuple[str, int]]:
        """查询批次规划，供 GUI 展示预估耗时。"""
        return self.query_engine.plan_batch(total)

    def get_stage_queue(self, stage: str) -> list[ParsedStdInfo]:
        """返回指定阶段的条目列表，供 UI 工作表按阶段切换显示。
        stage: 'download' | 'expire' | 'pending' | 'all'
        'all' 返回全量查询结果。"""
        if stage == "download":
            return list(self._download_list)
        if stage == "expire":
            return list(self._expire_list)
        if stage == "pending":
            return list(self._pending_list)
        return list(self._queried_items) if self._queried_items else list(self._parsed_results)

    def get_stage_summary(self) -> dict[str, int]:
        """返回各阶段条目计数，供查询汇总弹窗展示。"""
        return {
            "download": len(self._download_list),
            "expire": len(self._expire_list),
            "pending": len(self._pending_list),
            "total": len(self._queried_items or self._parsed_results),
        }

    # ── 待确认清单 ─────────────────────────────────────────────

    def record_pending(self, pending_items: list[ParsedStdInfo]) -> None:
        """将待确认项写入 pending_lookup 表（已存在则跳过）。"""
        self._pending_svc.record_pending(pending_items)

    def resolve_pending(self, pending_items: list[dict[str, Any]], resolution: str) -> None:
        """标记待确认项为已处理。resolution: 'discarded' | 'confirmed'"""
        self._pending_svc.resolve_pending(pending_items, resolution)

    def get_pending_items(self) -> list[dict[str, Any]]:
        """获取所有待确认项。"""
        return self._pending_svc.get_pending_items()  # type: ignore[no-any-return]  # 子服务返回值类型委托

    def increment_requery_count(self, standard_number: str) -> int:
        """待确认重试次数 +1。"""
        return self._pending_svc.increment_requery_count(standard_number)  # type: ignore[no-any-return]  # 子服务返回值类型委托

    def is_requery_exhausted(self, standard_number: str) -> bool:
        """重试次数 >= 3 → True。"""
        return self._pending_svc.is_requery_exhausted(standard_number)  # type: ignore[no-any-return]  # 子服务返回值类型委托

    def mark_manual_required(self, standard_number: str) -> None:
        """标记为需要手动查询。"""
        self._pending_svc.mark_manual_required(standard_number)

    def get_requery_count(self, standard_number: str) -> int:
        """返回当前重试次数。"""
        return self._pending_svc.get_requery_count(standard_number)  # type: ignore[no-any-return]  # 子服务返回值类型委托

    # ── 下载等待队列 ───────────────────────────────────────────

    def enqueue_download_wait(self, parsed: ParsedStdInfo) -> None:
        """写入下载等待队列（未到公开期的标准）。"""
        self._pending_svc.enqueue_download_wait(parsed)

    def get_due_downloads(self) -> list[dict[str, Any]]:
        """获取公开期已到的下载等待项。"""
        return self._pending_svc.get_due_downloads()  # type: ignore[no-any-return]  # 子服务返回值类型委托

    def remove_download_queue(self, standard_number: str) -> None:
        """从下载等待队列中移除指定项。"""
        self._pending_svc.remove_download_queue(standard_number)

    # ── 本地缓存查询 ─────────────────────────────────────────

    def query_local_cache(self, parsed_list: list[ParsedStdInfo]) -> list[ParsedStdInfo]:
        """从本地缓存（standard_info_cache + announcement_match）查询标准信息。
        返回 [(idx, QueryResult), ...]，供 GUI 离线查询模式使用。
        """
        return self._pending_svc.query_local_cache(parsed_list)  # type: ignore[no-any-return]  # 子服务返回值类型委托

    # ── 公告 ─────────────────────────────────────────────────

    def check_announcements(self) -> dict[str, Any]:
        """检查各公告源的新公告，匹配本地标准，返回 {matched: int, error: str}。"""
        return self._announce_svc.check_announcements()  # type: ignore[no-any-return]  # 子服务返回值类型委托

    def get_announcement_match(self, limit: int = 500) -> list[dict[str, Any]]:
        """从 announcement_match 表读取最近公告结果。返回字典列表。"""
        rows = self.db.fetchall(
            "SELECT standard_number, source_site, result_json, cached_at "
            "FROM announcement_match ORDER BY cached_at DESC LIMIT ?",
            (limit,),
        )
        items = []
        for row in rows:
            item = {
                "std_code": row.get("standard_number", ""),
                "source_site": row.get("source_site", "gb"),
            }
            rj = row.get("result_json", "")
            if rj:
                try:
                    import json

                    extra = json.loads(rj) if isinstance(rj, str) else rj
                    if isinstance(extra, dict):
                        item["std_name"] = extra.get("standard_name", "")
                        item["replaces_code"] = extra.get("replaces", "")
                        item["publish_date"] = extra.get("publish_date", "")
                except (json.JSONDecodeError, TypeError):
                    pass
            items.append(item)
        return items

    def check_announcements_filtered(
        self,
        std_type: Optional[str] = None,
        since_date: str = "",
        progress_callback: Any = None,
    ) -> dict[str, Any]:
        """带类型过滤和日期筛选的公告检查。供 CLI cmd_announce 调用。
        返回 {std_type: {matched: int, updated: int, ...}, ...}"""
        return self._announce_svc.check_announcements_filtered(  # type: ignore[no-any-return]
            std_type=std_type,
            since_date=since_date,
            progress_callback=progress_callback,
        )

    def announce_stream(
        self, since_date: str = "", on_progress: Any = None, on_adapter_done: Any = None
    ) -> dict[str, Any]:
        """流式公告检查（线程安全）。逐适配器检查并通过回调通知进度。
        回调签名: on_progress(current, total, matched)  on_adapter_done(std_type, result_dict)
        """
        engine = self._announce_svc._get_or_create_engine()
        ocr = self._announce_svc._get_ocr_provider()
        total = len(engine.adapters)
        results = {}
        matched_total = 0
        for idx, adapter in enumerate(engine.adapters):
            if not since_date:
                log_row = self.file_index._db.fetchone(
                    "SELECT * FROM fetch_checkpoint WHERE source_site=?",
                    (adapter.source_site,),
                )
                since = log_row["last_notice_date"] if log_row else ""
            else:
                since = since_date
            result = engine.check_one(adapter.standard_type, since_date=since, ocr_provider=ocr)
            results[adapter.standard_type] = result
            matched_total += result.get("matched", 0)
            if on_adapter_done:
                on_adapter_done(adapter.standard_type, result)
            if on_progress:
                on_progress(idx + 1, total, matched_total)
        return {"matched": matched_total, "results": results}

    @staticmethod
    def _is_word_or_template(src_path: str) -> bool:
        """通过扩展名判断是否为 Word/模板文件"""
        return OrganizerService._is_word_or_template(src_path)

    def organize_skipped_dirs(self, skipped_dirs: List[str], source_root: Optional[str] = None) -> dict[str, Any]:
        """将扫描时跳过的目录原封不动镜像到新库。

        不扫描、不解析、不改名、不改后缀、不改变目录层次——整体移动。
        目标路径 = <输出根>/<相对源根路径>，保留原始目录结构。
        """
        return self._organizer_svc.organize_skipped_dirs(  # type: ignore[no-any-return]
            skipped_dirs, source_root
        )

    @staticmethod
    def _resolve_industry_in_path(rel_path: str) -> str:
        """解析相对路径第一段中的行业代号为完整目录名。

        源目录的跳过子目录保留了原始行业代号（如 API），
        但主归档已将文件移至完整目录名（如 API 美国石油学会）。
        此方法将跳过目录的目标路径同步到与主归档一致。
        """
        return OrganizerService._resolve_industry_in_path(rel_path)

    # 兜底镜像中需跳过的系统垃圾文件
    _FALLBACK_SKIP_FILES = frozenset({"Thumbs.db", "sync.ffs_db"})
    _FALLBACK_SKIP_PREFIX = "~$"  # Office 临时锁文件

    def organize_fallback(self, source_root: str) -> dict[str, Any]:
        """归档收尾：将源目录中所有残留文件按目录结构镜像到输出目录。

        不解析、不分类、不查询。跳过系统垃圾文件（Thumbs.db、~$* 等）。
        跳过 next_action="pending" 的条目。
        在正常归档和 organize_skipped_dirs 之后调用。
        """
        # 收集待确认条目的源文件路径，兜底镜像时跳过
        pending_paths = frozenset(p.source_path for p in self._pending_list if getattr(p, "source_path", ""))
        # [TRACE] 修复C: _pending_list按match_status汇总
        _ps_by_ms: dict[str, int] = {}
        for p in self._pending_list:
            ms = getattr(p, "match_status", "") or "(empty)"
            _ps_by_ms[ms] = _ps_by_ms.get(ms, 0) + 1
        logger.info(
            "[PENDING_SUMMARY] 总数=%d 按匹配状态=%s",
            len(self._pending_list),
            _ps_by_ms,
        )
        # [TRACE] 指令8: pending路径数量 + 路径归一化采样
        logger.info(
            "[PENDING] 待确认路径总数: %d (采样: %s)",
            len(pending_paths),
            [p[:80] for p in list(pending_paths)[:5]],
        )
        return self._organizer_svc.organize_fallback(  # type: ignore[no-any-return]
            source_root, pending_paths
        )

    # ════════════════════════════════════════════════════════════════
    # 过期处理
    # ════════════════════════════════════════════════════════════════

    def handle_expired(self, parsed_list: Optional[List[ParsedStdInfo]] = None) -> dict[str, Any]:
        """将查询结果为「废止」的标准移入 过期作废 目录。"""
        return self._organizer_svc.handle_expired(parsed_list)  # type: ignore[no-any-return]

    def merge_expire_from_source(self, root_dir: str, parsed_list: list[ParsedStdInfo]) -> int:
        """将源目录中的过期作废文件夹合并到标准库对应目录。返回合并文件数。"""
        return self._organizer_svc.merge_expire_from_source(  # type: ignore[no-any-return]
            root_dir, parsed_list
        )

    # ════════════════════════════════════════════════════════════════
    # 便捷方法
    # ════════════════════════════════════════════════════════════════

    # ════════════════════════════════════════════════════════════════
    # 定时任务专用方法
    # ════════════════════════════════════════════════════════════════

    def scan_and_index(self, root_path: Optional[str] = None) -> int:
        """定时任务专用：扫描目录 → 解析 → 写入 file_index。返回入库文件数。"""
        try:
            count = self._scheduled_svc.scan_and_index(root_path)  # type: ignore[no-any-return]
        except Exception as e:
            logger.exception("scan_and_index 定时任务失败")
            if self.notification_mgr:
                try:
                    self.notification_mgr.send_event(
                        "auto_scan_failed",
                        {
                            "path": root_path or "默认",
                            "error": str(e)[:200],
                        },
                    )
                except Exception:
                    pass
            return 0
        if count == 0 and self.notification_mgr:
            try:
                self.notification_mgr.send_event(
                    "auto_scan_failed",
                    {
                        "path": root_path or "默认",
                        "error": "未扫描到任何文件",
                    },
                )
            except Exception:
                pass
        return count

    def recheck_updates(self) -> dict[str, int]:
        """定时任务专用：重新查询 file_index 中的现行标准，检测是否有更新/废止。"""
        return self._scheduled_svc.recheck_updates()  # type: ignore[no-any-return]

    def query_by_numbers(
        self, numbers: List[str], force_refresh: bool = False, preferred_site: str = ""
    ) -> tuple[list[QueryResult], BatchQueryStats]:
        """直接按标准号字符串列表查询（跳过扫描步骤）。preferred_site 可选强制指定站点。"""
        return self._scheduled_svc.query_by_numbers(  # type: ignore[no-any-return]
            numbers, force_refresh, preferred_site
        )

    def download_by_numbers(self, numbers: List[str]) -> tuple[list[DownloadTask], Any]:
        """按标准号列表下载。先查询获取采标状态，采标标准给提示并跳过。"""
        return self._scheduled_svc.download_by_numbers(numbers)  # type: ignore[no-any-return]

    # ════════════════════════════════════════════════════════════════
    # 一键自动运行
    # ════════════════════════════════════════════════════════════════
    # 增量文件监控
    # ════════════════════════════════════════════════════════════════

    def start_watching(self, root_paths: Optional[list[str]] = None) -> None:
        """启动增量文件监控。可选，需安装 watchdog 包。"""
        try:
            if self._file_watcher is None:
                paths = root_paths or [get_library_root(self.cfg)]
                from ..scan.watcher import (
                    FileWatcher,  # 惰性导入，避免 Docker 环境缺 watchdog
                )

                self._file_watcher = FileWatcher(self.file_index, self.parser, self.cfg)  # type: ignore[assignment]
                self._file_watcher.start(paths)  # type: ignore[attr-defined]
                logger.info("增量文件监控已启动: %s", paths)
        except ImportError:
            logger.warning("watchdog 未安装，跳过增量监控")
        except Exception:
            logger.warning("启动文件监控失败", exc_info=True)

    def stop_watching(self) -> None:
        """停止增量文件监控。"""
        if self._file_watcher:
            self._file_watcher.stop()
            self._file_watcher = None

    # ════════════════════════════════════════════════════════════════

    def auto_run(self, root_path: str) -> dict[str, int]:
        """一键自动运行：扫描 → 查询 → 下载 → 归类。

        Args:
            root_path: 标准文件所在的根目录
        Returns:
            包含各步骤统计数的报告字典
        """
        import time as _time

        report = {
            "scan": 0,
            "query_found": 0,
            "download_success": 0,
            "organize_moved": 0,
        }
        t_stage = _time.monotonic()

        # 1. 扫描
        parsed = self.scan_directory(root_path)
        report["scan"] = len(parsed)
        logger.info("阶段耗时 scan: %.1fs (%d 条)", _time.monotonic() - t_stage, len(parsed))
        t_stage = _time.monotonic()

        # 2. 查询
        _, q_stats = self.query(parsed)
        report["query_found"] = q_stats.found
        logger.info("阶段耗时 query: %.1fs (%d 条)", _time.monotonic() - t_stage, q_stats.found)
        t_stage = _time.monotonic()

        # 3. 下载
        dl_tasks, dl_stats = self.download()
        report["download_success"] = dl_stats.success
        logger.info(
            "阶段耗时 download: %.1fs (%d 成功)",
            _time.monotonic() - t_stage,
            report["download_success"],
        )
        t_stage = _time.monotonic()

        # 4. 归类
        org_result = self.archive_standards(parsed)
        report["organize_moved"] = org_result["moved"]
        report["mirror_skipped"] = 0
        report["fallback_mirrored"] = 0
        logger.info(
            "阶段耗时 archive: %.1fs (%d 已移动)",
            _time.monotonic() - t_stage,
            report["organize_moved"],
        )
        t_stage = _time.monotonic()

        # 5. 归档收容：镜像跳过的目录 + 兜底残留文件
        if self.cfg.get("storage.mirror_skipped_dirs", True):
            skipped = getattr(self, "_last_skipped_dirs", [])
            if skipped:
                mirror_result = self.organize_skipped_dirs(skipped, source_root=root_path)
                report["mirror_skipped"] = mirror_result.get("moved", 0)
        if self.cfg.get("storage.mirror_fallback", True):
            fallback_result = self.organize_fallback(root_path)
            report["fallback_mirrored"] = fallback_result.get("moved", 0)
        logger.info(
            "阶段耗时 收容: %.1fs (镜像跳过%d 兜底%d)",
            _time.monotonic() - t_stage,
            report["mirror_skipped"],
            report["fallback_mirrored"],
        )

        logger.info(f"自动运行完成: {report}")
        return report

    def auto_run_stream(
        self,
        root_path: str,
        on_scan_batch: Any = None,
        on_scan_progress: Any = None,
        on_query_progress: Any = None,
        on_query_result: Any = None,
        on_download_progress: Any = None,
        on_download_result: Any = None,
        on_archive_result: Any = None,
        on_stage_change: Any = None,
    ) -> dict[str, int]:
        """流式自动管线（线程安全）。所有回调在调用线程执行。
        各阶段串行执行: scan → query → download → archive。
        回调签名: on_stage_change(stage_name, current, total)
        """
        import time as _time

        report = {
            "scan": 0,
            "query_found": 0,
            "download_success": 0,
            "organize_moved": 0,
        }
        t_stage = _time.monotonic()
        # Stage 1: 扫描
        if on_stage_change:
            on_stage_change("scan", 0, 0)
        parsed = self.scan_directory_stream(root_path, on_progress=on_scan_progress, on_batch=on_scan_batch)
        report["scan"] = len(parsed)
        logger.info("阶段耗时 scan: %.1fs (%d 条)", _time.monotonic() - t_stage, len(parsed))
        t_stage = _time.monotonic()
        if not parsed:
            if on_stage_change:
                on_stage_change("done", 0, 0)
            return report
        # Stage 2: 查询
        if on_stage_change:
            on_stage_change("query", 0, len(parsed))
        # 包装进度回调：主流程占 90%，剩余 10% 留给 CSRES/溢出等内部处理
        _wrapped_query_progress = None
        if on_query_progress:
            _q_total = len(parsed)

            def _wrapped_query_progress(cur: int, total: int) -> None:
                # 映射到 90%~99%：90 + 9×(cur/total)
                scaled = 90 + int(cur / total * 9) if total > 0 else 90
                on_query_progress(scaled, 100)

            _progress_cb = _wrapped_query_progress
        else:
            _progress_cb = on_query_progress

        results, q_stats = self.query(
            parsed,
            progress_callback=_progress_cb,
            result_callback=on_query_result,
        )
        # 查询完成（query_batch_parsed 内部 CSRES/溢出均已结束），进度到 100%
        if on_query_progress:
            on_query_progress(100, 100)
        report["query_found"] = q_stats.found
        logger.info("阶段耗时 query: %.1fs (%d 条)", _time.monotonic() - t_stage, q_stats.found)
        t_stage = _time.monotonic()
        # Stage 3: 下载
        dl_list = self._download_list
        if dl_list:
            if on_stage_change:
                on_stage_change("download", 0, len(dl_list))
            _, dl_stats = self.download_stream(on_progress=on_download_progress, on_result=on_download_result)
            report["download_success"] = dl_stats.success
        logger.info(
            "阶段耗时 download: %.1fs (%d 成功)",
            _time.monotonic() - t_stage,
            report["download_success"],
        )
        t_stage = _time.monotonic()
        # Stage 4: 归档（跳过待确认项）
        if on_stage_change:
            on_stage_change("archive", 0, len(parsed))
        to_archive = [p for p in parsed if getattr(p, "next_action", "") != "pending"]
        org_result = self.archive_standards(to_archive, on_result=on_archive_result)
        report["organize_moved"] = org_result.get("moved", 0)
        logger.info(
            "阶段耗时 archive: %.1fs (%d 已移动)",
            _time.monotonic() - t_stage,
            report["organize_moved"],
        )
        report["mirror_skipped"] = 0
        report["fallback_mirrored"] = 0
        t_stage = _time.monotonic()
        # Stage 5: 归档收容
        if self.cfg.get("storage.mirror_skipped_dirs", True):
            skipped = getattr(self, "_last_skipped_dirs", [])
            if skipped:
                if on_stage_change:
                    on_stage_change("mirror_skipped", 0, len(skipped))
                mirror_result = self.organize_skipped_dirs(skipped, source_root=root_path)
                report["mirror_skipped"] = mirror_result.get("moved", 0)
        if self.cfg.get("storage.mirror_fallback", True):
            if on_stage_change:
                on_stage_change("fallback", 0, 0)
            fallback_result = self.organize_fallback(root_path)
            report["fallback_mirrored"] = fallback_result.get("moved", 0)
        if on_stage_change:
            on_stage_change("done", 0, 0)
        logger.info(
            "阶段耗时 收容: %.1fs (镜像跳过%d 兜底%d)",
            _time.monotonic() - t_stage,
            report["mirror_skipped"],
            report["fallback_mirrored"],
        )
        logger.info(f"自动运行完成: {report}")
        return report

    # ════════════════════════════════════════════════════════════════
    # CLI 命令直通 — 消除 CLI 层的底层对象重复创建
    # ════════════════════════════════════════════════════════════════

    def organize_files(self, file_paths: list[str]) -> dict[str, Any]:
        """接受文件路径列表，解析后走完整 organizer_service 归档。供 cmd_move 调用。"""
        parsed = []
        for path in file_paths:
            if not os.path.isfile(path):
                continue
            info = self.parser.parse(os.path.basename(path))
            if info:
                info.source_path = path
                parsed.append(info)
        if not parsed:
            return {
                "moved": 0,
                "failed": 0,
                "skipped_exists": 0,
                "word_mirrored": 0,
                "skipped_source": 0,
                "dedup_skipped": 0,
                "details": ["无有效文件"],
            }
        return self.archive_standards(parsed)  # type: ignore[no-any-return]

    def expire_files(self, file_paths: list[str]) -> dict[str, Any]:
        """接受文件路径列表，解析后过期处理。供 cmd_expire 调用。"""
        items = []
        for path in file_paths:
            if not os.path.isfile(path):
                continue
            info = self.parser.parse(os.path.basename(path))
            if info:
                items.append((path, info))
        if not items:
            return {"moved": 0, "failed": 0, "details": ["无有效文件"]}
        return self._organizer_svc.handle_expired(items)  # type: ignore[no-any-return]

    def normalize_files(self, file_paths: list[str]) -> list[dict[str, Any]]:
        """返回文件规范化名称列表。供 cmd_normalize 调用。"""
        from ..core.file_utils import make_standard_filename
        from ..organizer.industry_lookup import get_folder_name

        results = []
        for path in file_paths:
            if not os.path.isfile(path):
                continue
            info = self.parser.parse(os.path.basename(path))
            if not info:
                continue
            norm_name = make_standard_filename(
                logical_code=info.logical_code,
                number=info.number,
                year=info.year,
                std_name=info.std_name,
                part=info.part,
                language=info.language,
                num_prefix=info.num_prefix,
                num_suffix=info.num_suffix,
                ext=info.ext,
            )
            folder = get_folder_name(info.logical_code)
            results.append(
                {
                    "source": path,
                    "logical_code": info.logical_code,
                    "number": info.number,
                    "year": info.year,
                    "normalized": norm_name,
                    "folder": folder,
                }
            )
        return results

    @staticmethod
    def _make_archive_filename(parsed: ParsedStdInfo) -> str:
        """根据已解析元数据统一生成归档文件名。"""
        from ..core.file_utils import make_standard_filename

        return make_standard_filename(
            logical_code=parsed.logical_code,
            number=parsed.number,
            year=parsed.year,
            std_name=parsed.std_name,
            part=getattr(parsed, "part", None),
            language=getattr(parsed, "language", ""),
            num_prefix=getattr(parsed, "num_prefix", ""),
            num_suffix=getattr(parsed, "num_suffix", ""),
            ext=getattr(parsed, "ext", "pdf"),
        )

    def normalize_files_stream(
        self,
        parsed_list: list[ParsedStdInfo],
        on_progress: Any = None,
        on_batch: Any = None,
    ) -> list[dict[str, Any]]:
        """流式规范化（线程安全）。回调签名:
        on_progress(current, total)  on_batch([(idx, ParsedStdInfo, name), ...])
        """
        from ..organizer.industry_lookup import get_folder_name

        results = []
        total = len(parsed_list)
        batch = []
        for i, parsed in enumerate(parsed_list):
            src_path = getattr(parsed, "source_path", "") or ""
            name = self._make_archive_filename(parsed)
            folder = get_folder_name(parsed.logical_code)
            results.append(
                {
                    "source": src_path,
                    "logical_code": parsed.logical_code,
                    "number": parsed.number,
                    "year": parsed.year,
                    "normalized": name,
                    "folder": folder,
                }
            )
            batch.append((i, parsed, name))
            if on_batch and len(batch) >= 50:
                on_batch(batch)
                batch = []
            if on_progress:
                on_progress(i + 1, total)
        if on_batch and batch:
            on_batch(batch)
        return results

    # ════════════════════════════════════════════════════════════════
    # 暴露内部组件方法 — 消除 UI/Web 层直接穿透子组件
    # ════════════════════════════════════════════════════════════════

    def get_query_sites(self) -> list[str]:
        """暴露所有查询站点名称列表。"""
        return self.query_engine.get_all_sites()

    def get_site_adapter(self, site_name: str) -> Any:
        """暴露指定站点的适配器实例（供 UI 取 site_label 等元数据）。"""
        return self.query_engine.get_adapter(site_name)

    def get_site_cooldown(self, site_name: str) -> float:
        """暴露指定站点的冷却剩余秒数。"""
        return self.query_engine.get_site_cooldown(site_name)

    def get_query_status(self) -> dict[str, bool]:
        """返回查询引擎运行时状态，供进度条轮询。
        返回值: {is_running, overflow_count, csres_active, is_idle}
        """
        result: dict[str, Any] = {
            "is_running": self.query_engine.is_query_running(),
            "overflow_count": self.query_engine.get_overflow_count(),
            "csres_active": self.query_engine.get_csres_status()["is_active"],
            "is_idle": self.query_engine.is_idle(),
        }
        return result

    def get_adapter_report(self) -> list[dict[str, Any]]:
        """返回所有适配器的统计汇总报告。
        每项包含：名称、总查询次数、成功率、平均响应时间、冷却次数、最后冷却原因。
        """
        return self.db.get_adapter_stats_all()

    def upsert_file_index(
        self,
        file_path: str,
        logical_code: str,
        number: int,
        year: int,
        part: Any = None,
        std_name: str = "",
        status: str = "现行",
    ) -> None:
        """封装 file_index.upsert，供 UI 层在归档完成后写入索引。"""
        if self.file_index:
            self.file_index.upsert(
                file_path=file_path,
                logical_code=logical_code,
                number=number,
                year=year,
                part=part,
                std_name=std_name,
                status=status,
            )

    def get_file_index(self, file_path: str) -> dict[str, Any] | None:
        """封装 file_index.get，供 UI 层查询文件索引。"""
        if self.file_index:
            return self.file_index.get(file_path)
        return None

    def get_file_index_full_info(self, logical_code: str, number: int) -> list[dict[str, Any]]:
        """封装 file_index.get_full_info，供 UI 层查询文件版本列表。"""
        if self.file_index:
            return self.file_index.get_full_info(logical_code, number)
        return []

    def parse_standard_number(self, filename: str) -> object | None:
        """封装 parser.parse，供 UI 层解析标准文件名。"""
        return self.parser.parse(filename)

    def restore_parsed_from_index(self, file_path: str) -> object | None:
        """从 file_index 恢复已解析的标准信息。"""
        if self.file_index:
            return self.file_index.restore_parsed(file_path)
        return None

    def shutdown(self) -> None:
        """关闭数据库连接，应用退出时调用。"""
        if self.db:
            self.db.close_all()
