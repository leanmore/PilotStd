# 容器//脚本—备份管理接口
import logging
import os
from datetime import datetime

from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

from pilotstd.core.audit import get_current_user_id as audit_actor_id
from pilotstd.core.audit import write_audit
from pilotstd.core.notification.security_notifier import client_ip

from ..auth import require_role
from ..manager import get_manager_dep

logger = logging.getLogger(__name__)
router = APIRouter(tags=["backup"])


def _get_backup_dir(mgr) -> str:
    """返回备份目录：与数据库文件同级，便于整目录搬迁与容量核查。

    不新建独立配置项——备份目录始终随数据库位置派生，避免二者分离导致
    "备份到了另一块盘而运维不知情"。
    """
    db_path = mgr.db.path
    return os.path.join(os.path.dirname(db_path), "backups")


# 说明：本模块的写操作端点（create_backup）在 L-01 接线时补入审计。
# 读操作端点（list_backups）不写审计——只读不改变状态，无留痕价值。


@router.get("/api/backup/list")
@require_role("admin")
def list_backups(request: Request, mgr=Depends(get_manager_dep)):
    """获取所有备份列表（**仅管理员**）。

    **授权（收尾 B）**：原实现无 `@require_role`——与 `POST /api/backup/create` 同类越权。
    列表虽不含备份**内容**，但**备份文件的存在性本身是信息**：文件名带时间戳，可据此推断
    系统状态与备份频率（如是否存在攻击前后的快照、运维活跃度）。普通用户无需知道。

    **`request` 参数不可省**：`require_role` 从**函数参数**中查找 `Request`
    （`docker/auth.py` 的 wrapper 遍历 `args`/`kwargs`）以读取 Cookie 中的 JWT。
    若签名中无 `request`，wrapper 取不到请求对象 → `current_role` 回落默认 `"user"`
    → **连 admin 也被拒**（实测：加 `@require_role` 但无 `request` 时 admin 得 403）。
    这与 `create_backup` 当初补 `request` 参数是同一原因。

    本文件两个端点现均为 admin-only（`list` 读 + `create` 写）。
    """
    backup_dir = _get_backup_dir(mgr)
    backups = []
    if os.path.exists(backup_dir):
        for f in sorted(os.listdir(backup_dir), reverse=True):
            if f.endswith(".bak") or f.endswith(".db"):
                path = os.path.join(backup_dir, f)
                stat = os.stat(path)
                backups.append(
                    {
                        "id": f,
                        "name": f,
                        "size": stat.st_size,
                        "size_mb": round(stat.st_size / (1024 * 1024), 2),
                        "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    }
                )
    return {"items": backups, "count": len(backups)}


@router.post("/api/backup/create")
@require_role("admin")
def create_backup(request: Request, mgr=Depends(get_manager_dep)):
    """手动创建数据库备份（**仅管理员**）。

    **授权（本批修复）**：原实现无 `@require_role`——全局 `AuthMiddleware`
    （docker/app.py:288）只保证"已认证"，不保证角色；故**任意登录用户**都能触发出
    含全量数据库内容（用户表/密码哈希/审计日志/通知凭证）的备份文件。属越权。

    全部出口（1 成功 + 2 失败）均写审计——手动备份与定时路径口径不同，
    且失败原因（备份 API 返回假/异常）是运维排查的关键信号。
    """
    actor_id = audit_actor_id()
    from_ip = client_ip(request)
    try:
        result = mgr.db.backup(
            os.path.join(_get_backup_dir(mgr), f"pilotstd_manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak")
        )
        if result:
            write_audit(
                action="BACKUP_CREATE",
                resource="POST /api/backup/create",
                detail={"from_ip": from_ip, "result": "ok"},
                user_id=actor_id,
            )
            return {"ok": True, "message": "备份创建成功"}
        write_audit(
            action="BACKUP_CREATE_FAILED",
            resource="POST /api/backup/create",
            detail={"from_ip": from_ip, "reason": "backup_api_returned_false"},
            user_id=actor_id,
        )
        return JSONResponse({"ok": False, "message": "备份创建失败"}, status_code=500)
    except Exception as e:
        logger.exception("手动备份失败")
        write_audit(
            action="BACKUP_CREATE_FAILED",
            resource="POST /api/backup/create",
            detail={"from_ip": from_ip, "reason": str(e)},
            user_id=actor_id,
        )
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
