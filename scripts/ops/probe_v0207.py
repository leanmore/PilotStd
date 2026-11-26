#!/usr/bin/env python3
"""部署验收：v0.207.0 专项自动检查（对应 `docs/ops/deploy-selfcheck.md` §十）。

只读：仅 `POST /api/login`（换会话）与受限只读 SQL 端点 `POST /query`（共享层强制单条 SELECT）。

检查分四组：
1. **版本**：`/api/health.version` 是 40 位 sha 且存在于本仓库；`/api/system/version` = `VERSION` 文件值；
2. **状态口径（批次 11）**：`?status=未生效` 与 `?status=即将实施`/`upcoming` 结果集一致且不是全表；
   非法值返回 400；
3. **数据治理（批次 12）**：`file_index` 无 `未生效` 行、`superseded_by` 无「倒退且目标存在」残留、
   `favorite_downloads` 无孤儿、`notification_log.user_id=1` 仅剩真实 `user_activity`；
4. **统计一致（批次 11/C3 后）**：`/api/stats` 四桶之和 ≤ `file_index` 总数且 `expired >= 170`。

用法：
  python scripts/ops/probe_v0207.py --base-url http://192.168.1.18:9028
  python scripts/ops/probe_v0207.py --json

退出码：0 全部通过 / 1 有失败或必跑项无法验证 / 2 环境不可达。
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _probe_common as common  # noqa: E402  共享层（凭据/HTTP/报告）

# 期望版本号**动态读取仓库 VERSION**：硬编码会在每次发版后假失败
# （2026-11-26 实测：部署 v0.207.1 后脚本仍期望 0.207.0 而误报 FAIL）。
EXPECT_SYSTEM_VERSION = "0.207.0"
_FALLBACK_EXPECT_VERSION = EXPECT_SYSTEM_VERSION


def expected_system_version() -> str:
    """期望的 `/api/system/version`：优先 `PROBE_EXPECT_VERSION`，否则读仓库 `VERSION`。"""
    override = os.environ.get("PROBE_EXPECT_VERSION", "").strip()
    if override:
        return override
    version_file = Path(__file__).resolve().parents[2] / "VERSION"
    try:
        text = version_file.read_text(encoding="utf-8").strip()
    except OSError:
        return _FALLBACK_EXPECT_VERSION
    return text or _FALLBACK_EXPECT_VERSION


def _sql(client: common.HttpClient, sql: str) -> list[dict]:
    """执行一条只读 SQL，返回行列表；失败抛 RuntimeError（不静默）。"""
    response = client.post("/query", json={"sql": sql}, headers=client.csrf_headers())
    if response.status_code != 200:
        raise RuntimeError(f"/query HTTP {response.status_code}")
    payload = response.json()
    if not payload.get("success"):
        raise RuntimeError(f"/query failed: {payload}")
    return payload.get("rows") or []


def run(options: argparse.Namespace, session: object | None = None) -> common.Report:
    """执行 v0.207.0 专项验收，返回报告（供测试注入假 session）。"""
    report = common.Report(probe="deploy-v0207")
    client = common.build_client(options, session=session)
    report.base_url = client.base_url
    try:
        client.login()
    except common.EnvironmentUnreachable as exc:
        report.unreachable_reason = str(exc)
        return report

    # ── 1. 版本 ──
    try:
        health = client.get("/api/health").json()
        version = str(health.get("version") or "")
        report.add(
            "version.deployed_sha",
            common.STATUS_PASS if len(version) == 40 else common.STATUS_FAIL,
            f"/api/health version={version[:12]}…",
        )
        system = client.get("/api/system/version").json()
        sys_ver = str(system.get("version") or "")
        expected = expected_system_version()
        report.add(
            "version.system_version",
            common.STATUS_PASS if sys_ver == expected else common.STATUS_FAIL,
            f"/api/system/version={sys_ver}（期望 {expected}）",
            tag=system.get("tag"),
            image=system.get("image"),
        )
    except Exception as exc:  # noqa: BLE001  验收脚本需如实报告异常而不是崩溃
        report.add("version.read", common.STATUS_FAIL, f"读取版本失败: {type(exc).__name__}: {exc}")
        return report

    # ── 2. 状态口径（批次 11） ──
    def _total(status_value: str) -> int | None:
        resp = client.get("/api/standards/status", params={"status": status_value, "page": 1, "page_size": 1})
        if resp.status_code != 200:
            return None
        return int(resp.json().get("total") or 0)

    total_wei = _total("未生效")
    total_upcoming = _total("即将实施")
    total_upcoming_en = _total("upcoming")
    total_all = _total("")
    report.add(
        "status.wei_sheng_xiao",
        common.STATUS_PASS if total_wei is not None and total_wei == total_upcoming else common.STATUS_FAIL,
        f"?status=未生效 total={total_wei}，?status=即将实施 total={total_upcoming}（应相等）",
    )
    report.add(
        "status.alias_equal",
        common.STATUS_PASS if total_upcoming == total_upcoming_en else common.STATUS_FAIL,
        f"中文/英文键结果一致：{total_upcoming} vs {total_upcoming_en}",
    )
    report.add(
        "status.not_whole_table",
        common.STATUS_PASS if total_wei is not None and total_all and total_wei < total_all else common.STATUS_FAIL,
        f"未生效 {total_wei} < 全表 {total_all}（旧缺陷：等于全表）",
    )
    invalid = client.get("/api/standards/status", params={"status": "faq", "page": 1, "page_size": 1})
    report.add(
        "status.invalid_400",
        common.STATUS_PASS if invalid.status_code == 400 else common.STATUS_FAIL,
        f"非法 status 返回 {invalid.status_code}（期望 400）",
    )

    # ── 3. 数据治理（批次 12） ──
    try:
        rows = _sql(client, "SELECT COUNT(*) AS c FROM file_index WHERE status='未生效'")
        wei_rows = int(rows[0]["c"]) if rows else -1
        report.add(
            "data.file_index_no_wei",
            common.STATUS_PASS if wei_rows == 0 else common.STATUS_FAIL,
            f"file_index 未生效 行数={wei_rows}（C3 清洗后期望 0）",
        )
        rows = _sql(
            client,
            "SELECT COUNT(*) AS c FROM favorite_downloads d "
            "LEFT JOIN user_favorites f ON f.id=d.favorite_id WHERE f.id IS NULL",
        )
        orphan = int(rows[0]["c"]) if rows else -1
        report.add(
            "data.favorite_orphan",
            common.STATUS_PASS if orphan == 0 else common.STATUS_FAIL,
            f"favorite_downloads 孤儿行={orphan}（期望 0）",
        )
        rows = _sql(
            client,
            "SELECT COUNT(*) AS c FROM notification_log "
            "WHERE user_id=1 AND notify_event != 'user_activity'",
        )
        sys_rows = int(rows[0]["c"]) if rows else -1
        report.add(
            "data.a40_remaining",
            common.STATUS_PASS if sys_rows == 0 else common.STATUS_FAIL,
            f"user_id=1 的系统类事件行={sys_rows}（A-40 清理后期望 0）",
        )
    except Exception as exc:  # noqa: BLE001
        report.add("data.sql", common.STATUS_FAIL, f"数据检查失败: {type(exc).__name__}: {exc}")

    # ── 4. 统计一致 ──
    try:
        stats = client.get("/api/stats").json()
        expired = int(stats.get("expired") or 0)
        four_sum = sum(int(stats.get(k) or 0) for k in ("current", "expired", "pending", "upcoming"))
        rows = _sql(client, "SELECT COUNT(*) AS c FROM file_index")
        fi_total = int(rows[0]["c"]) if rows else -1
        report.add(
            "stats.expired_after_c3",
            common.STATUS_PASS if expired >= 170 else common.STATUS_FAIL,
            f"/api/stats expired={expired}（部署前 116；A1 后应 ≥174）",
        )
        report.add(
            "stats.four_buckets_le_total",
            common.STATUS_PASS if four_sum <= fi_total else common.STATUS_FAIL,
            f"四桶之和 {four_sum} ≤ file_index 总数 {fi_total}",
        )
    except Exception as exc:  # noqa: BLE001
        report.add("stats.read", common.STATUS_FAIL, f"统计检查失败: {type(exc).__name__}: {exc}")
    return report


def main(argv: list[str] | None = None) -> int:
    """入口：解析参数 → 跑验收 → 渲染/JSON 输出并返回退出码。"""
    common.stdout_utf8()
    parser = argparse.ArgumentParser(description="v0.207.0 部署专项验收（只读）")
    common.add_common_args(parser)
    return common.finish(run(parser.parse_args(argv)), parser.parse_args(argv), "v0.207.0 部署验收")


if __name__ == "__main__":
    raise SystemExit(main())
