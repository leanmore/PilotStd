#!/usr/bin/env python3
"""部署探测：统计表对账（只读 SQL）。

走 admin 只读查询端点 `POST /query`（`docker/api/admin_db.py`；共享层强制单条
`SELECT`/`PRAGMA`/`EXPLAIN`，见 `_assert_read_only_sql`），对账以下口径：

1. **pending 自洽**：`pending_lookup` 总数 = 各 `status` 之和；`/api/pending` 返回条数
   = `status='pending'` 行数；`reason='file_missing'` 的行必须都有 `file_path`（否则是
   `no_file` 误标，见 `pilotstd/manager/pending_service.py:resolve_reason`）；
2. **收藏/下载自洽**：`user_favorites` 总数 ≥ `/api/favorites` 返回条数（接口按用户过滤）；
   `favorite_downloads` 不得有孤儿行（`favorite_id` 指向不存在的收藏）；
3. **公告记录自洽**：`/api/announce/stats` 的 `total.all` 与 `matched` 必须等于 SQL 的
   `COUNT(*)` / `COUNT(*) WHERE matched=1`；`data_state='fresh'` 行不得重复
   （`stale` 行按设计保留历史版本，允许重复）；
4. **文件索引**：`file_index` 各 `status` 之和 = 总数，且 `/api/stats` 的四项计数
   （现行/废止/待确认/即将实施）必须落在 SQL 口径内；
5. **通知日志**：`/api/notification/logs` 的 `total` 与 SQL `COUNT(*)` 一致。

只读：只发 `GET` + 白名单内的 `POST /api/login`、`POST /query`（语句在发送前已校验为只读）。

用法：
  python scripts/ops/probe_db_counts.py
  python scripts/ops/probe_db_counts.py --base-url http://192.168.1.18:9028 --json

退出码：0 通过 / 1 有失败或必跑项无法验证 / 2 环境不可达。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _probe_common as common  # noqa: E402  共享层（凭据/HTTP/报告）

# 对账 SQL：键是检查名，值是单条只读语句（共享层会再校验一次语句类型）
COUNT_SQL = {
    "announcement_record": "SELECT COUNT(*) AS c FROM announcement_record",
    "announcement_matched": "SELECT COUNT(*) AS c FROM announcement_record WHERE matched = 1",
    "pending_total": "SELECT COUNT(*) AS c FROM pending_lookup",
    "pending_pending": "SELECT COUNT(*) AS c FROM pending_lookup WHERE status = 'pending'",
    "pending_status_sum": "SELECT COUNT(*) AS c FROM pending_lookup WHERE status IS NOT NULL",
    "pending_file_missing_no_path": (
        "SELECT COUNT(*) AS c FROM pending_lookup "
        "WHERE reason = 'file_missing' AND (file_path IS NULL OR TRIM(file_path) = '')"
    ),
    "favorites_total": "SELECT COUNT(*) AS c FROM user_favorites",
    "favorite_downloads_orphan": (
        "SELECT COUNT(*) AS c FROM favorite_downloads d "
        "LEFT JOIN user_favorites f ON f.id = d.favorite_id WHERE f.id IS NULL"
    ),
    "announcement_fresh_dup": (
        "SELECT COUNT(*) AS c FROM ("
        "SELECT source_site, announce_no, standard_number FROM announcement_record "
        "WHERE data_state = 'fresh' GROUP BY 1, 2, 3 HAVING COUNT(*) > 1)"
    ),
    "file_index_total": "SELECT COUNT(*) AS c FROM file_index",
    "file_index_status_sum": "SELECT COUNT(*) AS c FROM file_index WHERE status IS NOT NULL",
    "notification_log_total": "SELECT COUNT(*) AS c FROM notification_log",
}


def _query(client: common.HttpClient, sql: str) -> tuple[bool, Any, str]:
    """执行一条只读 SQL，返回 `(成功, 首行首列值, 错误说明)`；失败原因必须回传（不吞）。"""
    response = client.post("/query", json={"sql": sql}, headers=client.csrf_headers())
    try:
        payload = response.json()
    except ValueError:
        return False, None, f"HTTP {response.status_code} 非 JSON 响应"
    if response.status_code != 200 or payload.get("success") is not True:
        return False, None, str(payload.get("error") or payload.get("code") or response.status_code)
    rows = payload.get("rows") or []
    if not rows:
        return True, None, "查询无返回行"
    return True, list(rows[0].values())[0], ""


def collect_counts(report: common.Report, client: common.HttpClient) -> dict[str, Any]:
    """批量执行对账 SQL，返回 `{检查名: 值}`；单条失败只标该条「无法验证」。"""
    values: dict[str, Any] = {}
    failures: list[str] = []
    for name, sql in COUNT_SQL.items():
        ok, value, error = _query(client, sql)
        if not ok:
            failures.append(f"{name}: {error}")
            continue
        values[name] = value
    if failures:
        report.add(
            "db.query",
            common.STATUS_UNVERIFIED,
            f"{len(failures)} 条对账 SQL 执行失败：" + "；".join(failures[:5]),
            tier=common.TIER_ADVISORY,
        )
    else:
        report.add("db.query", common.STATUS_PASS, f"{len(values)} 条对账 SQL 全部成功")
    return values


def _compare(
    report: common.Report,
    name: str,
    left: Any,
    right: Any,
    detail: str,
    tier: str = common.TIER_REQUIRED,
) -> None:
    """比较两个计数并登记结论：相等通过，不等失败（附两侧实际值）。"""
    ok = left is not None and right is not None and int(left) == int(right)
    report.add(
        name,
        common.STATUS_PASS if ok else common.STATUS_FAIL,
        f"{detail}：{left} vs {right}" + ("" if ok else "（不一致）"),
        tier=tier,
        left=left,
        right=right,
    )


def check_pending(report: common.Report, client: common.HttpClient, values: dict[str, Any]) -> None:
    """pending 自洽：状态之和 = 总数；接口条数 = pending 行数；file_missing 必须有路径。"""
    _compare(
        report,
        "pending.status_sum",
        values.get("pending_status_sum"),
        values.get("pending_total"),
        "各 status 之和 = 总行数",
    )
    status_code, payload = client.get_json("/api/pending")
    if status_code == 200:
        api_items = len((payload or {}).get("items") or [])
        _compare(
            report,
            "pending.api_vs_sql",
            api_items,
            values.get("pending_pending"),
            "GET /api/pending 条数 = SQL pending 行数",
            tier=common.TIER_ADVISORY,
        )
    else:
        report.add(
            "pending.api_vs_sql",
            common.STATUS_UNVERIFIED,
            f"GET /api/pending 返回 {status_code}",
            tier=common.TIER_ADVISORY,
        )
    no_path = values.get("pending_file_missing_no_path")
    report.add(
        "pending.file_missing_has_path",
        common.STATUS_PASS if no_path == 0 else common.STATUS_FAIL,
        f"reason=file_missing 但无 file_path 的行数 {no_path}"
        + ("" if no_path == 0 else "（应归为 no_file，说明标记逻辑或历史数据有误）"),
        count=no_path,
    )


def check_favorites(report: common.Report, client: common.HttpClient, values: dict[str, Any]) -> None:
    """收藏/下载自洽：接口条数不超过表总数；下载表不得有孤儿行。"""
    status_code, payload = client.get_json("/api/favorites")
    api_count = len((payload or {}).get("favorites") or []) if status_code == 200 else None
    total = values.get("favorites_total")
    if api_count is None or total is None:
        report.add(
            "favorites.api_vs_sql",
            common.STATUS_UNVERIFIED,
            f"无法对账（接口 {status_code}，SQL 值 {total}）",
            tier=common.TIER_ADVISORY,
        )
    else:
        # 接口按当前用户过滤，故只要求 ≤ 表总数（相等说明单用户部署）
        ok = int(api_count) <= int(total)
        report.add(
            "favorites.api_vs_sql",
            common.STATUS_PASS if ok else common.STATUS_FAIL,
            f"接口返回 {api_count} 条 ≤ 表总数 {total} 条"
            + ("" if ok else "（接口返回多于表内总数，口径不一致）"),
            tier=common.TIER_ADVISORY,
            api=api_count,
            sql=total,
        )
    orphan = values.get("favorite_downloads_orphan")
    report.add(
        "favorite_downloads.orphan",
        common.STATUS_PASS if orphan == 0 else common.STATUS_FAIL,
        f"favorite_downloads 孤儿行 {orphan} 条（favorite_id 指向不存在的收藏）",
        tier=common.TIER_REQUIRED,
        count=orphan,
    )


def check_announcements(report: common.Report, client: common.HttpClient, values: dict[str, Any]) -> None:
    """公告记录自洽：`/api/announce/stats` 与 SQL 一致；fresh 行不得重复。"""
    status_code, payload = client.get_json("/api/announce/stats")
    if status_code == 200:
        total = (payload or {}).get("total") or {}
        _compare(
            report,
            "announce.stats_total",
            total.get("all"),
            values.get("announcement_record"),
            "/api/announce/stats total.all = SQL COUNT(*)",
        )
        _compare(
            report,
            "announce.stats_matched",
            (payload or {}).get("matched"),
            values.get("announcement_matched"),
            "/api/announce/stats matched = SQL matched=1",
        )
    else:
        report.add(
            "announce.stats_total",
            common.STATUS_UNVERIFIED,
            f"GET /api/announce/stats 返回 {status_code}",
            tier=common.TIER_ADVISORY,
        )
    dup = values.get("announcement_fresh_dup")
    report.add(
        "announce.fresh_duplicates",
        common.STATUS_PASS if dup == 0 else common.STATUS_FAIL,
        f"data_state='fresh' 的重复 (source_site, announce_no, standard_number) 组数 {dup}"
        + ("" if dup == 0 else "（fresh 行应唯一，重复会导致统计膨胀）"),
        tier=common.TIER_ADVISORY,
        count=dup,
    )


def check_file_index(report: common.Report, client: common.HttpClient, values: dict[str, Any]) -> None:
    """文件索引自洽：状态之和 = 总数；`/api/stats` 四项必须落在 SQL 口径内。"""
    _compare(
        report,
        "file_index.status_sum",
        values.get("file_index_status_sum"),
        values.get("file_index_total"),
        "各 status 之和 = 总行数",
    )
    status_code, payload = client.get_json("/api/stats")
    if status_code != 200:
        report.add(
            "file_index.api_stats",
            common.STATUS_UNVERIFIED,
            f"GET /api/stats 返回 {status_code}",
            tier=common.TIER_ADVISORY,
        )
        return
    # `/api/stats` 只汇总 现行/废止(含被代替)/待确认/即将实施 四类，其余状态不计入
    api_sum = sum(int((payload or {}).get(k) or 0) for k in ("current", "expired", "pending", "upcoming"))
    total = values.get("file_index_total")
    ok = total is not None and api_sum <= int(total)
    report.add(
        "file_index.api_stats",
        common.STATUS_PASS if ok else common.STATUS_FAIL,
        f"/api/stats 四项之和 {api_sum} ≤ 表总数 {total}"
        + ("" if ok else "（四项之和超过表内总行数，口径不一致）"),
        tier=common.TIER_ADVISORY,
        api_sum=api_sum,
        sql_total=total,
    )


def check_notification_log(report: common.Report, client: common.HttpClient, values: dict[str, Any]) -> None:
    """通知日志自洽：接口 `total` = SQL `COUNT(*)`。"""
    status_code, payload = client.get_json("/api/notification/logs", params={"page_size": 1})
    if status_code != 200:
        report.add(
            "notification_log.api_vs_sql",
            common.STATUS_UNVERIFIED,
            f"GET /api/notification/logs 返回 {status_code}",
            tier=common.TIER_ADVISORY,
        )
        return
    _compare(
        report,
        "notification_log.api_vs_sql",
        (payload or {}).get("total"),
        values.get("notification_log_total"),
        "/api/notification/logs total = SQL COUNT(*)",
        tier=common.TIER_ADVISORY,
    )


def run(options: common.ProbeOptions, session=None) -> common.Report:
    """执行本 probe：登录 admin → 批量对账 SQL → 逐组核对。"""
    creds = common.read_creds()
    base_url = common.resolve_base_url(options.base_url, creds)
    report = common.Report("db_counts", base_url)
    client = common.HttpClient(base_url, timeout=options.timeout, session=session, creds=creds)
    try:
        status_code, _ = client.get_json("/api/health")
    except common.EnvironmentUnreachable as exc:
        report.unreachable_reason = str(exc)
        report.add("health.reachable", common.STATUS_UNVERIFIED, f"环境不可达：{exc}")
        return report
    if status_code != 200:
        report.add("health.reachable", common.STATUS_UNVERIFIED, f"/api/health 返回 {status_code}")
        return report
    try:
        login_detail = client.require_admin()
        report.add("auth.admin", common.STATUS_PASS, login_detail)
    except common.AuthError as exc:
        report.add(
            "auth.admin",
            common.STATUS_UNVERIFIED,
            f"{exc}；所需条件：admin 账号（只读 SQL 端点 POST /query 要求 admin 角色）",
        )
        return report

    values = collect_counts(report, client)
    if not values:
        # 一条都没跑通时不再往下判，避免用 None 造出「全绿」的假象
        return report
    check_pending(report, client, values)
    check_favorites(report, client, values)
    check_announcements(report, client, values)
    check_file_index(report, client, values)
    check_notification_log(report, client, values)
    return report


def main(argv: list[str] | None = None) -> int:
    """命令行入口：解析参数 → 跑探测 → 按退出码语义返回。"""
    common.stdout_utf8()
    parser = argparse.ArgumentParser(description="部署探测：统计表对账（只读 SQL）")
    common.add_common_args(parser)
    args = parser.parse_args(argv)
    options = common.ProbeOptions(base_url=args.base_url, timeout=args.timeout, strict=args.strict)
    report = run(options)
    if report.unreachable_reason:
        common.finish(report, args)
        return common.EXIT_UNREACHABLE
    return common.finish(report, args)


if __name__ == "__main__":
    sys.exit(main())
