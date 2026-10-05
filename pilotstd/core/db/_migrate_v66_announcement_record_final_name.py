# 模块：项目/核心/数据库/迁移_v66脚本
# v66：announcement_record 追加 final_name 列（阶段③「名称决策」结果落库）+ 从 pending_lookup 回填存量
#
# 为什么需要这一列：名称决策（pipeline/router.py::_resolve_names）此前**只在内存**回写
# p.std_name，从不落库 ⇒ 下载通知族等 DB 后消费方读不到③的值，只能退回①②（空名/旧名）。
# 本迁移只负责「建列 + 回填历史」；**运行期写入**由 manager/classifier.py 的批量落库负责（best-effort）。
#
# 幂等（可重复执行）：
#   ① 补列前先 `PRAGMA table_info` 探测，列已存在即跳过（先例：_migrate_v54.py 同款做法）；
#   ② 回填只填 final_name 为空的行，且在待确认表中确有非空③值时才更新。

from typing import Any

from ._constants import migration


@migration(66)
def _migrate_v66_announcement_record_final_name(db: Any) -> None:
    """announcement_record 补 final_name 列 + 从 pending_lookup 回填（幂等）。"""
    tables = {r["name"] for r in db.fetchall("SELECT name FROM sqlite_master WHERE type='table'")}
    if "announcement_record" not in tables:
        return

    # ── 1. 补列（探测式，幂等）──
    cols = {r["name"] for r in db.fetchall("PRAGMA table_info(announcement_record)")}
    if "final_name" not in cols:
        db.execute("ALTER TABLE announcement_record ADD COLUMN final_name TEXT")

    # ── 2. 回填存量：把待确认表里的③值搬到公告记录上 ──
    # 只取「非空」的 final_name，**不限 status**——`pending_lookup.status` 表示"待确认流程"的
    # 生命周期（pending/resolved/manual_required），与名称本身的优劣无关；已 resolved 的行
    # 恰恰是人工确认过的高质量③值，丢掉它反而更差。
    # 只填目标列为空的行 + EXISTS 守卫 ⇒ 重跑迁移不会覆盖已有值（幂等）。
    if "pending_lookup" not in tables:
        return
    db.execute(
        "UPDATE announcement_record SET final_name = ("
        "  SELECT pl.final_name FROM pending_lookup pl"
        "  WHERE pl.standard_number = announcement_record.standard_number"
        "    AND pl.final_name IS NOT NULL AND pl.final_name != ''"
        "  ORDER BY pl.created_at DESC LIMIT 1"
        ") WHERE (final_name IS NULL OR final_name = '')"
        "  AND EXISTS ("
        "    SELECT 1 FROM pending_lookup pl2"
        "    WHERE pl2.standard_number = announcement_record.standard_number"
        "      AND pl2.final_name IS NOT NULL AND pl2.final_name != ''"
        "  )"
    )
