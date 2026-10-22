# 模块：公告源站标准号纠错（可维护列表）
"""按“标准名称反查权威标准号”修正源站已知录入错误。

兜底维护列表：
- 内置：`pilotstd/announcement/data/source_code_corrections.json`
- 运行时覆盖：`data/source_code_corrections.json`
- 环境变量：`PILOTSTD_CODE_CORRECTIONS=/path/to/file.json`
- 格式：`{"entries": [{source_site, announce_no, std_name, wrong_code, corrected_code, reason, authority}]}`

只对指定公告 + 精确名称（可再限定 wrong_code）生效。
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_BUNDLED_PATH = Path(__file__).with_name("data") / "source_code_corrections.json"
_cache: dict[tuple[str, str, str, str], str] | None = None


def _norm_name(name: str) -> str:
    """去掉空白和书名号，避免 PDF/HTML 换行导致匹配失败。"""
    return re.sub(r"[\s《》]+", "", name or "")


def _norm_code(code: str) -> str:
    """标准号只比较字母数字，忽略空格与大小写差异。"""
    return re.sub(r"\s+", "", code or "").upper()


def _load_file(path: Path) -> list[dict[str, Any]]:
    """读取单个维护列表文件；格式错误只告警，不阻断公告解析。"""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("correction list read failed %s: %s", path, exc)
        return []
    entries = raw.get("entries", []) if isinstance(raw, dict) else []
    if not isinstance(entries, list):
        return []
    return [e for e in entries if isinstance(e, dict)]


def _candidate_paths() -> list[Path]:
    """内置列表 + 环境变量指定的外部维护列表（后者覆盖前者）。"""
    paths = [_BUNDLED_PATH]
    env = os.environ.get("PILOTSTD_CODE_CORRECTIONS", "")
    if env:
        paths.append(Path(env))
    return paths


def _build_cache() -> dict[tuple[str, str, str, str], str]:
    """把多份文件合并成 (站点,公告号,名称,错误号) -> 正确号 的索引。"""
    cache: dict[tuple[str, str, str, str], str] = {}
    # 后加载的文件覆盖先加载的内置条目，便于现场热修维护列表
    for path in _candidate_paths():
        if not path.exists():
            continue
        for entry in _load_file(path):
            site = str(entry.get("source_site", ""))
            anno = str(entry.get("announce_no", ""))
            name = _norm_name(str(entry.get("std_name", "")))
            corrected = str(entry.get("corrected_code", ""))
            if not (site and anno and name and corrected):
                logger.warning("correction entry incomplete, ignored: %s", entry)
                continue
            wrong = _norm_code(str(entry.get("wrong_code", "")))
            cache[(site, anno, name, wrong)] = corrected
    return cache


def reload_corrections() -> None:
    """清空缓存，供测试/运行时维护列表更新后调用。"""
    global _cache
    _cache = None


def correct_std_code(source_site: str, announce_no: str, std_name: str, std_code: str) -> str:
    """命中维护列表时返回权威标准号，否则原样返回。"""
    global _cache
    if _cache is None:
        _cache = _build_cache()
    name = _norm_name(std_name)
    code = _norm_code(std_code)
    exact = _cache.get((source_site, announce_no, name, code))
    if exact:
        return exact
    # wrong_code 为空表示该公告下同名条目一律修正；这是维护列表的兜底匹配
    return _cache.get((source_site, announce_no, name, ""), std_code)
