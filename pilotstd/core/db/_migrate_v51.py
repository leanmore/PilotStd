# 模块：项目/核心/数据库/迁移_v51脚本
# v51 迁移 — adapter_state 新增健康检查字段，从 migrations.py 拆出避免 G-010 单文件超限

from typing import Any


def _migrate_v51_adapter_health_check(db: Any) -> None:
    """为 adapter_state 表新增健康检查字段。

    last_health_check: 最近一次探活时间（NULL 表示从未检查）。
    health_status: 探活结果（up/down，NULL 表示从未检查），不用 'unknown' 减少状态枚举复杂度。
    """
    try:
        db.execute("ALTER TABLE adapter_state ADD COLUMN last_health_check TIMESTAMP")
    except Exception:
        pass  # 列已存在
    try:
        db.execute("ALTER TABLE adapter_state ADD COLUMN health_status TEXT")
    except Exception:
        pass  # 列已存在
