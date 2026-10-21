# 模块：公告入库条数对账
"""P2 防漏：按公告聚合，对比源站声明条数与实际入库记录数。"""

from __future__ import annotations

from typing import Any


def find_announcement_count_mismatches(db: Any) -> list[dict[str, Any]]:
    """返回源站 `standard_count` 与实际 `announcement_record` 行数不一致的公告。

    口径：同一 source_site + 公告号聚合；`standard_count` 取该公告下的最大值（同公告所有
    记录共享该值）。返回项含 declared/actual/diff，供运维巡检或启动告警使用。
    """
    rows = db.fetchall(
        "SELECT source_site, TRIM(announce_no) AS announce_no,"
        " MAX(standard_count) AS declared, COUNT(*) AS actual"
        " FROM announcement_record"
        " WHERE announce_no IS NOT NULL AND TRIM(announce_no) != ''"
        " GROUP BY source_site, TRIM(announce_no)"
        " HAVING MAX(standard_count) IS NOT NULL AND COUNT(*) != MAX(standard_count)"
        " ORDER BY source_site, announce_no"
    )
    result = []
    for row in rows:
        declared = int(row["declared"])
        actual = int(row["actual"])
        result.append(
            {
                "source_site": row["source_site"],
                "announce_no": row["announce_no"],
                "declared": declared,
                "actual": actual,
                "diff": actual - declared,
            }
        )
    return result
