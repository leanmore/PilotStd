# 模块：项目/核心/数据库/迁移_v53脚本
# v53：announcement_record 分页查询复合索引
# 根因：分页端点 WHERE announce_no=? ORDER BY standard_number LIMIT/OFFSET，
#      原库只有 standard_number 单列索引，EXPLAIN 显示全表扫描
#      （SCAN announcement_record USING INDEX idx_announcement_record_standard_number）。
#      复合索引 (announce_no, standard_number) 同时命中 WHERE 过滤与 ORDER BY 排序。

from typing import Any


def _migrate_v53_announce_record_pagination_index(db: Any) -> None:
    """创建公告记录分页查询复合索引（幂等，IF NOT EXISTS 保证可重复执行）。"""
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_announcement_record_announce_no_std"
        " ON announcement_record(announce_no, standard_number)"
    )
