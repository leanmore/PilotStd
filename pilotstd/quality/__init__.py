# 模块：pilotstd/quality/__init__.py
# 质量检查框架——在 push 前检测陈旧引用、死代码等质量问题

from .runner import QualityRunner

__all__ = ["QualityRunner"]
