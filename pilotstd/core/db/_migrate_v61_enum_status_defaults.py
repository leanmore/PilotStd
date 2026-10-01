# 模块：项目/核心/数据库/迁移_v61脚本
# v61：把 `file_index.status` / `standard_validity.status` 的**列默认值**收敛到权威状态字典
#      （`pilotstd/core/status.py`），取代历史迁移里写死的中文字面量。
#
# 背景（#32-C / R14-4c）：默认值目前硬编码在 v2/v3（`file_index.status ... DEFAULT '现行'`）
# 与 v16（`standard_validity.status ... DEFAULT '未知'`）里。**P-106 铁律**：已执行迁移源码不可变
# （改动会触发 checksum 不匹配导致库无法启动）→ 只能新增版本号收敛（同 v48…v60 的追加范式）。
#
# 做法（**零数据搬动**优先）：
#   1. 读 `sqlite_master` 里两张表的建表 DDL，取出 status 列的 DEFAULT 字面量；
#   2. 与枚举派生值比较（`Status.ACTIVE.value` / `Status.UNKNOWN.value`）：
#      · 一致 → **不重建**（现网库全部命中此分支：DDL 默认值本就等于枚举值，行为零变化）；
#      · 不一致 → 走 SQLite 12 步重建，把默认值改写为枚举派生值，**保留全部数据与索引**；
#      · 表不存在/无 DEFAULT → 跳过（故障库只含部分表的场景，同 v53/v57 防御口径）。
#   3. 重建失败 → 降级为告警（同 v60 口径）：schema 默认值未收敛不影响任何功能，
#      而抛异常会让 `_run_migrations()` 直接阻断应用启动，代价远大于收益。
#
# 幂等性：重复执行结果一致（第二次比较即命中"一致"分支）。
# SQLite 限制：不支持 `ALTER COLUMN ... SET DEFAULT`，故必须重建表才能改默认值。

import logging
import re
from typing import Any

from ..status import Status
from ._constants import migration

_log = logging.getLogger("pilotstd.db.migrate.v61")

# 动态表名/列名一律取本文件全大写常量，禁止外部数据拼入（R-009）
_TARGETS: tuple[tuple[str, str, str], ...] = (
    ("file_index", "status", Status.ACTIVE.value),  # 原 v2/v3 的 DEFAULT '现行'
    ("standard_validity", "status", Status.UNKNOWN.value),  # 原 v16 的 DEFAULT '未知'
)
_TMP_SUFFIX = "__v61_tmp"


def _status_default_of(ddl: str, column: str) -> str | None:
    """从建表 DDL 中取出 `column ... DEFAULT <literal>` 的字面量（无则 None）。"""
    match = re.search(rf"\b{column}\b[^,)]*?\bDEFAULT\s+('[^']*'|\"[^\"]*\"|\S+)", ddl, re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip("'\"")


def _rebuild_with_default(db: Any, table: str, ddl: str, column: str, value: str) -> None:
    """SQLite 12 步重建：把 `table` 的 `column` 默认值改写为 `value`，保留数据与索引。"""
    tmp = f"{table}{_TMP_SUFFIX}"
    new_ddl = re.sub(
        rf"(\b{column}\b[^,)]*?\bDEFAULT\s+)('[^']*'|\"[^\"]*\"|\S+)",
        lambda m: m.group(1) + f"'{value}'",
        ddl,
        count=1,
        flags=re.IGNORECASE,
    )
    # 重建表时改名为临时表：`CREATE TABLE [IF NOT EXISTS] <table>` → `<table>__v61_tmp`
    # 表名可能被引号包裹（SQLite 对 RENAME 后的表会把名字写成 "table"），两种写法都要吃下
    new_ddl = re.sub(
        rf"(\bTABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?)(\"?\[?`?{re.escape(table)}`?\]?\"?)",
        lambda m: f"{m.group(1)}{tmp}",
        new_ddl,
        count=1,
        flags=re.IGNORECASE,
    )
    index_sqls = [
        row["sql"]
        for row in db.fetchall(
            "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name=? AND sql IS NOT NULL",
            (table,),
        )
    ]
    columns = [row["name"] for row in db.fetchall(f"PRAGMA table_info({table})")]
    column_list = ", ".join(columns)

    db.execute("PRAGMA foreign_keys=OFF")
    try:
        db.execute(new_ddl)
        db.execute(f"INSERT INTO {tmp} ({column_list}) SELECT {column_list} FROM {table}")
        db.execute(f"DROP TABLE {table}")
        db.execute(f"ALTER TABLE {tmp} RENAME TO {table}")
        for sql in index_sqls:
            db.execute(sql)
    finally:
        db.execute("PRAGMA foreign_keys=ON")


@migration(61)
def _migrate_v61_enum_status_defaults(db: Any) -> None:
    """把状态列默认值收敛到 `pilotstd/core/status.py`（幂等；不一致时才重建表）。"""
    for table, column, expected in _TARGETS:
        row = db.fetchone("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,))
        if not row or not row["sql"]:
            _log.debug("v61：表 %s 不存在，跳过", table)
            continue
        ddl = row["sql"]
        current = _status_default_of(ddl, column)
        if current is None:
            _log.debug("v61：%s.%s 无 DEFAULT 子句，跳过", table, column)
            continue
        if current == expected:
            _log.debug("v61：%s.%s 默认值已等于枚举值 %r，无需重建", table, column, expected)
            continue
        try:
            _rebuild_with_default(db, table, ddl, column, expected)
            _log.warning("v61：%s.%s 默认值 %r → %r（表已重建，数据与索引保留）", table, column, current, expected)
        except Exception as e:  # noqa: BLE001 — 降级为告警，避免阻断启动（同 v60 口径）
            _log.warning("v61：重建 %s 以收敛默认值失败（%s），schema 未收敛但不影响功能", table, e)
