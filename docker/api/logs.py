# 容器//脚本—应用日志读取接口（供前端日志栏+压测远端取回使用）
import os
import re
import time
from collections import deque
from datetime import datetime, timezone

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.routing import APIRouter

from pilotstd.core.logger import _get_log_dir

from ..auth import require_role

router = APIRouter(tags=["logs"])

# 日志文件路径（写入的.）
_LOG_PATH = os.path.join(_get_log_dir(), "app.log")

# 轮转日志文件名白名单：app.log 或 app.log.N（后缀为数字）
_ROTATED_NAME_RE = re.compile(r"^app\.log(\.\d+)?$")
# 行长度估算均值（字节/行），用于 lines_estimate 不实际计数
_AVG_LINE_BYTES = 200
# 列表缓存秒数
_LIST_CACHE_SECONDS = 60

# 轮转文件列表缓存（时间戳用单调时钟）
_list_cache: dict = {"ts": 0.0, "files": []}

# 日志时间戳正则：-::
_TIMESTAMP_PATTERN = re.compile(r"^(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})")


def _extract_timestamp(line: str) -> str | None:
    """从日志行提取时间戳 'MM-DD HH:MM:SS'，失败返回 None。"""
    m = _TIMESTAMP_PATTERN.match(line)
    if m:
        return m.group(1)
    # 兼容格式2026-07-1910:30:00
    m2 = re.match(r"^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})", line)
    return m2.group(1) if m2 else None


@router.get("/api/logs")
@require_role("admin")
def get_logs(request: Request, tail: int = 50, since: str = ""):
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
        # 首次加载：返回最近条
        lines = all_lines[-tail:] if tail > 0 and total > tail else all_lines
        lines = [line.rstrip("\n") for line in lines]
        last_ts = _extract_timestamp(lines[-1]) if lines else None
        return {
            "lines": lines,
            "total": total,
            "lastTimestamp": last_ts,
        }

    # 增量模式：从末尾向前找对应位置，返回之后的新行
    # 从文件末尾开始扫描比全量后更高效
    start_idx = None
    for i in range(total - 1, -1, -1):
        ts = _extract_timestamp(all_lines[i])
        if ts and ts <= since:
            start_idx = i + 1
            break

    if start_idx is None:
        # 未匹配到，可能日志已轮转，返回最近条
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
@require_role("admin")
def get_app_log_raw(request: Request):
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
@require_role("admin")
def clear_logs(
    request: Request,
    before_hours: int = 24,
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

        # 保留最近_小时内的日志
        from datetime import datetime, timedelta

        cutoff = datetime.now() - timedelta(hours=before_hours)
        kept = []
        deleted = 0
        for line in lines:
            # 日志格式:"-::[]"
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


# ── 轮转日志访问 ──────────────────────────────────────────────


def _log_dir() -> str:
    """返回日志目录的 realpath 形式，供路径校验统一使用。"""
    return os.path.realpath(_get_log_dir())


def _list_rotated_impl() -> list[dict]:
    """扫描日志目录，返回轮转日志文件列表（缓存 60 秒避免频繁 IO）。"""
    now = time.monotonic()
    if now - _list_cache["ts"] < _LIST_CACHE_SECONDS:
        return _list_cache["files"]
    files: list[dict] = []
    log_dir = _log_dir()
    try:
        for name in os.listdir(log_dir):
            if not _ROTATED_NAME_RE.match(name):
                continue
            path = os.path.join(log_dir, name)
            if not os.path.isfile(path):
                continue
            st = os.stat(path)
            files.append(
                {
                    "name": name,
                    "size_bytes": st.st_size,
                    "mtime_iso": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
                    "lines_estimate": max(st.st_size // _AVG_LINE_BYTES, 0),
                }
            )
    except OSError:
        pass
    files.sort(key=lambda f: f["mtime_iso"], reverse=True)
    _list_cache["ts"] = now
    _list_cache["files"] = files
    return files


def _read_rotated_impl(filename: str, offset: int, limit: int, grep: str, context: int) -> dict:
    """流式读取轮转日志内容（分页 + grep 过滤 + 前后 context），不整文件载入内存。"""
    log_dir = _log_dir()
    full_path = os.path.realpath(os.path.join(log_dir, filename))
    # realpath 越界校验：拼接后必须仍在日志目录内
    if not full_path.startswith(log_dir + os.sep):
        raise HTTPException(status_code=403, detail="路径越界")
    if not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    offset = max(offset, 0)
    limit = min(max(limit, 1), 1000)
    context = min(max(context, 0), 10)

    total_lines = 0
    content: list[str] = []

    if not grep:
        # 纯分页：逐行跳过 offset，取 limit 行
        with open(full_path, encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                total_lines += 1
                if i < offset:
                    continue
                if len(content) >= limit:
                    continue
                content.append(line.rstrip("\n"))
    else:
        # grep 加上下文：滑动窗口取匹配行前后若干行
        before: deque[str] = deque(maxlen=context)
        after_remaining = 0
        with open(full_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                total_lines += 1
                line = line.rstrip("\n")
                if after_remaining > 0:
                    content.append(line)
                    after_remaining -= 1
                    continue
                if grep in line:
                    content.extend(before)
                    content.append(line)
                    after_remaining = context
                    before.clear()
                else:
                    before.append(line)
        # 结果集再做 offset/limit 切分
        content = content[offset : offset + limit]

    return {
        "filename": filename,
        "total_lines": total_lines,
        "returned_lines": len(content),
        "offset": offset,
        "content": content,
    }


@router.get("/api/logs/rotated")
@require_role("admin")
def list_rotated_logs(request: Request) -> list[dict]:
    """返回轮转日志文件列表。"""
    return _list_rotated_impl()


@router.get("/api/logs/rotated/{filename}")
@require_role("admin")
def read_rotated_log(
    request: Request,
    filename: str,
    offset: int = 0,
    limit: int = 500,
    grep: str = "",
    context: int = 0,
) -> dict:
    """读取指定轮转日志内容（分页 + 搜索 + 上下文）。"""
    # 文件名白名单校验，同时显式拒绝路径遍历字符
    if not _ROTATED_NAME_RE.match(filename) or any(c in filename for c in "/\\%"):
        raise HTTPException(status_code=400, detail="非法文件名")
    return _read_rotated_impl(filename, offset, limit, grep, context)
