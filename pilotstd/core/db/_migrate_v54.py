# 模块：项目/核心/数据库/迁移_v54脚本
# v54：favorite_downloads 补 user_id / standard_no / standard_name 列 + 回填存量
# 根因：收藏→下载链路断链修复的前置——add_favorite 需在 favorite_downloads 写入
#      带 user_id 隔离与标准信息的记录（v44 表只有 favorite_id/record_id 关联）。
# 设计（v3.0 + 实测适配）：
#  - 以实测 v44 表结构为基准（favorite_id NOT NULL, record_id NOT NULL, ...），仅补列不重建
#  - 列名探测：announcement_record 实际列为 standard_number / std_name
#  - 回填：user_id 取自 user_favorites（favorite_id 关联），标准信息取自 announcement_record
#  - 防御：前置表缺失（跳跃迁移）时跳过，由完整初始化兜底

from typing import Any

from ._constants import migration

# 目标列：列名 → 建列 SQL 片段
_TARGET_COLUMNS = {
    "user_id": "user_id INTEGER",
    "standard_no": "standard_no TEXT",
    "standard_name": "standard_name TEXT",
}


@migration(54)
def _migrate_v54_favorite_downloads_columns(db: Any) -> None:
    """补 favorite_downloads 列 + 回填存量（幂等，可重复执行）。"""
    tables = {r["name"] for r in db.fetchall("SELECT name FROM sqlite_master WHERE type='table'")}
    # 防御：favorite_downloads / user_favorites / announcement_record 任一缺失则跳过
    if not {"favorite_downloads", "user_favorites", "announcement_record"} <= tables:
        return

    # ── 1. 补列（探测式，幂等）──
    fd_cols = {r["name"] for r in db.fetchall("PRAGMA table_info(favorite_downloads)")}
    for col, col_sql in _TARGET_COLUMNS.items():
        if col not in fd_cols:
            db.execute(f"ALTER TABLE favorite_downloads ADD COLUMN {col_sql}")

    # ── 2. 回填 user_id：从 user_favorites 关联（favorite_id → user_favorites.id）──
    db.execute(
        "UPDATE favorite_downloads SET user_id = ("
        "  SELECT uf.user_id FROM user_favorites uf WHERE uf.id = favorite_downloads.favorite_id"
        ") WHERE user_id IS NULL"
    )

    # ── 3. 回填标准信息：列名探测（实测 standard_number / std_name）──
    ar_cols = {r["name"] for r in db.fetchall("PRAGMA table_info(announcement_record)")}
    std_no_col = "standard_number" if "standard_number" in ar_cols else None
    std_name_col = "std_name" if "std_name" in ar_cols else None
    if std_no_col:
        db.execute(
            f"UPDATE favorite_downloads SET standard_no = ("
            f"  SELECT ar.{std_no_col} FROM announcement_record ar WHERE ar.id = favorite_downloads.record_id"
            f") WHERE standard_no IS NULL"
        )
    if std_name_col:
        db.execute(
            f"UPDATE favorite_downloads SET standard_name = ("
            f"  SELECT ar.{std_name_col} FROM announcement_record ar WHERE ar.id = favorite_downloads.record_id"
            f") WHERE standard_name IS NULL"
        )
