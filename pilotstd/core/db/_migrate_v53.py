# 模块：项目/核心/数据库/迁移_v53脚本
# v53：announcement_record 分页查询复合索引
# 根因：分页端点 WHERE announce_no=? ORDER BY standard_number LIMIT/OFFSET，
#      原库只有 standard_number 单列索引，EXPLAIN 显示全表扫描
#      （SCAN announcement_record USING INDEX idx_announcement_record_standard_number）。
#      复合索引 (announce_no, standard_number) 同时命中 WHERE 过滤与 ORDER BY 排序。

from typing import Any


def _migrate_v53_announce_record_pagination_index(db: Any) -> None:
    """为 announcement_record 添加复合索引以优化分页查询（幂等）。

    防御性检查：从旧版本跳跃迁移时 announcement_record 表可能尚未创建
    （如仅含 user_favorites 的故障库场景），此时跳过建索引，
    由后续迁移或首次完整初始化创建表后再建。
    """
    tables = db.fetchall(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='announcement_record'"
    )
    if not tables:
        return  # 表不存在则跳过，避免 CREATE INDEX 报 no such table

    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_announcement_record_announce_no_std"
        " ON announcement_record(announce_no, standard_number)"
    )
