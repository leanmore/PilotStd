# pilotstd/scan/parser/_utils.py
# 标准解析器工具函数兼容模块
"""兼容层 — 保留 UtilsMixin 符号，委托给 ParserCore。

外部代码 `from pilotstd.scan.parser._utils import UtilsMixin` 仍可正常工作。
"""

from ._core import ParserCore as UtilsMixin  # noqa: F401 — 兼容导入
