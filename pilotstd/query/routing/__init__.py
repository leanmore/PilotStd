# 模块：项目/查询/路由/____脚本
# 阶段3.1:路由评分器包

from .scorer import ScoreResult, get_priority_chain, score_adapter

__all__ = ["get_priority_chain", "score_adapter", "ScoreResult"]
