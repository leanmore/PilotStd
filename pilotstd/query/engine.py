# pilotstd/query/engine.py
# 查询引擎：每日配额管理、任务分割、站点轮转冷却、采标校验

from __future__ import annotations

import re
import concurrent.futures
import threading
import time
import logging
from typing import Dict, List, Tuple, Optional, Callable

from ..query.search_strategy import MATCH_SCORE
#
# 架构说明：
#   查询引擎是标准查询的核心调度器。它管理多个网站适配器，按优先级和配额
#   分配查询任务。支持三种查询粒度：单条文本、单条结构化、批量并行。
#
#   路由机制：
#     1. 按标准代号（GB/ISO/SH 等）匹配预定义适配器链
#     2. 用户可在设置中自定义站点优先级（site_order）
#     3. 站点轮转器（SiteRotator）自动跳过冷却中的站点
#     4. 无适配器匹配时回退到全部已知适配器
#
#   配额机制：
#     DailyQuotaTracker 按日跟踪每个站点的请求次数，plan_batch 按配额
#     分割任务，超出配额的部分自动切换到下一个站点。

import concurrent.futures
import logging
import os
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple

from .adapters.base import BaseAdapter
from .cache import CacheRepository
from .models import QueryResult, BatchQueryStats
from .rotator import SiteRotator
from .daily_quota import DailyQuotaTracker
from .search_strategy import match_result

logger = logging.getLogger(__name__)

# 默认站点优先级（兜底，无代号匹配时使用）
PROD_PRIORITY = ["ahbz", "std_gov", "hbba", "iso_gov", "njbz365", "csres"]
# 国外标准默认路由：ahbz免鉴权优先，njbz365次选
FOREIGN_ROUTE = ["ahbz", "njbz365"]

# 按标准代号分流：专业站点优先，njbz365 二线，csres 国标/行业兜底
def _build_default_code_routes():
    from ..scan.parser import FOREIGN_CODE_SET
    from ..organizer.industry_lookup import _DB_PROVINCE_MAP
    routes = {
        "GB":   ["std_gov", "ahbz", "njbz365", "csres"],
        "GB/T": ["std_gov", "ahbz", "njbz365", "csres"],
        "GB/Z": ["std_gov", "ahbz", "njbz365", "csres"],
        "GSB":  ["std_gov", "ahbz", "njbz365", "csres"],
        "ISO":  ["iso_gov", "ahbz", "njbz365"],
        "IEC":  ["iso_gov", "ahbz", "njbz365"],
    }
    # 地方标准省级代码：DB11, DB11/T, DB35, DB35/T 等 → dbba 优先
    for province_code in _DB_PROVINCE_MAP:
        routes[f"DB{province_code}"] = ["dbba", "ahbz", "njbz365"]
        routes[f"DB{province_code}/T"] = ["dbba", "ahbz", "njbz365"]
    for fc in FOREIGN_CODE_SET:
        if fc not in routes:
            routes[fc] = list(FOREIGN_ROUTE)
    # 省级DB代码已在上方动态生成，市级DB代码未命中时走行业路由
    return routes

CODE_ROUTES = _build_default_code_routes()
# 行业标准（SH/NB/HG/JB 等）：行标平台优先，njbz365二线，csres兜底
INDUSTRY_ROUTE = ["hbba", "ahbz", "njbz365", "csres"]


class QueryEngine:
    """查询引擎：缓存优先 + 多适配器回退 + 配额感知。

    典型用法:
        engine = QueryEngine(adapters=[...], cache=cache)
        result = engine.query_parsed("GB/T", 19001, 2020)
        results, stats = engine.query_batch_parsed(parsed_list)
    """

    def __init__(self, adapters: List[BaseAdapter], cache: CacheRepository,
                 use_cache: bool = True, rotator: SiteRotator = None,
                 quota_tracker: DailyQuotaTracker = None,
                 site_order: List[str] = None,
                 query_interval: tuple = None,
                 parser = None):
        self._adapters = adapters
        # site_name → adapter 映射，O(1) 查找
        self._adapter_map: Dict[str, BaseAdapter] = {a.site_name: a for a in adapters}
        self._cache = cache
        self._use_cache = use_cache
        self._rotator = rotator          # 站点轮转（冷却管理）
        self.rotator = rotator            # 公开引用，供外部（如测试）查询冷却状态
        self._quota = quota_tracker      # 每日配额
        self._site_order = site_order    # 用户自定义优先级
        self._parser = parser            # StandardParser 实例，query_batch 解析用
        # 查询间隔（含随机抖动）：(最小秒, 最大秒)，如 (0.5, 1.5)。None=不启用
        self._query_interval = query_interval

    # ════════════════════════════════════════════════════════════════
    # 公共 API
    # ════════════════════════════════════════════════════════════════

    def query_parsed(self, logical_code: str, number: int, year: int,
                     std_name: str = "", part: int = None,
                     force_refresh: bool = False,
                     num_prefix: str = "") -> QueryResult:
        """根据结构化信息查询（比 query_single 更精准）。

        使用 query_with_strategy 进行渐进式搜索：
        先用精确关键词，未命中则放宽条件，多候选打分取最优。
        """
        part_str = f".{part}" if part else ""
        target = f"{logical_code} {number}{part_str}-{year}"
        if self._use_cache and not force_refresh:
            for adapter in self._adapters:
                cached = self._cache.get(target, adapter.site_name)
                if cached:
                    logger.debug(f"查询 [{target}] 缓存命中 @{cached.source_site}")
                    return cached

        priority = self._get_priority(logical_code)
        # 全部站点冷却中 → 等待恢复
        if self._rotator and not priority:
            logger.warning("所有站点均在冷却中，等待恢复...")
            self._rotator.wait_for_any_recovery(
                [a.site_name for a in self._adapters])
            priority = self._get_priority(logical_code)
            logger.info("站点冷却恢复，继续查询")
        logger.debug(f"查询 [{target}] 路由={'→'.join(priority) if priority else '(全部冷却)'}")

        quota_exhausted = True
        tried: list[str] = []
        for name in priority:
            adapter = self._adapter_map.get(name)
            if adapter is None:
                continue
            if self._quota and self._quota.get_search_remaining(name) <= 0:
                logger.warning(f"{adapter.site_label}({name}) 今日配额已用尽，跳过")
                continue
            quota_exhausted = False
            tried.append(name)
            result = adapter.query_with_strategy(logical_code, number, year, std_name, part, num_prefix=num_prefix)
            if result and result.is_found():
                result.source_site = adapter.site_name
                if not result.standard_number:
                    result.standard_number = target
                result = self._verify_adoption(result)
                # 查询结果始终写入缓存（不受 use_cache 控制）
                if getattr(result, 'match_status', '') == 'exact':
                    self._cache.put(result)
                self._record(name, 1)
                logger.info(f"查询 [{target}] ✓{name}({result.match_status}) tried={'→'.join(tried)}")
                return result

        if quota_exhausted:
            logger.info(f"查询 [{target}] ✗配额耗尽")
            return QueryResult(
                standard_number=target,
                error_message="所有站点今日配额已用尽，请明日再试",
                source_site="")
        logger.info(f"查询 [{target}] ✗ tried={'→'.join(tried)}")
        return QueryResult(
            standard_number=target,
            error_message="所有来源均未找到该标准",
            source_site="")

    def plan_batch(self, total: int, logical_code: str = "") -> List[tuple]:
        """按配额预估分配方案（供 UI 展示）。返回 [(site_name, count), ...]"""
        plan = []
        remaining = total
        priority = self._get_priority(logical_code)
        if self._quota is None:
            return [(priority[0], total)] if priority else []
        for name in priority:
            if remaining <= 0:
                break
            quota = self._quota.get_search_remaining(name)
            if quota <= 0:
                continue
            take = min(remaining, quota)
            plan.append((name, take))
            remaining -= take
        return plan

    def get_quota_info(self) -> dict:
        """返回各站点配额信息（供 UI 弹窗展示）。"""
        if self._quota:
            return self._quota.get_all_remaining()
        return {}

    def get_adapter(self, name: str):
        """获取指定站点适配器（供 PendingQueryDialog 使用）。"""
        return self._adapter_map.get(name)

    def get_site_cooldown(self, name: str) -> float:
        """返回指定站点剩余冷却秒数，0=不在冷却中。"""
        if self._rotator:
            return self._rotator.get_cooldown_remaining(name)
        return 0.0

    def get_all_sites(self) -> List[str]:
        """返回所有已注册站点名称。"""
        return list(self._adapter_map.keys())

    # ════════════════════════════════════════════════════════════════
    # 内部方法
    # ════════════════════════════════════════════════════════════════
    def _get_priority(self, logical_code: str = "") -> List[str]:
        """按标准代号返回适配器优先级链。

        优先级决定因素（按顺序）：
          1. 标准代号匹配（CODE_ROUTES）
          2. 代号长度 ≤4 且非 ISO/IEC → 行业标准路由
          3. 其他 → 国外标准路由或默认全链
          4. 用户自定义 site_order 置顶
          5. 站点轮转过滤（冷却中跳过）
          6. 过滤后为空则回退到全部已知适配器
        """
        # 步骤1：确定基础路由
        if logical_code in CODE_ROUTES:
            base = CODE_ROUTES[logical_code]
        elif logical_code and re.match(r'^DB\d{2,4}(?:/T)?$', logical_code):
            base = ["dbba", "njbz365"]  # 市级DB代码 → 地方标准平台优先
        elif logical_code:
            # 先查是否为国外代号（避免 AWWA/SAE/NFPA 等 4 字符国外代号误入行业路由）
            from ..scan.parser import FOREIGN_CODE_SET, ITU_CODES, CAC_PREFIXES
            code_no_space = logical_code.upper().replace(" ", "")
            is_foreign = any(
                code_no_space.startswith(fc.upper().replace(" ", ""))
                for fc in FOREIGN_CODE_SET
            )
            if not is_foreign:
                is_foreign = any(
                    logical_code.upper().startswith(itu.upper())
                    for itu in ITU_CODES
                )
            if not is_foreign:
                is_foreign = any(
                    logical_code.upper().startswith(cac.upper())
                    for cac in CAC_PREFIXES
                )
            if is_foreign:
                base = FOREIGN_ROUTE
            elif len(logical_code) <= 4:
                base = INDUSTRY_ROUTE
            else:
                base = FOREIGN_ROUTE
        else:
            base = PROD_PRIORITY

        # 步骤2：用户自定义优先级叠加（置顶）
        if self._site_order:
            base = list(self._site_order) + [s for s in base if s not in self._site_order]

        # 步骤3：站点轮转过滤（冷却中的站点暂时跳过）
        if self._rotator:
            base = self._rotator.get_available(base)

        # 步骤4：过滤出已注册的适配器
        known = set(self._adapter_map.keys())
        pri = [n for n in base if n in known]
        # 过滤后为空（如测试环境的 mock 适配器不在路由表中）→ 回退到全部已知
        if not pri and known:
            pri = [a.site_name for a in self._adapters]
            # 国外路由回退时排除国标/行标专属站点，避免 ASME 等被送到 csres/std_gov
            if base == FOREIGN_ROUTE:
                pri = [n for n in pri if n not in ("std_gov", "hbba")]
        return pri

    def _record(self, site_name: str, count: int):
        """记录配额消耗 + 通知站点轮转器记录成功请求。"""
        if self._quota:
            self._quota.record_usage(site_name, count)
        if self._rotator:
            for _ in range(count):
                self._rotator.record_success(site_name)

    def _verify_adoption(self, result: QueryResult) -> QueryResult:
        """采标检测：判断是否为采标标准，采标标准不可直接下载。"""
        if not result.is_adopted and "采标" in result.status:
            result.is_adopted = True
        result.is_downloadable = not result.is_adopted
        return result

    # ════════════════════════════════════════════════════════════════
    # 逐桶查询（V2）：桶内串行 + 桶间并行 + 临时桶链迭代
    # ════════════════════════════════════════════════════════════════

    # 子桶大小（压测后数据驱动动态化）
    _BUCKET_SIZE = 80
    # 子桶间冷却间隔（秒）
    _BUCKET_INTERVAL = 30
    # csres 日配额（30 GB + 20 行业）
    _CSRES_LIMIT = 50
    # csres 连续失败熔断阈值
    _CSRES_CIRCUIT_BREAK = 5
    # 溢出站点共享配额（ahbz: 200 中 170 给溢出, njbz365: 200 全给溢出）
    _AHBZ_OVERFLOW_QUOTA = 170
    _NJBZ_OVERFLOW_QUOTA = 200

    def _bucket_key(self, logical_code: str) -> str:
        """按 _get_priority 第一条（主站点）确定桶标识。"""
        priority = self._get_priority(logical_code)
        return priority[0] if priority else "other"

    def _build_chain_for_item(self, item: tuple) -> list:
        """返回条目对应的完整优先级链（不含 csres）。"""
        logical_code = item[0]
        chain = self._get_priority(logical_code)
        # 从链中移除 csres（csres 由独立线程处理）
        return [s for s in chain if s != "csres"]

    def query_batch_parsed(self,
                           parsed_list: List[Tuple[str, int, int, str, Optional[int], str]],
                           progress_callback: Callable[[int], None] = None,
                           result_callback: Callable[[int, QueryResult], None] = None,
                           preferred_site: str = "",
                           ) -> List[QueryResult]:
        """逐桶查询版——桶内串行+桶间并行+临时桶链迭代。"""
        import time as _time
        _bucket_t0 = _time.time()
        n = len(parsed_list)
        results: Dict[int, QueryResult] = {}
        counter_lock = threading.Lock()
        counter = [0]

        def bump():
            with counter_lock:
                counter[0] += 1
                if progress_callback:
                    progress_callback(counter[0])

        # ── 1. 分组 ──
        buckets: Dict[str, List[Tuple[int, tuple]]] = {}
        for i, item in enumerate(parsed_list):
            key = self._bucket_key(item[0])
            # GB 类标准：ahbz 与 std_gov 同为一线，交替分配错开冷却
            if key == "std_gov":
                from ..core.std_utils import classify_std_code
                if classify_std_code(item[0]) == "gb" and i % 2 == 0:
                    key = "ahbz"
            buckets.setdefault(key, []).append((i, item))

        for key, items in buckets.items():
            logger.info("[BUCKET] %s total=%d", key, len(items))

        # ── 2. 全局溢出配额锁 ──
        overflow_lock = threading.Lock()
        overflow_quota = {
            "ahbz": [self._AHBZ_OVERFLOW_QUOTA],
            "njbz365": [self._NJBZ_OVERFLOW_QUOTA],
        }

        def _try_overflow(site: str) -> bool:
            """尝试从溢出池扣减配额，成功返回 True。"""
            if site not in overflow_quota:
                return True
            with overflow_lock:
                if overflow_quota[site][0] > 0:
                    overflow_quota[site][0] -= 1
                    return True
            return False

        # ── 3. csres 独立线程 ──
        csres_results: Dict[int, QueryResult] = {}
        csres_failures = [0]

        def _csres_worker(gb_items, industry_items):
            adapter = self._adapter_map.get("csres")
            if not adapter:
                return
            import random as _random
            import time as _time
            gb_take = int(self._CSRES_LIMIT * 0.6)  # 30
            industry_take = self._CSRES_LIMIT - gb_take  # 20
            pool = gb_items[:gb_take] + industry_items[:industry_take]
            _last_ts = _time.time()
            for idx, item in pool:
                if csres_failures[0] >= self._CSRES_CIRCUIT_BREAK:
                    break
                try:
                    result = adapter.query_with_strategy(
                        item[0], item[1], item[2], num_prefix=item[3], part=item[4])
                    if result:
                        result.source_site = "csres"
                        csres_results[idx] = result
                        csres_failures[0] = 0
                        logger.info("[CSRES] idx=%d code=%s action=found score=100",
                                    idx, item[0])
                    else:
                        csres_failures[0] += 1
                        logger.info("[CSRES] idx=%d code=%s action=not_found failures=%d/%d",
                                    idx, item[0], csres_failures[0], self._CSRES_CIRCUIT_BREAK)
                except Exception:
                    csres_failures[0] += 1
                    logger.info("[CSRES] idx=%d code=%s action=error failures=%d/%d",
                                idx, item[0], csres_failures[0], self._CSRES_CIRCUIT_BREAK)
                delay = _random.uniform(5, 10)
                _time.sleep(delay)
                now = _time.time()
                logger.info("[CSRES_INTERVAL] actual=%.1fs target=%.1fs",
                           now - _last_ts, delay)
                _last_ts = now

        # ── 4. 桶工作线程 ──
        bucket_times: Dict[str, tuple] = {}  # {key: (start, end, done, overflowed)}
        site_usage: Dict[str, int] = {}  # {site: count}
        usage_lock = threading.Lock()

        def _record_usage(site: str):
            with usage_lock:
                site_usage[site] = site_usage.get(site, 0) + 1

        # 追踪结构
        overflow_events: list = []      # (timestamp, from_bucket, to_site, idx)
        match_scores: Dict[str, Dict[str, int]] = {}  # {site: {match_status: count}}
        item_chains: Dict[int, list] = {}  # {idx: [site1, site2, ...]}
        pending_reasons: list = []       # [(idx, chain_str)]
        score_lock = threading.Lock()

        def _record_match(site: str, status: str):
            with score_lock:
                if site not in match_scores:
                    match_scores[site] = {}
                match_scores[site][status] = match_scores[site].get(status, 0) + 1

        def _bucket_worker(bucket_items, primary_site: str):
            _ts = _time.time()
            chain = self._get_priority(bucket_items[0][1][0]) if bucket_items else []
            chain = [s for s in chain if s != "csres"]
            # 桶键可能不是链首（如 GB 分桶到 ahbz），裁剪链从当前主站开始
            if primary_site in chain:
                chain = chain[chain.index(primary_site):]

            sub_buckets = [bucket_items[i:i + self._BUCKET_SIZE]
                          for i in range(0, len(bucket_items), self._BUCKET_SIZE)]
            overflow_items = []

            for sb_idx, sub in enumerate(sub_buckets):
                if sb_idx > 0:
                    _time.sleep(self._BUCKET_INTERVAL)

                for idx, item in sub:
                    # 检查冷却
                    if self._rotator and self._rotator.get_cooldown_remaining(primary_site) > 0:
                        # 主站点冷却→尝试溢出到链上下一个站点
                        remaining = self._rotator.get_cooldown_remaining(primary_site)
                        logger.info("[COOLDOWN] site=%s action=overflow_skip "
                                    "remaining_s=%.0f chain=%s",
                                    primary_site, remaining, "→".join(chain))
                        overflow_site = chain[1] if len(chain) > 1 else None
                        if overflow_site and _try_overflow(overflow_site):
                            assigned_site = overflow_site
                        else:
                            overflow_items.append((idx, item))
                            continue
                    else:
                        assigned_site = primary_site

                    adapter = self._adapter_map.get(assigned_site)
                    if not adapter:
                        overflow_items.append((idx, item))
                        continue

                    try:
                        result = adapter.query_with_strategy(
                            item[0], item[1], item[2], item[3], item[4])
                    except Exception:
                        overflow_items.append((idx, item))
                        continue

                    if result:
                        result.source_site = assigned_site
                        self._record(assigned_site, 1)
                        _record_usage(assigned_site)
                        _record_match(assigned_site, getattr(result, 'match_status', 'err'))
                        score = MATCH_SCORE.get(getattr(result, 'match_status', ''), 0)
                        # 记条目链
                        item_chains.setdefault(idx, []).append(assigned_site)
                        if score >= 100:
                            results[idx] = result
                            if result_callback and result.is_found():
                                result_callback(idx, result)
                            bump()
                        else:
                            # 未达100分 → 溢出
                            overflow_events.append((_time.time(), primary_site, assigned_site, idx))
                            overflow_items.append((idx, item))
                    else:
                        overflow_items.append((idx, item))

            done = len(bucket_items) - len(overflow_items)
            return (overflow_items, _time.time() - _ts, done)

        # ── 5. 桶间并行执行 ──
        csres_pool_gb = []
        csres_pool_industry = []
        all_overflow = []
        bucket_futures = {}

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            for bucket_key, items in buckets.items():
                if not items:
                    continue
                future = executor.submit(_bucket_worker, items, bucket_key)
                bucket_futures[future] = bucket_key
                # 收集 csres 候选条目
                if bucket_key in ("std_gov",):
                    csres_pool_gb.extend(items)
                elif bucket_key in ("hbba",):
                    csres_pool_industry.extend(items)

            # csres 独立线程
            csres_future = executor.submit(_csres_worker, csres_pool_gb, csres_pool_industry)

            # 收集桶结果
            for future in concurrent.futures.as_completed(bucket_futures):
                try:
                    overflow, elapsed, done = future.result()
                    key = bucket_futures[future]
                    bucket_times[key] = (_bucket_t0, _bucket_t0 + elapsed, done, len(overflow))
                    all_overflow.extend(overflow)
                except Exception:
                    logger.exception("桶执行异常: %s", bucket_futures[future])

            # 等待 csres 完成
            try:
                csres_future.result(timeout=600)
            except Exception:
                pass

        # ── 6. 合并 csres 结果 ──
        for idx, result in csres_results.items():
            if idx not in results:
                results[idx] = result
                bump()

        # ── 7. 临时桶：链迭代（微批 + 抖动防惊群）──
        temp_cooldown_skips = 0
        if all_overflow:
            # 按剩余站点数升序
            all_overflow.sort(key=lambda x: len(self._build_chain_for_item(x[1])))
            # 微批：每批 20 条，批次间 2-5s 随机抖动
            batch_size = 20
            for batch_start in range(0, len(all_overflow), batch_size):
                batch = all_overflow[batch_start:batch_start + batch_size]
                if batch_start > 0:
                    import random as _random
                    jitter = _random.uniform(2, 5)
                    _time.sleep(jitter)
                for idx, item in batch:
                    if idx in results:
                        continue
                    chain = self._build_chain_for_item(item)
                    # 主站点已查过，从二线开始
                    start = 1 if chain and chain[0] == self._bucket_key(item[0]) else 0
                    found = False
                    tried_chain = item_chains.get(idx, [])
                    for site in chain[start:]:
                        if site not in self._adapter_map:
                            continue
                        if self._rotator and self._rotator.get_cooldown_remaining(site) > 0:
                            temp_cooldown_skips += 1
                            continue
                        adapter = self._adapter_map[site]
                        try:
                            result = adapter.query_with_strategy(
                                item[0], item[1], item[2], item[3], item[4])
                        except Exception:
                            continue
                        if result:
                            result.source_site = site
                            self._record(site, 1)
                            _record_match(site, getattr(result, 'match_status', 'err'))
                            tried_chain.append(site)
                            item_chains[idx] = tried_chain
                            score = MATCH_SCORE.get(getattr(result, 'match_status', ''), 0)
                            if score >= 100:
                                results[idx] = result
                                if result_callback and result.is_found():
                                    result_callback(idx, result)
                                bump()
                                found = True
                                break
                    # 链耗尽→待确认
                    if not found:
                        chain_str = "→".join(item_chains.get(idx, [])) or "none"
                        pending_reasons.append((idx, chain_str))
                        results[idx] = QueryResult(
                            standard_number=f"{item[0]} {item[1]}-{item[2]}",
                            standard_name=item[3],
                            status="待确认",
                            source_site="",
                            match_status="chain_exhausted")
                        bump()

        # ── 桶统计 ──
        for key in sorted(bucket_times.keys()):
            start, end, done, ov = bucket_times[key]
            logger.info("[BUCKET] %s total=%d done=%d overflow=%d elapsed=%.1fs",
                       key, done + ov, done, ov, end - _bucket_t0)
        logger.info("[TIMELINE] buckets=%d overlap_total=%.1fs",
                   len(bucket_times), _time.time() - _bucket_t0)

        # ── 站点配额日志 ──
        for site in sorted(site_usage.keys()):
            logger.info("[QUOTA] site=%s used=%d", site, site_usage[site])

        # ── 溢出时序 ──
        logger.info("[OVERFLOW] events=%d", len(overflow_events))

        # ── csres 状态 ──
        csres_hit = len(csres_results)
        logger.info("[CSRES] processed=%d failures=%d", csres_hit, csres_failures[0])

        # ── 站点评分卡 ──
        for site in sorted(match_scores.keys()):
            score_dist = " ".join(f"{k}={v}" for k, v in sorted(match_scores[site].items()))
            logger.info("[SCORE] site=%s %s", site, score_dist)

        # ── 条目链追踪（前 20 条）──
        for idx in sorted(item_chains.keys())[:20]:
            chain_str = "→".join(item_chains[idx])
            logger.info("[CHAIN] #%d %s", idx, chain_str)

        # ── 待确认归因 ──
        for idx, chain_str in pending_reasons[:10]:
            logger.info("[PENDING] #%d chain=%s", idx, chain_str)

        # ── 配额水位 ──
        logger.info("[WATER] ahbz_overflow_remain=%d njbz365_remain=%d",
                   overflow_quota["ahbz"][0], overflow_quota["njbz365"][0])
        logger.info("[RECOVERY] temp_cooldown_skips=%d", temp_cooldown_skips)

        # ── 漏斗汇总 ──
        pending_count = len(pending_reasons)
        logger.info("[FUNNEL] total=%d ok=%d overflow=%d pending=%d",
                   n, len(results) - pending_count, len(all_overflow), pending_count)
        logger.info("[TIMELINE] query_bucketed_done total=%d elapsed=%.1fs",
                   n, _time.time() - _bucket_t0)
        logger.info("[BASELINE] total=%d ok=%d overflow=%d pending=%d elapsed=%.1fs",
                   n, len(results) - pending_count, len(all_overflow), pending_count,
                   _time.time() - _bucket_t0)

        # ── 8. 按原始顺序组装 ──
        return [results.get(i, QueryResult(
            standard_number=f"{parsed_list[i][0]} {parsed_list[i][1]}-{parsed_list[i][2]}",
            error_message="查询未完成", source_site=""))
            for i in range(n)]
