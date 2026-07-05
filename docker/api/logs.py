# docker/api/logs.py — 应用日志读取 API（供前端日志栏 + 压测远端取回使用）
import os

from fastapi import Depends
from fastapi.responses import FileResponse
from fastapi.routing import APIRouter

from pilotstd.core.logger import _get_log_dir

from ..auth import require_admin

router = APIRouter(tags=["logs"])

# 日志文件路径（LoggerManager 写入的 app.log）
_LOG_PATH = os.path.join(_get_log_dir(), "app.log")


@router.get("/api/logs")
def get_logs(tail: int = 50, offset: int = 0):
    """返回最近 N 行日志。tail=0 表示全量（最大 10000 行）。"""
    if not os.path.exists(_LOG_PATH):
        return {"lines": [], "path": _LOG_PATH, "note": "日志文件尚未生成"}
    try:
        with open(_LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        total = len(lines)
        if tail > 0 and total > tail:
            lines = lines[-tail:]
        elif total > 10000:
            lines = lines[-10000:]
        if offset > 0 and offset < len(lines):
            lines = lines[offset:]
        return {
            "lines": [line.rstrip("\n") for line in lines],
            "path": _LOG_PATH,
            "total": total,
        }
    except OSError as e:
        return {"lines": [f"[日志读取失败] {e}"], "path": _LOG_PATH}


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
