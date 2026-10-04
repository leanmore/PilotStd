# 容器//脚本—通知接口公共依赖（步 C：按职责自 notification.py 拆出）
"""通知接口的公共依赖注入助手：用户存在性校验 + 通知管理器获取。

**为什么独立成模块**：这两个助手此前定义在 `docker/api/notification.py`，被配置 / 日志 /
策略三组端点共用；端点按职责拆到子模块后，若子模块反向 import 聚合模块会构成**循环导入**，
故助手独立成模块（聚合模块再导出 `_get_user_id`，保持既有 import 路径可用）。
"""

from typing import cast

from fastapi import Depends, HTTPException

from pilotstd.core.notification import NotificationManager
from pilotstd.i18n import t

from ..auth import get_current_user_id
from ..manager import get_manager_dep


def _get_user_id(user_id: int = Depends(get_current_user_id), mgr=Depends(get_manager_dep)) -> int:
    """按主键校验用户存在性，不存在则抛出 401。"""
    if mgr.user_service.get_user_by_id(user_id) is None:
        raise HTTPException(status_code=401, detail=t("notification.api.user_not_found"))
    return user_id


def _get_notification_mgr(mgr=Depends(get_manager_dep)) -> NotificationManager:
    return cast("NotificationManager", mgr.notification_mgr)
