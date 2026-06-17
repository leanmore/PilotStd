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
        result = engine.query_single("GB/T 19001—2020")
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

    def query_single(self, standard_number: str,
                     force_refresh: bool = False) -> QueryResult:
        """根据标准号字符串查询单个标准。

        流程：缓存命中直接返回 → 按优先级遍历适配器 → 首个命中即返回。
        适用于命令行或 API 调用，只需标准号文本即可。
        """
        # 先查缓存（force_refresh=True 时跳过）
        if self._use_cache and not force_refresh:
            for adapter in self._adapters:
                cached = self._cache.get(standard_number, adapter.site_name)
                if cached:
                    return cached

        # 按优先级链依次尝试各适配器
        # 从标准号字符串提取代号（如 "NB/T 20646-2023" → "NB/T"），用于精确路由
        code_match = re.match(r'([A-Z]{2,}(?:\s*/\s*[A-Z]+)?)', standard_number.strip())
        logical_code = code_match.group(1).replace(" ", "") if code_match else ""
        priority = self._get_priority(logical_code)
        quota_exhausted = True
        for name in priority:
            adapter = self._adapter_map.get(name)
            if adapter is None:
                continue
            # 配额耗尽则跳过该站点
            if self._quota and self._quota.get_search_remaining(name) <= 0:
                logger.warning(f"{adapter.site_label}({name}) 今日配额已用尽，跳过")
                continue
            quota_exhausted = False
            result = adapter.query_single(standard_number)
            if result and result.is_found():
                result.source_site = adapter.site_name
                result = self._verify_adoption(result)  # 采标检测
                # 查询结果始终写入缓存（不受 use_cache 控制，use_cache 仅控制读取）
                if getattr(result, 'match_status', '') == 'exact':
                    self._cache.put(result)
                self._record(name, 1)  # 记录配额消耗 + 轮转成功
                return result
            if result and result.error_message:
                logger.warning(f"查询失败 {standard_number} @ {adapter.site_name}: {result.error_message}")

        # 所有站点都未命中
        if quota_exhausted:
            return QueryResult(
                standard_number=standard_number,
                error_message="所有站点今日配额已用尽，请明日再试",
                source_site="")
        return QueryResult(
            standard_number=standard_number,
            error_message="所有来源均未找到该标准",
            source_site="")

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

    def query_batch(self, standard_numbers: List[str],
                    force_refresh: bool = False,
                    progress_callback: Callable[[int, int], None] = None,
                    preferred_site: str = "") -> tuple:
        """批量查询标准号列表。StandardParser 解析失败的条目跳过。"""
        total = len(standard_numbers)
        parsed: List[Tuple[str, int, int, str, Optional[int], str]] = []
        for s in standard_numbers:
            info = self._parser.parse(s + ".pdf") if self._parser else None
            if info:
                parsed.append((info.logical_code, info.number, info.year,
                              info.std_name or "", info.part,
                              getattr(info, "num_prefix", ""),
                              getattr(info, "num_suffix", ""), ""))
            else:
                logger.warning("无法解析标准号，跳过: %s", s)

        cb = (lambda c: progress_callback(c, total)) if progress_callback else None
        results = self.query_batch_parsed(parsed, progress_callback=cb,
                                          preferred_site=preferred_site)

        # 从结果列表构建统计（保持与原接口兼容）
        stats = BatchQueryStats()
        stats.total = total
        for r in results:
            if r.is_found():
                stats.found += 1
                if r.status == "待确认":
                    stats.pending += 1
                elif r.is_downloadable:
                    stats.downloadable += 1
                else:
                    stats.adopted_restricted += 1
            elif r.error_message:
                stats.not_found += 1
            else:
                stats.errors += 1
        return results, stats

    def query_batch_parsed(self,
                           parsed_list: List[Tuple[str, int, int, str, Optional[int], str]],
                           progress_callback: Callable[[int], None] = None,
                           result_callback: Callable[[int, QueryResult], None] = None,
                           preferred_site: str = "",
                           ) -> List[QueryResult]:
        """多线程批量查询（动态路由版）。

        逐轮分配+执行：每轮按当前冷却/配额状态重新分配，
        站点冷却后其未处理条目回池，下轮自然路由到同类型的其他站点。
        结果按原始顺序组装返回。

        Args:
            parsed_list: [(logical_code, number, year, std_name, part, num_prefix), ...]
            progress_callback: 每个标准完成后回调当前计数（线程安全）
            result_callback: 每条结果就绪时回调 (index, QueryResult)（线程安全）

        Returns:
            与输入顺序一致的 QueryResult 列表
        """
        n = len(parsed_list)
        results: Dict[int, QueryResult] = {}
        # remaining: [(原始索引, item_tuple), ...]
        remaining: List[Tuple[int, tuple]] = list(enumerate(parsed_list))
        counter = [0]
        lock = threading.Lock()
        max_rounds = len(self._adapter_map) + 2  # 最多每站点一轮 + 缓冲
        # 统计：每轮完成的条目数和冷却回池数
        round_stats: List[dict] = []

        def bump():
            with lock:
                counter[0] += 1
                if progress_callback:
                    progress_callback(counter[0])

        for _round in range(max_rounds):
            if not remaining:
                break

            # ── 按当前状态重新分配 ──
            remaining_items = [item for _, item in remaining]
            plan = self._plan_batch(remaining_items, preferred_site)
            if not plan:
                break

            # ── 构建站点批次（子索引 → 原始索引映射）──
            site_batches: List[Tuple[str, List[Tuple[int, tuple]]]] = []
            for site_name, batch in plan.items():
                mapped = [(remaining[sub_idx][0], item) for sub_idx, item in batch]
                site_batches.append((site_name, mapped))

            # ── 并行执行 ──
            round_ok = round_cooled = round_retry = 0
            next_remaining: List[Tuple[int, tuple]] = []
            with concurrent.futures.ThreadPoolExecutor(
                    max_workers=min(len(site_batches), 4)) as executor:
                futures = {}
                for site_name, batch in site_batches:
                    future = executor.submit(
                        self._run_site_batch, site_name, batch, bump, result_callback)
                    futures[future] = (site_name, batch)

                for future in concurrent.futures.as_completed(futures):
                    site_name, batch = futures[future]
                    try:
                        batch_results = future.result()
                    except Exception as e:
                        logger.error(f"站点 {site_name} 线程异常: {e}")
                        for idx, entry in batch:
                            if idx not in results:
                                results[idx] = QueryResult(
                                    standard_number=f"{entry[0]} {entry[1]}-{entry[2]}",
                                    error_message=f"查询线程异常: {e}",
                                    source_site=site_name)
                        continue

                    for idx, result, status in batch_results:
                        if status == "ok":
                            results[idx] = result
                            round_ok += 1
                        elif status == "retry":
                            # 类型链已全试但没100分，接受最佳结果
                            results[idx] = result
                            round_retry += 1
                        elif status == "cooled":
                            # 站点冷却没试成，回池下轮重分配
                            orig_item = parsed_list[idx]
                            next_remaining.append((idx, orig_item))
                            round_cooled += 1

            remaining = next_remaining
            round_stats.append({"round": _round + 1, "ok": round_ok,
                               "retry": round_retry, "cooled": round_cooled,
                               "remaining": len(remaining)})

            if not remaining:
                break

            # 全部站点冷却中 → 等待恢复
            all_cooling = True
            for site_name in self._adapter_map:
                if self._rotator and self._rotator.get_cooldown_remaining(site_name) <= 0:
                    all_cooling = False
                    break
            if all_cooling and self._rotator:
                logger.warning("全部站点冷却中，等待恢复...")
                self._rotator.wait_for_any_recovery(
                    list(self._adapter_map.keys()))
                logger.info("站点冷却恢复，继续查询")

        # ── 查询统计汇总 ──
        if round_stats:
            total_ok = sum(r["ok"] for r in round_stats)
            total_retry = sum(r["retry"] for r in round_stats)
            total_cooled = sum(r["cooled"] for r in round_stats)
            logger.info("查询完成: %d/%d 条, %d 轮, ok=%d retry=%d cooled=%d",
                        len(results), n, len(round_stats), total_ok, total_retry, total_cooled)
            for r in round_stats:
                logger.info("  第%d轮: ok=%d retry=%d cooled=%d 剩余=%d",
                           r["round"], r["ok"], r["retry"], r["cooled"], r["remaining"])

        # ── 未完成条目兜底 ──
        for idx, item in remaining:
            if idx not in results:
                full_num = f"{item[0]} {item[1]}-{item[2]}"
                results[idx] = QueryResult(
                    standard_number=full_num,
                    error_message="所有站点均无法处理该标准",
                    source_site="")

        # ── 按原始顺序组装 ──
        full_num = lambda p: f"{p[0]} {p[1]}-{p[2]}"
        return [results.get(i, QueryResult(
            standard_number=full_num(parsed_list[i]),
            error_message="查询未完成", source_site=""))
            for i in range(n)]

    def _run_site_batch(self, site_name: str,
                        batch: List[Tuple[int, tuple]],
                        progress_callback: Callable[[], None],
                        result_callback: Callable[[int, QueryResult], None] = None,
                        ) -> List[Tuple[int, QueryResult, str]]:
        """单个站点线程的执行体。返回 (idx, result, status)。
        status: "ok"=已完成, "retry"=未达100分回池重试, "cooled"=站点冷却回池

        逐条查询 batch 中的标准：
          1. 主站点冷却 → 整批标记 "cooled" 回池
          2. 主站点未达100分 → 按路由链回退到同类型其他站点
          3. 整条链都没有100分 → 标记 "retry" 回池
        """
        from ..query.search_strategy import MATCH_SCORE
        results: List[Tuple[int, QueryResult, str]] = []
        primary_adapter = self._adapter_map.get(site_name)
        site_cooled = False

        for idx, entry in batch:
            result = None
            logical_code = entry[0]
            number = entry[1]
            year = entry[2]
            std_name = entry[3]
            part = entry[4]
            num_prefix = entry[5]
            num_suffix = entry[6] if len(entry) > 6 else ""
            src_path = entry[7] if len(entry) > 7 else ""
            part_str = f".{part}" if part else ""
            target = f"{logical_code} {num_prefix or ''}{number}{num_suffix or ''}{part_str}-{year}"
            src_hint = os.path.basename(src_path) if src_path else ""
            target_display = f"{target} ← {src_hint}" if src_hint else target
            tried: list[str] = []

            # 主站点冷却中 → 本条及后续全部回池，不继续请求
            if self._rotator and self._rotator.get_cooldown_remaining(site_name) > 0:
                if not site_cooled:
                    logger.info("站点 %s 冷却中，剩余条目回池重分配", site_name)
                    site_cooled = True
                results.append((idx, QueryResult(
                    standard_number=target,
                    error_message="站点冷却中，等待重分配",
                    source_site=""), "cooled"))
                continue

            # 先查缓存（遍历所有适配器，不限来源站点）
            if self._use_cache and not getattr(self, '_force_refresh', False):
                for adapter in self._adapters:
                    cached = self._cache.get(target, adapter.site_name)
                    if cached:
                        result = cached
                        result.source_site = getattr(cached, 'source_site', adapter.site_name)
                        score = MATCH_SCORE.get(getattr(result, 'match_status', ''), 0)
                        if score >= 100:
                            logger.debug(f"查询 [{target_display}] 缓存命中 @{result.source_site}({getattr(result, 'match_status', '')})")
                            results.append((idx, result, "ok"))
                            progress_callback()
                            break
                else:
                    # 缓存未命中，走网络（循环正常结束）
                    result = None
                if result is not None:
                    continue  # 缓存命中，跳过本条网络查询

            # 类型路由链（含主站点，用于回退遍历）
            priority = self._get_priority(logical_code)
            if not priority:
                priority = [site_name]

            # 遍历类型路由链，直到拿到100分或整链耗尽
            best_result = None
            best_score = -1
            for name in priority:
                if self._rotator and self._rotator.get_cooldown_remaining(name) > 0:
                    continue  # 该站点冷却中，跳过
                adapter = self._adapter_map.get(name)
                if adapter is None:
                    continue
                if name != site_name and self._quota and self._quota.get_search_remaining(name) <= 0:
                    continue
                tried.append(name)
                result = adapter.query_with_strategy(
                    logical_code, number, year, std_name, part,
                    num_prefix=num_prefix, num_suffix=num_suffix)
                if result:
                    result.source_site = name
                    self._record(name, 1)
                    score = MATCH_SCORE.get(getattr(result, 'match_status', ''), 0)
                    if score > best_score:
                        best_result = result
                        best_score = score
                    if score == 100:
                        break  # 拿到100分，停止回退
                elif name == site_name:
                    self._record(name, 1)

            result = best_result

            # 构建最终结果 + INFO 单行日志
            if not result:
                result = QueryResult(
                    standard_number=target,
                    error_message="所有来源均未找到该标准",
                    source_site="")
                logger.info(f"查询 [{target_display}] [NG] tried={'→'.join(tried)}")
                # 没找到不再回池（已试完整条链）
                results.append((idx, result, "ok"))
            elif result.is_found():
                if not result.standard_number:
                    result.standard_number = target
                result = self._verify_adoption(result)
                # 查询结果始终写入缓存（不受 use_cache 控制）
                if getattr(result, 'match_status', '') == 'exact':
                    self._cache.put(result)
                score = MATCH_SCORE.get(getattr(result, 'match_status', ''), 0)
                if score >= 100:
                    logger.info(f"查询 [{target_display}] [OK]{result.source_site}({result.match_status}) tried={'→'.join(tried)}")
                    results.append((idx, result, "ok"))
                else:
                    logger.info(f"查询 [{target_display}] [LO]{result.source_site}({result.match_status}={score}) tried={'→'.join(tried)} 未达100分回池")
                    results.append((idx, result, "retry"))
            else:
                logger.info(f"查询 [{target_display}] [NG]{result.source_site}({getattr(result, 'match_status', 'err')}) tried={'→'.join(tried)}")
                results.append((idx, result, "ok"))

            if result_callback and result.is_found():
                result_callback(idx, result)
            if results[-1][2] == "ok":
                progress_callback()

            # 查询间隔（含随机抖动），降低被站点限流的概率
            if self._query_interval:
                import random
                delay = random.uniform(*self._query_interval)
                time.sleep(delay)

        return results

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

    def _plan_batch(self, parsed_list: List[tuple],
                    preferred_site: str = "") -> Dict[str, List[Tuple[int, tuple]]]:
        """按标准类型、站点覆盖、配额、冷却状态综合分配。

        逐条遍历，每条标准找到覆盖该类型的第一个可用站点（有配额+未冷却）。
        preferred_site 非空时置顶该站点。

        Returns:
            {site_name: [(index, (logical_code, number, year, std_name, part)), ...]}
        """
        plan: Dict[str, List[Tuple[int, tuple]]] = {}
        if not parsed_list:
            return plan

        for idx, item in enumerate(parsed_list):
            logical_code = item[0]
            candidates = self._get_priority(logical_code)
            # preferred_site 置顶
            if preferred_site and preferred_site in self._adapter_map:
                candidates = [preferred_site] + [c for c in candidates if c != preferred_site]

            assigned = False
            for site_name in candidates:
                if site_name not in self._adapter_map:
                    continue
                # 冷却中的站点已在 _get_priority 中过滤，此处仅检查配额
                if self._quota and self._quota.get_search_remaining(site_name) <= 0:
                    continue
                # 分配到此站点
                plan.setdefault(site_name, []).append((idx, item))
                assigned = True
                break

            if not assigned:
                logger.warning(
                    f"无可用站点: {logical_code} {item[1]}-{item[2]}")

        return plan

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
    # csres 日配额
    _CSRES_LIMIT = 40
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
            # 从 GB 和行业各取一半
            pool = gb_items[:self._CSRES_LIMIT // 2] + industry_items[:self._CSRES_LIMIT // 2]
            for idx, item in pool:
                if csres_failures[0] >= self._CSRES_CIRCUIT_BREAK:
                    break
                try:
                    result = adapter.query_with_strategy(
                        item[0], item[1], item[2], item[3], item[4])
                    if result:
                        result.source_site = "csres"
                        csres_results[idx] = result
                        csres_failures[0] = 0
                    else:
                        csres_failures[0] += 1
                except Exception:
                    csres_failures[0] += 1
                delay = _random.uniform(5, 10)
                _time.sleep(delay)

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
                        logger.info("[COOLDOWN] site=%s triggered_by=%s_bucket",
                                   primary_site, primary_site)
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

        # ── 7. 临时桶：链迭代 ──
        temp_cooldown_skips = 0
        if all_overflow:
            # 按剩余站点数升序
            all_overflow.sort(key=lambda x: len(self._build_chain_for_item(x[1])))

            for idx, item in all_overflow:
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

        # ── 8. 按原始顺序组装 ──
        return [results.get(i, QueryResult(
            standard_number=f"{parsed_list[i][0]} {parsed_list[i][1]}-{parsed_list[i][2]}",
            error_message="查询未完成", source_site=""))
            for i in range(n)]
