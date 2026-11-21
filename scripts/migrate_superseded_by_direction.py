#!/usr/bin/env python3
"""superseded_by 方向纠正迁移（默认只演练，不写库）。

## 背景（2026-11-21 生产实测）

`announcement_record.superseded_by` 现在写的是“本行标准替代了谁”（如
`GB 30871-2022 -> GB 30871-2014`），语义应反过来：**旧标准指向新标准**。
抽样 4,000 行：方向倒退 3,695 行（92%），已是正向仅 1 行，其余无法判年。

## 规则（数据实证后收敛，见 docs/onboarding/27 #97）

对每行 `(std, sup)`：
1. `sup` 为空 → 跳过；
2. `year(sup) < year(std)`（方向倒退）→ 把 `std.superseded_by` 里这一条去掉；
3. 目标旧标准行（`standard_number = sup`）的 `superseded_by` **只在该列为空时才写** `std`；
   已有值的 67/100 条本身也是乱的（实测无一条正向），直接覆盖会丢信息 → 交给清洗流程，不在这里改；
4. `year(sup) >= year(std)` → 已经是正向，保持不动；
5. 多值（逗号分隔）逐条拆分处理，只去掉倒退的那几条，其余保留原样。

## 用法

```
python scripts/migrate_superseded_by_direction.py --db data/pilotstd.db              # 演练（默认）
python scripts/migrate_superseded_by_direction.py --db data/pilotstd.db --limit 100  # 只演练 100 行
python scripts/migrate_superseded_by_direction.py --db data/pilotstd.db --apply --limit 100
python scripts/migrate_superseded_by_direction.py --db data/pilotstd.db --rollback C:/Temp/plan.json --apply
```

`--apply` 前会建列级备份表 `announcement_record_bak_<yyyymmdd>`；`--rollback` 用它按 id 还原。
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# 标准号里的年份：取最后一个 `-YYYY`（兼容 `GB/T 1.1-2020`、`ISO 16852:2016` 之外的常见形态）
YEAR_RE = re.compile(r"-(\d{4})\s*$")
# 多值分隔符：源站用半角逗号，个别行混用中文逗号
SPLIT_RE = re.compile(r"[,，]")


def parse_year(code: str) -> int:
    """从标准号取年份；取不到返回 0（调用方按“无法判年”处理）。"""
    m = YEAR_RE.search((code or "").strip())
    return int(m.group(1)) if m else 0


def split_codes(cell: str | None) -> list[str]:
    """把 `A,B` 拆成列表并去空白；空值返回空列表。"""
    if not cell:
        return []
    return [c.strip() for c in SPLIT_RE.split(cell) if c and c.strip()]


@dataclass
class RowPlan:
    """单行的迁移计划：清掉哪些倒退值、目标行要不要写。"""

    row_id: int
    standard_number: str
    before: str
    keep: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    targets: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        """本行是否需要更新（去掉过倒退值）。"""
        return bool(self.dropped)

    def after(self) -> str:
        """更新后的单元格内容（保留原顺序）。"""
        return ",".join(self.keep)


def plan_row(row_id: int, standard_number: str, superseded_by: str | None) -> RowPlan:
    """按规则拆出一条记录的迁移计划（纯函数，便于测试）。"""
    codes = split_codes(superseded_by)
    std_year = parse_year(standard_number)
    keep: list[str] = []
    dropped: list[str] = []
    targets: list[str] = []
    for code in codes:
        sup_year = parse_year(code)
        # 无年份或不是倒退方向：原样保留，不做任何猜测
        if not sup_year or not std_year or sup_year >= std_year:
            keep.append(code)
            continue
        dropped.append(code)
        targets.append(code)
    return RowPlan(
        row_id=row_id,
        standard_number=standard_number,
        before=superseded_by or "",
        keep=keep,
        dropped=dropped,
        targets=targets,
    )


def _connect(db_path: Path) -> sqlite3.Connection:
    """打开库并开启行工厂（只读演练也用同一连接）。"""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _backup_table_name() -> str:
    """列级备份表名（按天，重复执行复用同一张）。"""
    return f"announcement_record_bak_{datetime.now().strftime('%Y%m%d')}"


def _ensure_backup(conn: sqlite3.Connection) -> str:
    """建列级备份表（幂等）；返回表名。"""
    name = _backup_table_name()
    conn.execute(
        f"CREATE TABLE IF NOT EXISTS {name} AS "
        "SELECT id, standard_number, superseded_by FROM announcement_record"
    )
    return name


def collect_plans(conn: sqlite3.Connection, limit: int) -> list[RowPlan]:
    """扫描待处理行并生成计划；`limit=0` 表示不限。"""
    sql = (
        "SELECT id, standard_number, superseded_by FROM announcement_record "
        "WHERE superseded_by IS NOT NULL AND superseded_by != '' ORDER BY id"
    )
    if limit:
        sql += f" LIMIT {int(limit)}"
    plans = [plan_row(r["id"], r["standard_number"], r["superseded_by"]) for r in conn.execute(sql)]
    return [p for p in plans if p.changed]


def apply_plans(conn: sqlite3.Connection, plans: list[RowPlan]) -> dict[str, int]:
    """写入计划：两阶段，整体一个事务。

    阶段 1 先把所有「方向倒退」的值清掉（含目标行自身也是倒退值的情况）；
    阶段 2 再给此时已为空的目标行补反向指针。若合并成单循环，目标行自己的清理
    与别的行对它的回填会互相阻塞（先回填再清理等于白写，先清理再回填才对）。
    """
    cleared = 0
    linked = 0
    with conn:  # 事务：失败自动回滚
        for plan in plans:
            conn.execute(
                "UPDATE announcement_record SET superseded_by = ? WHERE id = ?",
                (plan.after(), plan.row_id),
            )
            cleared += 1
        for plan in plans:
            for target in plan.targets:
                # 规则 3：只写空值（阶段 1 已把乱值清掉，这里写的是“清洗后的空位”）
                cur = conn.execute(
                    "UPDATE announcement_record SET superseded_by = ? "
                    "WHERE standard_number = ? "
                    "AND (superseded_by IS NULL OR superseded_by = '')",
                    (plan.standard_number, target),
                )
                linked += cur.rowcount
    return {"cleared_rows": cleared, "linked_rows": linked}


def rollback(conn: sqlite3.Connection, plan_file: Path) -> int:
    """按计划 JSON 还原：源行按 id，被回填的目标行按标准号一起还原。

    只按 id 还原会漏掉“被回填”的目标行（它们不在 plans 里），导致回滚后
    目标行仍留着新值 —— 演练时就踩过这个坑。
    """
    data = json.loads(plan_file.read_text(encoding="utf-8"))
    plans = data.get("plans", [])
    ids = [int(x["row_id"]) for x in plans]
    targets = [str(t) for x in plans for t in (x.get("targets") or [])]
    if not ids:
        return 0
    name = data.get("backup_table") or _backup_table_name()
    marks = ",".join("?" for _ in ids)
    where = f"id IN ({marks})"
    params: list[object] = list(ids)
    if targets:
        tmarks = ",".join("?" for _ in targets)
        where += f" OR standard_number IN ({tmarks})"
        params.extend(targets)
    with conn:
        cur = conn.execute(
            f"UPDATE announcement_record SET superseded_by = ("
            f"SELECT b.superseded_by FROM {name} b WHERE b.id = announcement_record.id) "
            f"WHERE {where}",
            params,
        )
    return cur.rowcount


def main(argv: list[str] | None = None) -> int:
    """入口：演练/应用/回滚三选一。"""
    ap = argparse.ArgumentParser(description="superseded_by 方向纠正迁移")
    ap.add_argument("--db", required=True, help="SQLite 路径（容器内通常是 /app/data/pilotstd.db）")
    ap.add_argument("--limit", type=int, default=0, help="最多处理多少行（0=不限）")
    ap.add_argument("--apply", action="store_true", help="真正写库（默认只演练）")
    ap.add_argument("--json", default="", help="把计划写到 JSON（--apply 时作为回滚依据）")
    ap.add_argument("--rollback", default="", help="按之前的 JSON 计划回滚")
    args = ap.parse_args(argv)

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"数据库不存在: {db_path}", file=sys.stderr)
        return 2
    conn = _connect(db_path)

    if args.rollback:
        if not args.apply:
            print("回滚也需要 --apply 才会写库", file=sys.stderr)
            return 2
        n = rollback(conn, Path(args.rollback))
        print(f"已回滚 {n} 行（依据 {args.rollback}）")
        return 0

    plans = collect_plans(conn, args.limit)
    dropped_total = sum(len(p.dropped) for p in plans)
    print(f"待处理行 {len(plans)}，将清掉倒退值 {dropped_total} 条")

    if args.json:
        payload = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "backup_table": _backup_table_name(),
            "plans": [
                {"row_id": p.row_id, "standard_number": p.standard_number,
                 "before": p.before, "after": p.after(), "dropped": p.dropped,
                 "targets": p.targets}
                for p in plans
            ],
        }
        Path(args.json).write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"计划已写出: {args.json}")

    if not args.apply:
        for p in plans[:5]:
            print(f"  样例 #{p.row_id} {p.standard_number}: {p.before} -> {p.after()}")
        print("（演练模式，未写库；加 --apply 执行）")
        return 0

    name = _ensure_backup(conn)
    print(f"列级备份表: {name}")
    result = apply_plans(conn, plans)
    print(f"已清理 {result['cleared_rows']} 行，补写空值目标 {result['linked_rows']} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
