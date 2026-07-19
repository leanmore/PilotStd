# docker/api/logs.py — 应用日志读取 API（供前端日志栏 + 压测远端取回使用）
import os
import re

from fastapi import Depends
from fastapi.responses import FileResponse
from fastapi.routing import APIRouter

from pilotstd.core.logger import _get_log_dir

from ..auth import require_admin

router = APIRouter(tags=["logs"])

# 日志文件路径（LoggerManager 写入的 app.log）
_LOG_PATH = os.path.join(_get_log_dir(), "app.log")

# 日志时间戳正则：MM-DD HH:MM:SS
_TIMESTAMP_PATTERN = re.compile(r"^(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})")


def _extract_timestamp(line: str) -> str | None:
    """从日志行提取时间戳 'MM-DD HH:MM:SS'，失败返回 None。"""
    m = _TIMESTAMP_PATTERN.match(line)
    if m:
        return m.group(1)
    # 兼容 ISO 格式 2026-07-19T10:30:00
    m2 = re.match(r"^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})", line)
    return m2.group(1) if m2 else None


@router.get("/api/logs")
def get_logs(tail: int = 50, since: str = ""):
    """返回日志行。支持增量模式。

    - since 为空：返回最近 tail 条日志（首次加载）
    - since 有值：从文件末尾向前搜索 since 对应的位置，仅返回增量行
    - tail: 增量模式下保护上限，默认 50

    返回格式: {lines, total, lastTimestamp}
    """
    if not os.path.exists(_LOG_PATH):
        return {"lines": [], "path": _LOG_PATH, "note": "日志文件尚未生成"}

    try:
        with open(_LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
    except OSError as e:
        return {"lines": [f"[日志读取失败] {e}"], "path": _LOG_PATH}

    total = len(all_lines)

    if not since:
        # 首次加载：返回最近 tail 条
        lines = all_lines[-tail:] if tail > 0 and total > tail else all_lines
        lines = [line.rstrip("\n") for line in lines]
        last_ts = _extract_timestamp(lines[-1]) if lines else None
        return {
            "lines": lines,
            "total": total,
            "lastTimestamp": last_ts,
        }

    # 增量模式：从末尾向前找 since 对应位置，返回之后的新行
    # 从文件末尾开始扫描比全量 readlines 后 filter 更高效
    start_idx = None
    for i in range(total - 1, -1, -1):
        ts = _extract_timestamp(all_lines[i])
        if ts and ts <= since:
            start_idx = i + 1
            break

    if start_idx is None:
        # 未匹配到 since，可能日志已轮转，返回最近 tail 条
        lines = all_lines[-tail:] if tail > 0 and total > tail else all_lines
    else:
        lines = all_lines[start_idx:]
        # 增量过多时截断保护（避免日志洪峰撑爆前端）
        if tail > 0 and len(lines) > tail:
            lines = lines[-tail:]

    lines = [line.rstrip("\n") for line in lines]
    last_ts = _extract_timestamp(lines[-1]) if lines else None
    return {
        "lines": lines,
        "total": total,
        "lastTimestamp": last_ts,
    }


@router.get("/api/admin/logs/app")
def get_app_log_raw(username: str = Depends(require_admin)):
    """返回完整 app.log 文件内容（管理员权限，供压测驱动器远端取回）。

    返回纯文本，Content-Type: text/plain; charset=utf-8。
    日志文件不存在时返回 404。
    """
    from fastapi import HTTPException

    if not os.path.exists(_LOG_PATH):
        raise HTTPException(status_code=404, detail="日志文件不存在")
    return FileResponse(
        _LOG_PATH,
        media_type="text/plain; charset=utf-8",
        filename="app.log",
    )


@router.delete("/api/admin/logs")
def clear_logs(
    before_hours: int = 24,
    username: str = Depends(require_admin),
):
    """清除 before_hours 小时前的日志条目（仅管理员）。

    默认 24 小时，传入 before_hours=0 表示清空全部。
    返回删除的日志行数。
    """
    if not os.path.exists(_LOG_PATH):
        return {"ok": True, "deleted": 0, "note": "日志文件不存在"}

    try:
        with open(_LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        total = len(lines)
        if before_hours <= 0:
            # 清空全部
            with open(_LOG_PATH, "w", encoding="utf-8") as f:
                f.write("")
            return {"ok": True, "deleted": total}

        # 保留最近 before_hours 小时内的日志
        from datetime import datetime, timedelta

        cutoff = datetime.now() - timedelta(hours=before_hours)
        kept = []
        deleted = 0
        for line in lines:
            # 日志格式: "MM-DD HH:MM:SS [LEVEL] TAG message"
            try:
                ts_str = line[:14]  # "MM-DD HH:MM:SS"
                # 补齐年份（假设当前年）
                log_time = datetime.strptime(f"{datetime.now().year}-{ts_str}", "%Y-%m-%d %H:%M:%S")
                if log_time >= cutoff:
                    kept.append(line)
                else:
                    deleted += 1
            except (ValueError, IndexError):
                # 无法解析的行保留
                kept.append(line)

        with open(_LOG_PATH, "w", encoding="utf-8") as f:
            f.writelines(kept)

        return {"ok": True, "deleted": deleted, "kept": len(kept)}
    except OSError as e:
        from fastapi import HTTPException

        raise HTTPException(status_code=500, detail=f"清理日志失败: {e}")
