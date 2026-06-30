# pilotstd/query/engine/__init__.py
# 查询引擎：每日配额管理、任务分割、站点轮转冷却、采标校验
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

from ._batch import BatchMixin
from ._constants import (
    CODE_ROUTES,
    FOREIGN_ROUTE,
    INDUSTRY_ROUTE,
    PROD_PRIORITY,
    PROGRESS_TAG,
)
from ._core import QueryEngineCore
from ._routing import RoutingMixin
from ._single import SingleMixin


class QueryEngine(QueryEngineCore, RoutingMixin, SingleMixin, BatchMixin):
    """查询引擎：缓存优先 + 多适配器回退 + 配额感知。

    典型用法:
        engine = QueryEngine(adapters=[...], cache=cache)
        result = engine.query_standards([("GB/T", 19001, 2020, "", None, "")])
        results = engine.query_standards(items, use_parallel=True)
    """


__all__ = [
    "QueryEngine",
    "PROGRESS_TAG",
    "PROD_PRIORITY",
    "FOREIGN_ROUTE",
    "CODE_ROUTES",
    "INDUSTRY_ROUTE",
]
