"""全局聚合搜索（P0 后端编排）——一次查询跨站并行检索、合并去重、按置信度排序。

设计要点（见 `docs/plans/2026-11-26-global-aggregate-search-plan.md`）：
1. **默认关闭**：`query.aggregate.enabled=false`，不改变现有单站查询链路；
2. **并发闸门**：线程池 + 全局并发上限（默认 4）+ 单站超时（默认 8s）+ 总预算（默认 12s），
   单站失败/超时**不影响整体**（结果里带 `errors` 与逐站耗时）；
3. **按站限速**：同一站点两次调用间隔下限（默认 0.5s），避免聚合放大触发风控；
4. **结果合并**：按标准号归一（`parse_std_number`）去重，同号多站合并为一条并记录 `sources`；
   置信度：查询可解析为编号且命中编号一致 = `exact`，其余 = `keyword`；
5. **可注入**：适配器/路由/配置均可注入（测试与矩阵脚本复用，避免真实网络）。

本模块是纯编排层，不实现站点解析；站点解析仍由各适配器 `_search_candidates()` 负责。
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from typing import Any, Callable

from pilotstd.core.std_utils import parse_std_number

# 实现分层：候选站点选择（路由/注册顺序）→ 并发执行（线程池 + 超时）→ 合并（归一/去重/排序）。
# 每一层都可注入替身：`routing`（站点顺序）、`adapters`/`adapter_getter`（检索实现）、`config`（开关与参数）。
logger = logging.getLogger(__name__)

# 配置键（`pilotstd/core/config/defaults.py` 同步登记；全部有默认值，缺配置也能工作）
CONFIG_ENABLED = "query.aggregate.enabled"
CONFIG_MAX_CONCURRENCY = "query.aggregate.max_concurrency"
CONFIG_PER_SITE_TIMEOUT = "query.aggregate.per_site_timeout"
CONFIG_MAX_SITES = "query.aggregate.max_sites"
CONFIG_MIN_INTERVAL = "query.aggregate.per_site_min_interval"
CONFIG_TOTAL_BUDGET = "query.aggregate.total_budget"

_DEFAULTS: dict[str, Any] = {
    CONFIG_ENABLED: False,
    CONFIG_MAX_CONCURRENCY: 4,
    CONFIG_PER_SITE_TIMEOUT: 8.0,
    CONFIG_MAX_SITES: 6,
    CONFIG_MIN_INTERVAL: 0.5,
    CONFIG_TOTAL_BUDGET: 12.0,
}


def _to_float(value: Any, default: float) -> float:
    """配置值转 float；非法值回退默认（配置来自 DB/JSON，不信任类型）。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int) -> int:
    """配置值转 int；非法值回退默认。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass
class SiteOutcome:
    """单站检索结果摘要（用于可观测性与 UI 的失败可见）。"""

    site: str
    ok: bool
    elapsed_ms: int
    count: int = 0
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转可 JSON 序列化字典。"""
        return {
            "site": self.site,
            "ok": self.ok,
            "elapsed_ms": self.elapsed_ms,
            "count": self.count,
            "error": self.error,
        }


@dataclass
class AggregateItem:
    """聚合后的单条标准（同号合并多站来源）。"""

    standard_number: str
    standard_name: str = ""
    status: str = ""
    status_key: str = ""
    confidence: str = "keyword"
    sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转可 JSON 序列化字典。"""
        return {
            "standard_number": self.standard_number,
            "standard_name": self.standard_name,
            "status": self.status,
            "status_key": self.status_key,
            "confidence": self.confidence,
            "sources": list(self.sources),
        }


@dataclass
class AggregateResult:
    """聚合查询结果：是否启用 + 合并条目 + 逐站摘要 + 总耗时。"""

    query: str
    enabled: bool
    items: list[AggregateItem] = field(default_factory=list)
    sites: list[SiteOutcome] = field(default_factory=list)
    elapsed_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        """转可 JSON 序列化字典（API 响应直接复用）。"""
        return {
            "query": self.query,
            "enabled": self.enabled,
            "elapsed_ms": self.elapsed_ms,
            "items": [item.to_dict() for item in self.items],
            "sites": [site.to_dict() for site in self.sites],
        }


def _dedupe_key(standard_number: str) -> str:
    """标准号归一键：解析成功用结构化字段，失败回退去空白大写原文。"""
    parsed = parse_std_number(standard_number or "")
    if parsed and parsed.get("code") and parsed.get("number") is not None:
        return "|".join(
            str(parsed.get(name) or "")
            for name in ("code", "number", "part", "num_prefix", "num_suffix", "year")
        )
    return "".join(str(standard_number or "").upper().split())


def _status_key_of(result: Any) -> str:
    """取结果的状态英文键（适配器可能只给中文 status，此处转为键）。"""
    from pilotstd.core.status import STATUS_EN_KEYS, normalize_status

    status = str(getattr(result, "status", "") or "")
    normalized = normalize_status(status) if status else ""
    return STATUS_EN_KEYS.get(normalized, STATUS_EN_KEYS.get(status, "unknown"))


class AggregationService:
    """聚合搜索编排器：候选站点选择 → 并行检索 → 合并去重 → 排序。"""

    def __init__(
        self,
        adapters: list[Any] | None = None,
        routing: Any = None,
        config: Any = None,
        adapter_getter: Callable[[str], Any] | None = None,
        site_order: list[str] | None = None,
    ) -> None:
        self._adapter_getter = adapter_getter
        self._adapters: dict[str, Any] = {}
        for adapter in adapters or []:
            site = str(getattr(adapter, "site_name", "") or "")
            if site:
                self._adapters[site] = adapter
        self._routing = routing
        self._config = config
        self._site_order = list(site_order or [])
        self._interval_lock = threading.Lock()
        self._last_call: dict[str, float] = {}

    # ── 配置 ──

    def _cfg(self, key: str) -> Any:
        """读配置项：无配置桩或桩异常时回退内置默认值（聚合不得因配置故障不可用）。"""
        if self._config is None:
            return _DEFAULTS[key]
        try:
            return self._config.get(key, _DEFAULTS[key])
        except Exception:  # noqa: BLE001 - 配置桩异常不得影响查询
            return _DEFAULTS[key]

    @property
    def enabled(self) -> bool:
        """当前是否启用聚合（默认关闭，不影响单站查询）。"""
        return bool(self._cfg(CONFIG_ENABLED))

    # ── 站点选择 ──

    def _candidate_sites(self, query: str, max_sites: int | None = None) -> list[str]:
        """候选站点：优先路由链顺序；无路由则按注册顺序；最后按 `max_sites` 截断。"""
        limit = max(1, int(max_sites) if max_sites else _to_int(self._cfg(CONFIG_MAX_SITES), 6))
        sites: list[str] = []
        if self._routing is not None:
            try:
                chain = self._routing.get_route_chain(query)
                for site in getattr(chain, "sites", []):
                    name = str(getattr(site, "site_name", site) or "")
                    if name:
                        sites.append(name)
            except Exception as exc:  # noqa: BLE001 - 路由故障降级为注册顺序
                logger.warning("aggregate routing failed, fallback to site order: %s", exc)
        if not sites:
            sites = [s for s in self._site_order if s] or list(self._adapters)
        # 去重保序
        unique: list[str] = []
        for name in sites:
            if name not in unique:
                unique.append(name)
        return unique[:limit]

    def _adapter_for(self, site: str) -> Any:
        """取站点适配器（优先注入表，其次工厂）。"""
        if site in self._adapters:
            return self._adapters[site]
        if self._adapter_getter is not None:
            try:
                return self._adapter_getter(site)
            except Exception as exc:  # noqa: BLE001
                logger.warning("aggregate adapter %s unavailable: %s", site, exc)
                return None
        return None

    def _throttle(self, site: str) -> None:
        """按站最小调用间隔限速（同一进程内重复调用场景；单次查询通常不触发）。"""
        interval = max(0.0, _to_float(self._cfg(CONFIG_MIN_INTERVAL), 0.5))
        if interval <= 0:
            return
        with self._interval_lock:
            last = self._last_call.get(site, 0.0)
            wait_for = last + interval - time.monotonic()
            if wait_for > 0:
                time.sleep(wait_for)
            self._last_call[site] = time.monotonic()

    # ── 单站检索 ──

    def _search_site(self, site: str, query: str) -> tuple[list[Any], SiteOutcome]:
        """在单站检索关键词；异常/超时由调用方兜底，本方法不吞错（返回 outcome）。"""
        adapter = self._adapter_for(site)
        started = time.monotonic()
        if adapter is None:
            return [], SiteOutcome(site=site, ok=False, elapsed_ms=0, error="adapter unavailable")
        try:
            self._throttle(site)
            rows = adapter._search_candidates(query) or []
            elapsed = int((time.monotonic() - started) * 1000)
            return list(rows), SiteOutcome(site=site, ok=True, elapsed_ms=elapsed, count=len(rows))
        except Exception as exc:  # noqa: BLE001 - 单站失败隔离，不影响整体
            elapsed = int((time.monotonic() - started) * 1000)
            logger.warning("aggregate site %s failed: %s", site, exc)
            return [], SiteOutcome(site=site, ok=False, elapsed_ms=elapsed, error=type(exc).__name__)

    # ── 合并 ──

    @staticmethod
    def _confidence(query: str, standard_number: str) -> str:
        """置信度：查询可解析且与结果编号一致 = exact，否则 keyword。"""
        parsed = parse_std_number(query or "")
        if not parsed or not parsed.get("code"):
            return "keyword"
        target = "|".join(
            str(parsed.get(name) or "")
            for name in ("code", "number", "part", "num_prefix", "num_suffix", "year")
        )
        return "exact" if _dedupe_key(standard_number) == target else "keyword"

    def _merge(
        self, query: str, batches: list[tuple[str, list[Any]]], site_rank: dict[str, int]
    ) -> list[AggregateItem]:
        """合并去重：同号多站合并 sources；精确命中优先排序。"""
        merged: dict[str, AggregateItem] = {}
        for site, rows in batches:
            for row in rows:
                if row is None or not getattr(row, "standard_number", ""):
                    continue
                if hasattr(row, "is_found") and not row.is_found():
                    continue
                key = _dedupe_key(str(row.standard_number))
                confidence = self._confidence(query, str(row.standard_number))
                item = merged.get(key)
                if item is None:
                    merged[key] = AggregateItem(
                        standard_number=str(row.standard_number).strip(),
                        standard_name=str(getattr(row, "standard_name", "") or ""),
                        status=str(getattr(row, "status", "") or ""),
                        status_key=_status_key_of(row),
                        confidence=confidence,
                        sources=[site],
                    )
                else:
                    if site not in item.sources:
                        item.sources.append(site)
                    if confidence == "exact":
                        item.confidence = "exact"
                    row_name = str(getattr(row, "standard_name", "") or "")
                    if not item.standard_name and row_name:
                        item.standard_name = row_name
        items = list(merged.values())
        # sources 按候选站点顺序排序（路由链顺序），保证同一查询结果稳定可断言
        for item in items:
            item.sources.sort(key=lambda name: site_rank.get(name, len(site_rank)))
        items.sort(key=lambda i: (0 if i.confidence == "exact" else 1, -len(i.sources), i.standard_number))
        return items

    # ── 入口 ──

    def search(self, query: str, max_sites: int | None = None) -> AggregateResult:
        """执行一次聚合检索（默认关闭时直接返回 `enabled=False`，不发任何网络请求）。"""
        query = str(query or "").strip()
        started = time.monotonic()
        if not self.enabled:
            return AggregateResult(query=query, enabled=False)
        sites = self._candidate_sites(query, max_sites)
        per_site_timeout = max(0.1, _to_float(self._cfg(CONFIG_PER_SITE_TIMEOUT), 8.0))
        total_budget = max(per_site_timeout, _to_float(self._cfg(CONFIG_TOTAL_BUDGET), 12.0))
        concurrency = min(max(1, _to_int(self._cfg(CONFIG_MAX_CONCURRENCY), 4)), max(1, len(sites)))

        outcomes: list[SiteOutcome] = []
        batches: list[tuple[str, list[Any]]] = []
        with ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="agg") as pool:
            futures: dict[Future[tuple[list[Any], SiteOutcome]], str] = {
                pool.submit(self._search_site, site, query): site for site in sites
            }
            done, pending = wait(futures, timeout=min(total_budget, per_site_timeout * 2))
            for future in done:
                rows, outcome = future.result()
                batches.append((outcome.site, rows))
                outcomes.append(outcome)
            for future in pending:
                future.cancel()
                site = futures[future]
                outcomes.append(
                    SiteOutcome(
                        site=site,
                        ok=False,
                        elapsed_ms=int(per_site_timeout * 1000),
                        error="timeout",
                    )
                )

        outcomes.sort(key=lambda o: o.site)
        # 合并顺序固定（按站点名）⇒ 同一查询多次调用时 sources[] 顺序稳定（API 契约可断言）
        batches.sort(key=lambda batch: batch[0])
        items = self._merge(query, batches, {name: idx for idx, name in enumerate(sites)})
        elapsed = int((time.monotonic() - started) * 1000)
        return AggregateResult(query=query, enabled=True, items=items, sites=outcomes, elapsed_ms=elapsed)
