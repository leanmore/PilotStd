#!/usr/bin/env python3
"""B 组护栏：所有 /api 路由必须声明 response_model（流式/文件响应显式豁免）。"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.routing import APIRoute

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 这些端点成功响应是 Response/FileResponse/StreamingResponse，没有 JSON 模型可校验
ALLOWLIST = {
    ("GET", "/api/notification/callback/wechat"),
    ("POST", "/api/notification/callback/{channel}"),
    ("GET", "/api/export/standards"),
    ("GET", "/api/admin/logs/app"),
    ("GET", "/api/backgrounds/{filename}"),
}


def missing_response_models(app) -> list[tuple[tuple[str, ...], str]]:
    """返回未声明 response_model 的 /api 路由。"""
    missing = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith("/api"):
            continue
        if route.response_model is not None:
            continue
        methods = tuple(sorted(route.methods))
        if any((m, route.path) in ALLOWLIST for m in methods):
            continue
        missing.append((methods, route.path))
    return missing


def main() -> int:
    """加载应用并检查全部 /api 路由。"""
    from docker.app import app

    missing = missing_response_models(app)
    if missing:
        for methods, path in missing:
            print(f"[FAIL] {','.join(methods)} {path} 缺少 response_model")
        return 1
    print("PASS: 所有 /api 路由均声明 response_model（5 个流式/文件端点豁免）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
