# docker/api/logs.py — 应用日志读取 API（供前端日志栏使用）
import os

from fastapi.routing import APIRouter

from pilotstd.core.logger import _get_log_dir

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
