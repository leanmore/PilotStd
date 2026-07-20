# pilotstd/core/db/_migration_checksum.py
# 迁移脚本 checksum 校验 — 从 database.py 拆分

import hashlib
import inspect
import logging
from typing import Any

from ._constants import MIGRATIONS, DatabaseError

logr = logging.getLogger("pilotstd.db")


def _is_inside_string(line: str, pos: int) -> bool:
    """判断给定位置是否在字符串字面量内部。用于避免误删字符串内的 # 字符。"""
    in_single = False
    in_double = False
    i = 0
    while i < pos:
        ch = line[i]
        # 跳过转义字符，避免 \" 或 \' 干扰状态判断
        if ch == "\\" and i + 1 < pos:
            i += 2
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "'" and not in_double:
            in_single = not in_single
        i += 1
    return in_single or in_double


def compute_checksum(fn: Any) -> str:
    """计算迁移函数的源码 checksum（原始，含注释和空行）。"""
    try:
        source = inspect.getsource(fn)
    except (OSError, TypeError):
        source = str(fn.__code__.co_code) if hasattr(fn, "__code__") else repr(fn)
    return hashlib.sha256(source.encode()).hexdigest()


def norm_source(source: str) -> str:
    """剥离 Python 源码中的注释和空行，只保留逻辑行。"""
    lines = []
    for line in source.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        # 处理行内注释：找到 # 位置并去除，跳过字符串内的 # 符号
        comment_pos = stripped.find("#")
        if comment_pos > 0 and not _is_inside_string(stripped, comment_pos):
            code_part = stripped[:comment_pos].strip()
            if code_part:
                lines.append(code_part)
        else:
            lines.append(stripped)
    return "\n".join(lines)


def norm_checksum(fn: Any) -> str:
    """计算迁移函数的标准化 checksum（剥离注释和空行后）。"""
    try:
        source = inspect.getsource(fn)
    except (OSError, TypeError):
        source = str(fn.__code__.co_code) if hasattr(fn, "__code__") else repr(fn)
    normalized = norm_source(source)
    return hashlib.sha256(normalized.encode()).hexdigest()


def verify_migration_checksums(db: Any) -> None:
    """验证已执行迁移的脚本 checksum，支持注释/空行变更的自愈。

    三级比较策略：
    1. 存储值 == 标准化值 → 直接通过
    2. 原始值 != 标准化值 → 仅注释/空行变化，强制更新
    3. 原始值 == 标准化值 但存储值 != 标准化值 → 真实 DDL 变更，抛错
    """
    current = db.schema_version
    for v in sorted(MIGRATIONS.keys()):
        if v > current:
            continue
        stored = db.fetchone("SELECT checksum FROM _schema_version WHERE version=?", (v,))
        if not stored or not stored["checksum"]:
            continue
        stored_checksum = stored["checksum"]

        # 先比较标准化 checksum（剥离注释后）
        norm_expected = norm_checksum(MIGRATIONS[v])
        if norm_expected == stored_checksum:
            continue

        # 标准化不等 → 检查原始 checksum，判断是否为仅注释变化
        raw_expected = compute_checksum(MIGRATIONS[v])
        if raw_expected != norm_expected:
            logr.warning(
                "迁移 v%d 的 checksum 已自动修复（仅注释/空行变化）。存储值: %s → 标准化值: %s…",
                v,
                (stored_checksum or "None")[:16],
                norm_expected[:16],
            )
            db.execute(
                "UPDATE _schema_version SET checksum=? WHERE version=?",
                (norm_expected, v),
            )
            continue

        logr.error(
            "迁移 v%d 的脚本逻辑已变更，checksum 不匹配。存储: %s…, 标准化: %s…",
            v,
            (stored_checksum or "None")[:16],
            norm_expected[:16],
        )
        raise DatabaseError(f"迁移 v{v} 的脚本逻辑已变更，checksum 不匹配")
