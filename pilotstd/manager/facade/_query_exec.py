# pilotstd/manager/facade/_query_exec.py
# ⚠️ 已迁移至 _query_subsystem.py — QuerySubsystem 组合类
# 原 _QueryExecMixin 的所有方法已迁入 QuerySubsystem。
# 此文件将在确认无外部 import 后删除。

# 保留类名以避免现有 import 立即中断
from ._query_subsystem import QuerySubsystem


class _QueryExecMixin:
    """⚠️ DEPRECATED: 已迁移至 QuerySubsystem。仅保留类名兼容。"""
    pass
