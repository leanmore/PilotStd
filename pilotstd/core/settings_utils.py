# 模块：pilotstd/core/settings_utils.py
"""Settings pure utilities — zero GUI/I/O dependencies."""


def sanitize_setting_value(raw: str) -> str:
    """清洗设置输入值：去除首尾空白，保留内部空格。"""
    return raw.strip()
