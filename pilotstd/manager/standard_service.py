# 模块：标准统计与列表查询服务
# 统一数据源为文件索引表

import logging
from typing import Any, Final

from pilotstd.core.db._constants import DatabaseError
from pilotstd.core.status import Status

logger = logging.getLogger(__name__)

#: 状态**统计分桶的显式枚举**：每个 `Status` 成员必须且只能归入一个桶（N2，P1-5 §5.2）。
#: 历史实现用「四值之外即未知」的补集机制——任何枚举外新值都会被静默吞进「未知」，
#: 既不报错也不告警。新增枚举值必须在此显式归桶，否则：
#: ① `tests/test_standard_service.py::TestExplicitStatusBuckets` 红；
#: ② 生产 `get_stats()` 会把该值当枚举外脏值告警（见 `_warn_unknown_statuses`）。
_STATUS_BUCKETS: Final[dict[str, tuple[Status, ...]]] = {
    Status.ACTIVE.value: (Status.ACTIVE,),
    # 废止族口径 = 废止 + 被代替 + 作废（A1 修复）；`已废止` 是展示规范拼写，同计入本桶
    Status.WITHDRAWN_NORMALIZED.value: (
        Status.WITHDRAWN,
        Status.WITHDRAWN_NORMALIZED,
        Status.SUPERSEDED,
        Status.VOIDED,
    ),
    Status.UNKNOWN.value: (Status.UPCOMING, Status.EXPIRED, Status.PENDING, Status.UNKNOWN),
}

#: 状态值 → 统计桶（由 `_STATUS_BUCKETS` 反向派生，保证两者不会脱节）
_STATUS_TO_BUCKET: Final[dict[str, str]] = {
    member.value: bucket for bucket, members in _STATUS_BUCKETS.items() for member in members
}

#: 各桶在 **SQL 筛选** 中使用的数据值：排除 `已废止`（展示规范拼写，不是 DB 数据值；
#: 写入端统一落 `废止`，见 `pilotstd/core/status.py::normalize_status_for_write()`）。
_STATUS_FILTER_VALUES: Final[dict[str, tuple[str, ...]]] = {
    bucket: tuple(member.value for member in members if member is not Status.WITHDRAWN_NORMALIZED)
    for bucket, members in _STATUS_BUCKETS.items()
}


class StandardService:
    """标准统计与列表查询（数据源：文件索引表，与首页卡片口径一致）。"""

    def __init__(self, manager: Any):
        self._mgr = manager
        # 已告警过的枚举外状态值（同一取值只告警一次，避免每次统计刷屏）
        self._warned_unknown_statuses: set[str] = set()

    # ── 状态映射：前端筛选值映射到文件索引表实际值 ──

    @staticmethod
    def _map_filter_status(filter_status: str) -> tuple[list[str], str | None]:
        """将前端筛选状态值映射到文件索引表的查询条件子句。
        返回：(值列表, 操作符) —— 操作符为包含、不包含或等于。

        废止族口径 = `_STATUS_BUCKETS` 的「已废止」桶（废止 + 被代替 + 作废）：
        `作废` 是 `Status` 枚举内的合法废止族状态（见 `core/status.py`），必须随
        「已废止」筛选一起返回、并从「未知」补集中排除，否则 58 条 `作废` 会被错误
        折叠进「未知」（P1-5 摸底报告 §5.1-A1）。

        「未知」筛选取非未知桶的补集，与 `get_stats()` 的显式分桶**同源**，
        保证「列表筛选结果」与「卡片数字」永远自洽。
        """
        if filter_status == Status.UNKNOWN.value:
            known = [
                value
                for bucket, values in _STATUS_FILTER_VALUES.items()
                if bucket != Status.UNKNOWN.value
                for value in values
            ]
            return (known, "NOT IN")
        bucket_values = _STATUS_FILTER_VALUES.get(filter_status)
        if bucket_values is not None:
            return (list(bucket_values), None if len(bucket_values) == 1 else "IN")
        # 枚举内的单值状态（如 `作废` / `即将实施` / `过期`）走精确匹配
        return ([filter_status], None)

    @staticmethod
    def _build_where(filters: dict[str, Any] | None, alias: str = "") -> tuple[str, list[Any]]:
        """构建文件索引表查询的条件子句，与首页卡片过滤条件一致。
        alias: 可选表别名前缀（如 'f.'），用于多表连接时消除列名歧义。
        """
        p = f"{alias}." if alias else ""
        clauses = [f"{p}status IS NOT NULL"]
        params: list[Any] = []
        if not filters:
            return "WHERE " + " AND ".join(clauses), params

        if filters.get("status"):
            values, op = StandardService._map_filter_status(filters["status"])
            if op == "IN":
                placeholders = ", ".join("?" for _ in values)
                clauses.append(f"{p}status IN ({placeholders})")
                params.extend(values)
            elif op == "NOT IN":
                placeholders = ", ".join("?" for _ in values)
                clauses.append(f"{p}status NOT IN ({placeholders})")
                params.extend(values)
            else:
                clauses.append(f"{p}status = ?")
                params.append(values[0])

        if filters.get("keyword"):
            clauses.append(f"(({p}logical_code || ' ' || {p}number) LIKE ? OR {p}std_name LIKE ?)")
            kw = f"%{filters['keyword']}%"
            params.extend([kw, kw])

        return "WHERE " + " AND ".join(clauses), params

    # ── 统计 ──

    def get_stats(self) -> dict[str, Any]:
        """获取标准统计信息（按状态分组计数），数据源为文件索引表。
        查询语句与首页卡片 get_status_stats() 完全一致。

        口径（P1-5）：已废止 = 废止 + 被代替 + 作废；未知 = 显式分桶中「未知」桶
        （即将实施 / 过期 / 待确认 / 未知）+ **枚举外脏值**（后者额外 `logger.warning`
        一次并带样本，见 `_warn_unknown_statuses`；A1 只修了 `作废` 这个具体值，
        本次修掉「补集吞新值」的机制）。
        """
        db = self._mgr.db
        rows = db.fetchall("SELECT status, COUNT(*) AS cnt FROM file_index WHERE status IS NOT NULL GROUP BY status")
        s = {row["status"]: row["cnt"] for row in rows}
        by_status: dict[str, int] = {bucket: 0 for bucket in _STATUS_BUCKETS}
        unknown_extras: dict[str, int] = {}
        for st, cnt in s.items():
            bucket = _STATUS_TO_BUCKET.get(st)
            if bucket is None:
                # 枚举外值：计入「未知」而不是丢弃，但必须可追踪（告警 + 测试守卫）
                unknown_extras[st] = cnt
            else:
                by_status[bucket] += cnt
        if unknown_extras:
            self._warn_unknown_statuses(db, unknown_extras)
            by_status[Status.UNKNOWN.value] += sum(unknown_extras.values())
        return {
            "total": sum(by_status.values()),
            "by_status": by_status,
        }

    # ── 枚举外状态值告警（N2）──

    @staticmethod
    def _unknown_status_samples(db: Any, statuses: tuple[str, ...]) -> list[str]:
        """[FUNC] 取枚举外状态值的少量样本（标准号），仅供告警定位；查询失败不阻断统计。"""
        placeholders = ", ".join("?" for _ in statuses)
        try:
            rows = db.fetchall(
                "SELECT (logical_code || ' ' || number) AS standard_number FROM file_index"
                f" WHERE status IN ({placeholders}) ORDER BY id LIMIT 3",
                tuple(statuses),
            )
        except DatabaseError as exc:
            logger.warning("枚举外状态样本查询失败: %s", exc)  # i18n-allow: 内部运维日志
            return []
        samples: list[str] = []
        for row in rows:
            number = row.get("standard_number") if isinstance(row, dict) else None
            if number:
                samples.append(str(number))
        return samples

    def _warn_unknown_statuses(self, db: Any, unknown_values: dict[str, int]) -> None:
        """[FUNC] 对枚举外状态值告警：**每个取值只告警一次**，带取值计数与样本标准号。"""
        fresh = {
            st: cnt for st, cnt in unknown_values.items() if st not in self._warned_unknown_statuses
        }
        if not fresh:
            return
        self._warned_unknown_statuses.update(fresh)
        samples = self._unknown_status_samples(db, tuple(fresh))
        logger.warning(  # i18n-allow: 内部运维日志
            "状态统计发现枚举外取值（新增状态值须显式加入 Status 枚举与统计分桶）: %s；样本: %s",
            ", ".join(f"{st}×{cnt}" for st, cnt in sorted(fresh.items())),
            ", ".join(samples) if samples else "无",  # i18n-allow: 内部运维日志
        )

    # ── 列表 ──

    def get_list(
        self,
        page: int = 1,
        size: int = 20,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """获取标准状态列表（分页加可选过滤），数据源为文件索引表。"""
        db = self._mgr.db
        offset = (page - 1) * size

        where_sql, params = self._build_where(filters, alias="f")

        total = db.fetchone(f"SELECT COUNT(*) AS cnt FROM file_index f {where_sql}", tuple(params))

        # 左连接标准有效性表获取检查时间与次数（一对一关系，无需分组）。
        # JOIN 键必须带年份：`standard_validity.standard_number` 存的是 `GB 19001-2020`
        # 这种完整号，只用 `代号 + 顺序号` 永远匹配不上（实测 100 条采样 last_checked_at 全空）。
        rows = db.fetchall(
            f"SELECT f.id, (f.logical_code || ' ' || f.number) AS standard_number,"
            f" f.status, f.std_name,"
            f" v.last_checked_at, COALESCE(v.check_count, 0) AS check_count"
            f" FROM file_index f"
            f" LEFT JOIN standard_validity v"
            f" ON (f.logical_code || ' ' || f.number ||"
            f"     CASE WHEN f.year > 0 THEN '-' || f.year ELSE '' END) = v.standard_number"
            f" {where_sql}"
            f" ORDER BY f.logical_code, f.number, f.part LIMIT ? OFFSET ?",
            tuple(params + [size, offset]),
        )

        return {
            "items": rows,
            "total": total["cnt"] if total else 0,
            "page": page,
            "size": size,
        }
