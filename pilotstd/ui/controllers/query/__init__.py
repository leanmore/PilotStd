# pilotstd/ui/controllers/query/__init__.py
# 查询模块 — 从 query_mixin.py 拆分为 3 个子模块

from .mixin import QueryCoreMethods
from .pending import QueryPendingMethods
from .summary import QuerySummaryMethods


class QueryMixin(QueryCoreMethods, QuerySummaryMethods, QueryPendingMethods):
    """查询相关方法混入类，组合自 core + summary + pending 子模块。"""
