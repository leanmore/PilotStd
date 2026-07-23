# pilotstd/core/download_utils.py
# Q24: 下载导入共享工具 — 文本解析 + 标准号校验 + 去重
# Web API 与桌面 GUI 共用

from __future__ import annotations

import csv
import io
import logging
from typing import Any

from .std_utils import parse_std_number

logger = logging.getLogger(__name__)


def parse_download_sources(text: str | None = None) -> dict[str, Any]:
    """解析下载输入文本，返回结构化结果。

    Args:
        text: 纯文本内容。CSV 格式自动识别（首行含 standard_number 列），
              否则按每行一个标准号处理。

    Returns:
        {
            "valid": list[str],
            "invalid": list[str],
            "duplicates": list[str],
        }
    """
    raw_numbers: list[str] = []

    if not text or not text.strip():
        return {"valid": [], "invalid": [], "duplicates": []}

    # CSV 自动识别：首行含 standard_number 列名
    if _looks_like_csv(text):
        raw_numbers = _parse_csv_content(text)
    else:
        raw_numbers = [line.strip() for line in text.splitlines() if line.strip()]

    # 校验 + 去重
    valid: list[str] = []
    invalid: list[str] = []
    seen: set[str] = set()
    duplicates: list[str] = []

    for num in raw_numbers:
        if not num:
            continue
        if not parse_std_number(num):
            invalid.append(num)
        elif num in seen:
            duplicates.append(num)
        else:
            seen.add(num)
            valid.append(num)

    return {"valid": valid, "invalid": invalid, "duplicates": duplicates}


def _looks_like_csv(text: str) -> bool:
    """启发式判断文本是否包含 CSV 表头。"""
    first_line = text.splitlines()[0] if text else ""
    return "standard_number" in first_line.lower() and ("," in first_line or "\t" in first_line)


def _parse_csv_content(text: str) -> list[str]:
    """从 CSV 文本中提取 standard_number 列。"""
    try:
        reader = csv.DictReader(io.StringIO(text))
        rows: list[str] = []
        for row in reader:
            val = row.get("standard_number", "").strip()
            if val:
                rows.append(val)
        return rows
    except Exception:
        logger.debug("CSV 解析失败", exc_info=True)
        return []
