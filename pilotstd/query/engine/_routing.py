# pilotstd/query/engine/_routing.py
# mypy: disable-error-code="no-any-return"
"""查询引擎路由处理器 — 优先级计算、配额分配、站点轮转、桶分片逻辑。

组合模式重构：RoutingMixin → RoutingHandler，依赖通过 EngineCore 注入。
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any, List, Optional, Tuple

from ..adapters.base import BaseAdapter
from ..search_strategy import ADAPTER_TYPE_MAP
from ._constants import CODE_ROUTES, FOREIGN_ROUTE, INDUSTRY_ROUTE, PROD_PRIORITY

if TYPE_CHECKING:
    from ._core_types import EngineCore

logger = logging.getLogger(__name__)


class RoutingHandler:
    """路由处理器 — 提供优先级计算、配额感知分配、站点选择方法。

    替代原 RoutingMixin，所有依赖通过 EngineCore 访问。
    """

    def __init__(self, core: "EngineCore") -> None:
        self._core = core

    # ── 路由基础 ──

    def _resolve_base_route(self, logical_code: str) -> list[str]:
        """按标准代号/类型确定基础路由链。返回站点名称列表。"""
        if logical_code in CODE_ROUTES:
            return list(CODE_ROUTES[logical_code])  # 硬编码路由：按代号直接映射
        if logical_code and re.match(r"^DB\d{2,4}(?:/T)?$", logical_code):
            return ["dbba", "njbz365"]  # 地方标准：dbba 主站 + njbz365 兜底

        from ...core.std_utils import classify_std_code

        std_type = classify_std_code(logical_code)
        type_route = ADAPTER_TYPE_MAP.get(std_type)
        if type_route:
            explicit_chain: Any = type_route.get("chain")
            if explicit_chain:
                base = list(explicit_chain)
            else:
                primary = str(type_route.get("primary", ""))
                fallback = str(type_route.get("fallback", ""))
                base = [primary] if primary else []
                extras = [s for s in PROD_PRIORITY if s not in base and s != fallback]
                base.extend(extras[:2])
                if fallback and fallback not in base:
                    base.append(fallback)
            logger.info("[ROUTE] 代号=%s 类型=%s 路由=%s", logical_code, std_type, "→".join(base))
            return base

        if logical_code:
            from ...scan.parser import CAC_PREFIXES, FOREIGN_CODE_SET, ITU_CODES

            # 三层国外标准检测：前缀白名单 → ITU 系列 → CAC 民航类
            code_no_space = logical_code.upper().replace(" ", "")
            is_foreign = any(code_no_space.startswith(fc.upper().replace(" ", "")) for fc in FOREIGN_CODE_SET)
            if not is_foreign:
                is_foreign = any(logical_code.upper().startswith(itu.upper()) for itu in ITU_CODES)
            if not is_foreign:
                is_foreign = any(logical_code.upper().startswith(cac.upper()) for cac in CAC_PREFIXES)
            if is_foreign:
                return list(FOREIGN_ROUTE)  # 国外标准路由
            if len(logical_code) <= 4:
                return list(INDUSTRY_ROUTE)  # 短代号 → 行业标准路由
            return list(FOREIGN_ROUTE)  # 未识别代号 → 按国外标准处理

        return list(PROD_PRIORITY)

    def _apply_site_order(self, base: list[str]) -> list[str]:
        """用户自定义 site_order 置顶叠加。"""
        site_order = self._core.site_order
        if site_order:
            return list(site_order) + [s for s in base if s not in site_order]
        return base

    def _filter_available_adapters(self, base: list[str]) -> list[str]:
        """站点轮转过滤（冷却跳过）+ 仅保留已注册适配器 + 回退逻辑。"""
        rotator = self._core.rotator
        adapter_map = self._core.adapter_map
        adapters = self._core.adapters

        if rotator:
            base = rotator.get_available(base)

        known = set(adapter_map.keys())
        pri = [n for n in base if n in known]
        if not pri and known:
            pri = [a.site_name for a in adapters]
            if base == FOREIGN_ROUTE:
                pri = [n for n in pri if n not in ("std_gov", "hbba")]
        return pri

    # ── 优先级链构建 ──

    def _get_priority(self, logical_code: str = "", preferred_site: str | None = None) -> list[str]:
        """按标准代号返回适配器优先级链。

        优先级决定因素（按顺序）：
          0. 用户指定站点 → 直接使用，不走自动路由
          1. 标准代号匹配（CODE_ROUTES）
          2. 代号长度 ≤4 且非 ISO/IEC → 行业标准路由
          3. 其他 → 国外标准路由或默认全链
          4. 用户自定义 site_order 置顶
          5. 站点轮转过滤（冷却中跳过）
          6. 过滤后为空则回退到全部已知适配器
        """
        if preferred_site:
            logger.info("[ROUTE] 用户指定站点=%s，跳过自动路由", preferred_site)
            return [preferred_site]
        base = self._resolve_base_route(logical_code)
        base = self._apply_site_order(base)
        return self._filter_available_adapters(base)

    # ── 配额与桶 █

    def plan_batch(self, total: int, logical_code: str = "") -> List[Tuple[str, int]]:
        """按配额预估分配方案（供 UI 展示）。返回 [(site_name, count), ...]"""
        plan = []
        remaining = total
        priority = self._get_priority(logical_code)
        quota = self._core.quota
        if quota is None:
            return [(priority[0], total)] if priority else []
        for name in priority:
            if remaining <= 0:
                break
            quota_remaining = quota.get_search_remaining(name)
            if quota_remaining <= 0:
                continue
            take = min(remaining, quota_remaining)
            plan.append((name, take))
            remaining -= take
        return plan

    def get_quota_info(self) -> dict[str, int]:
        """返回各站点配额信息（供 UI 弹窗展示）。"""
        quota = self._core.quota
        if quota:
            return quota.get_all_remaining()
        return {}

    def get_adapter(self, name: str) -> Optional[BaseAdapter]:
        """获取指定站点适配器（供 PendingQueryDialog 使用）。"""
        return self._core.adapter_map.get(name)

    def get_site_cooldown(self, name: str) -> float:
        """返回指定站点剩余冷却秒数，0=不在冷却中。"""
        rotator = self._core.rotator
        if rotator:
            return rotator.get_cooldown_remaining(name)
        return 0.0

    def get_all_sites(self) -> List[str]:
        """返回所有已注册站点名称。"""
        return list(self._core.adapter_map.keys())

    def _bucket_key(self, logical_code: str, preferred_site: str | None = None) -> str:
        """按 _get_priority 第一条（主站点）确定桶标识。"""
        priority = self._get_priority(logical_code, preferred_site)
        return priority[0] if priority else "other"

    def _build_chain_for_item(
        self,
        item: Tuple[str, int, int, str, Optional[int], str],
        preferred_site: str | None = None,
    ) -> list[str]:
        """返回条目对应的完整优先级链（不含 csres）。"""
        logical_code = item[0]
        chain = self._get_priority(logical_code, preferred_site)
        return [s for s in chain if s != "csres"]
