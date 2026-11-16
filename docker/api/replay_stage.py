"""受控测试投放/移动端点（M1 #2）。

仅用于测试线：把文件复制/移动到 `/inbox/__replay_*` 或 `/inbox/_quarantine`，
可选把目标 mtime 设为当前时间。**默认关闭**（`PILOTSTD_ENABLE_REPLAY_STAGE=1` 才启用），
不做任意写、删除、跨前缀操作；全部路径 realpath 校验并写审计。
"""

from __future__ import annotations

import logging
import os
import shutil
import time
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from pilotstd.core.audit import write_audit

from ..auth import require_role

logger = logging.getLogger(__name__)
router = APIRouter(tags=["replay-admin"])

_SRC_ROOTS = ("/inbox", "/standards")
_DST_PREFIXES = ("/inbox/__replay_",)
_DST_EXACT = "/data/_quarantine"
_MAX_ITEMS = 2000


class StageItem(BaseModel):
    """单条投放：源文件 → 目标路径。"""

    source: str = Field(min_length=1)
    target: str = Field(min_length=1)


class StageRequest(BaseModel):
    """投放请求：copy/move + 是否把目标 mtime 设为当前时间。"""

    action: Literal["copy", "move"] = "copy"
    items: list[StageItem]
    set_mtime: bool = True


class StageResultItem(BaseModel):
    """单条投放结果。"""

    source: str
    target: str
    ok: bool
    error: str = ""


class StageResponse(BaseModel):
    """批量投放结果。"""

    action: str
    total: int
    ok: int
    failed: int
    results: list[StageResultItem]


# 路径校验统一用 realpath 后再做前缀比较，避免 ../ 或符号链接逃逸
def _norm(path: str) -> str:
    """统一成 POSIX 风格（Windows 单测/容器路径一致），并去掉盘符。"""
    text = path.replace(chr(92), "/")
    if len(text) >= 2 and text[1] == ":":
        text = text[2:]
    return text


def _under(path: str, root: str) -> bool:
    """path 是否在 root 内（含相等）。"""
    path, root = _norm(path), _norm(root)
    return path == root or path.startswith(root.rstrip("/") + "/")


# 目标只允许两个测试前缀：__replay_*（投放）与 _quarantine（隔离）
def _dst_allowed(dst: str) -> bool:
    """目标必须落在测试前缀内。"""
    dst = _norm(dst)
    if _under(dst, _DST_EXACT):
        return True
    return any(_under(dst, prefix) for prefix in _DST_PREFIXES)


# 单条校验：源必须在 /inbox 或 /standards，目标必须在测试前缀，且不能原地移动
def validate_item(source: str, target: str) -> tuple[str, str]:
    """校验并返回 (src_real, dst_real)；越界直接抛 ValueError。"""
    src = _norm(os.path.realpath(source))
    dst = _norm(os.path.realpath(target))
    if not any(_under(src, root) for root in _SRC_ROOTS):
        raise ValueError(f"源路径不在允许的根目录内: {source}")  # i18n-allow: 管理端点错误
    if not _dst_allowed(dst):
        raise ValueError(f"目标不在 __replay_/_data/_quarantine 前缀内: {target}")  # i18n-allow: 管理端点错误
    if src == dst:
        raise ValueError("源与目标相同")  # i18n-allow: 管理端点错误
    return src, dst


# 执行层只做 copy/move；不提供删除，set_mtime 用当前时间覆盖（epoch 秒）
def stage_one(action: str, source: str, target: str, set_mtime: bool) -> None:
    """执行单条 copy/move（调用方已完成路径校验）。"""
    parent = os.path.dirname(target)
    if parent:
        os.makedirs(parent, exist_ok=True)
    if action == "copy":
        shutil.copy2(source, target)
    else:
        shutil.move(source, target)
    if set_mtime:
        now = time.time()
        os.utime(target, (now, now))


@router.post("/api/admin/replay-stage", response_model=StageResponse)
@require_role("admin")
def replay_stage(request: Request, body: StageRequest):
    """受控投放：仅 copy/move 到测试前缀（admin + 白名单 + 审计）。"""
    if not body.items:
        raise HTTPException(400, "items 不能为空")  # i18n-allow: 管理端点错误
    if len(body.items) > _MAX_ITEMS:
        raise HTTPException(400, f"单次最多 {_MAX_ITEMS} 条")  # i18n-allow: 管理端点错误

    # 逐条执行：单条失败只记 error，不中断整批（返回里逐条可见）
    results: list[StageResultItem] = []
    ok = failed = 0
    for item in body.items:
        try:
            src, dst = validate_item(item.source, item.target)
            if not os.path.isfile(src):
                raise ValueError("源文件不存在或不是文件")  # i18n-allow: 管理端点错误
            stage_one(body.action, src, dst, body.set_mtime)
            results.append(StageResultItem(source=item.source, target=item.target, ok=True))
            ok += 1
        except Exception as exc:  # noqa: BLE001 - 单条失败不阻断其余条目，必须逐条可见
            results.append(
                StageResultItem(source=item.source, target=item.target, ok=False, error=str(exc))
            )
            failed += 1
    try:
        write_audit(
            action="REPLAY_STAGE",
            resource="POST /api/admin/replay-stage",
            detail={"action": body.action, "total": len(body.items), "ok": ok, "failed": failed},
        )
    except Exception as exc:  # noqa: BLE001 - 审计失败不改变投放结果，但必须留痕
        logger.warning("replay stage audit failed: %s", exc)
    return StageResponse(action=body.action, total=len(body.items), ok=ok, failed=failed, results=results)
