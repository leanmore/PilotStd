#!/usr/bin/env python3
"""批次 1 部署判据自检：把 22 项「已修复（待部署）」变成一键验证（只读）。

## 为什么需要这个 probe

`docs/debt/06-full-inventory.md` 的批次 1 是「22 项已修但**待部署验证**」。
此前每项要手工按各自判据去生产复验，无法一次跑完 —— 于是这批**长期悬着**。

本 probe 把每项的**可自动化判据**变成一条检查：

| 项 | 判据 |
|---|---|
| G-14 | `GET /api/health` 可用（配置多实例覆盖写已修） |
| G-21 | `GET /api/announcements` 返回 `total` 字段（服务端分页已生效） |
| G-22 | `GET /api/system/archive-stats` 存在且返回 HTML/附件统计 |
| G-29 | `PUT /api/notification/menu/config` 端点存在（OPTIONS 探测） |
| G-36 | `GET /api/system/quarantine-stats` 存在 |
| G-37 | `GET /api/notification/menu/chats` 存在 |
| G-42 | `POST /query` 可查 `query_metrics` 表（指标落表已生效） |
| G-44 | `GET /api/notification/logs` 可返回（零渠道 skipped 行可见） |
| G-46 | 渠道能力矩阵端点/字段可读 |
| G-47 | 菜单客户端注册表（间接：G-29/G-37 端点齐备） |
| G-48 | `POST /api/pending/mark-missing` 端点存在（OPTIONS 探测） |

**只读保证**：写端点一律只发 `OPTIONS` 探测存在性，**从不 POST**；
读端点只发 `GET`；`/query` 只发单条 `SELECT`（共享层有 AST 级只读校验）。

**不可自动化项**（需人工，报告中列为 `unverified` 并说明原因）：
- G-15 深色主题对比度：需 Playwright 渲染实测（本地已有 30 例锁定）
- G-17/G-19 空目录清理：需真实目录操作（本地 52 例锁定）
- G-18 抓取起始日期：需观察实际抓取行为
- G-20 四主题配色：需视觉核对（本地 `theme-spec.test.ts` 30 例锁定）
- G-23 界面语言下拉：需前端渲染
- G-34 修改单解析：需真实公告正文
- G-38/G-39/G-40/G-41 通知渲染：需真实外发一条通知（G-40 明确「需真实外发」）

用法：
  python scripts/ops/probe_batch1.py
  python scripts/ops/probe_batch1.py --base-url http://192.168.1.18:9028 --json
  python scripts/ops/probe_batch1.py --strict     # 不可验证项也算失败

退出码：0 通过 / 1 有失败 / 2 环境不可达。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _probe_common as common  # noqa: E402  共享层（凭据/HTTP/报告）

# 需人工验证的项：编号 → 原因（报告里列为 unverified，说明为什么不能自动化）
MANUAL_ONLY: dict[str, str] = {
    "G-15": "深色主题按钮对比度需 Playwright 渲染实测（本地 theme-spec 已 30 例锁定）",
    "G-17": "空目录自动清理需真实目录操作（本地 52 例锁定）",
    "G-19": "clean-empty 与 monitor 同口径需真实目录（本地用例锁定）",
    "G-18": "公告抓取起始日期需观察实际抓取行为",
    "G-20": "四主题配色需视觉核对（本地 theme-spec.test.ts 30 例锁定）",
    "G-23": "界面语言下拉需前端渲染验证",
    "G-34": "修改单解析需真实公告正文",
    "G-38": "旧状态回填需观察实际检查周期",
    "G-39": "出厂渠道回退需新装用户场景",
    "G-40": "message.link 四渠道渲染**需真实外发一条通知**",
    "G-41": "企微应用形态需真实企微环境",
}


def _endpoint_exists(client: common.HttpClient, path: str) -> tuple[bool, str]:
    """用 `OPTIONS` 探测端点是否存在（**不发写请求**，只读性保证）。"""
    try:
        resp = client.options(path)
    except common.EnvironmentUnreachable:
        raise
    except Exception as exc:  # noqa: BLE001 - 探测失败必须可见，不静默
        return False, f"OPTIONS {path} 异常: {type(exc).__name__}: {exc}"
    code = getattr(resp, "status_code", 0)
    # 405 Method Not Allowed 也说明端点存在（只是不支持 OPTIONS）
    if code in (200, 204, 405):
        return True, f"OPTIONS {path} → {code}"
    if code == 404:
        return False, f"OPTIONS {path} → 404（端点不存在）"
    return False, f"OPTIONS {path} → {code}"


def run(options: common.ProbeOptions, session=None) -> common.Report:
    """执行批次 1 判据自检，返回报告。"""
    creds = common.read_creds()
    base_url = common.resolve_base_url(options.base_url, creds)
    report = common.Report("batch1", base_url)
    client = common.HttpClient(base_url, timeout=options.timeout, session=session, creds=creds)

    # ── 环境可达性前置（不可达则短路，避免每项都超时）──
    try:
        status_code, health = client.get_json("/api/health")
    except common.EnvironmentUnreachable as exc:
        report.unreachable_reason = str(exc)
        report.add("env.reachable", common.STATUS_UNVERIFIED, f"环境不可达：{exc}")
        return report
    if status_code != 200:
        report.add("env.reachable", common.STATUS_FAIL, f"/api/health → {status_code}")
        return report
    report.add("env.reachable", common.STATUS_PASS, f"/api/health → 200 (version={health.get('version', '?')})")

    # ── 需登录的检查：先登录（白名单：仅建会话）──
    login_code, login_msg = client.login()
    logged_in = login_code == 200
    report.add(
        "auth.login",
        common.STATUS_PASS if logged_in else common.STATUS_FAIL,
        login_msg,
    )

    # ── G-21：公告列表服务端分页（必须有 total 字段）──
    if logged_in:
        try:
            # 真实端点是 `/api/announce/results`（服务端分页 + total），
            # 不是 `/api/announcements`（后者只有 status/results/{task_id} 等异步任务端点）。
            code, payload = client.get_json("/api/announce/results?page=1&page_size=1")
            has_total = isinstance(payload, dict) and "total" in payload
            total = (payload or {}).get("total", "?") if isinstance(payload, dict) else "?"
            report.add(
                "G-21.announcements_paging",
                common.STATUS_PASS if has_total else common.STATUS_FAIL,
                f"/api/announce/results → {code}，total={total}",
            )
        except Exception as exc:  # noqa: BLE001
            report.add("G-21.announcements_paging", common.STATUS_FAIL, f"异常：{exc}")

    # ── G-22：归档统计（新增只读端点）──
    if logged_in:
        try:
            code, payload = client.get_json("/api/system/archive-stats")
            ok = code == 200 and isinstance(payload, dict)
            detail = f"/api/system/archive-stats → {code}"
            if ok:
                keys = sorted(payload)[:5]
                detail += f"，字段 {keys}"
            report.add("G-22.archive_stats", common.STATUS_PASS if ok else common.STATUS_FAIL, detail)
        except Exception as exc:  # noqa: BLE001
            report.add("G-22.archive_stats", common.STATUS_FAIL, f"异常：{exc}")

    # ── G-36：隔离区统计 ──
    if logged_in:
        try:
            code, _payload = client.get_json("/api/system/quarantine-stats")
            report.add(
                "G-36.quarantine_stats",
                common.STATUS_PASS if code == 200 else common.STATUS_FAIL,
                f"/api/system/quarantine-stats → {code}",
            )
        except Exception as exc:  # noqa: BLE001
            report.add("G-36.quarantine_stats", common.STATUS_FAIL, f"异常：{exc}")

    # ── G-29 / G-37 / G-48：写端点只做 OPTIONS 探测（绝不 POST）──
    if logged_in:
        for check, path, note in (
            ("G-29.menu_config_endpoint", "/api/notification/menu/config", "菜单配置写入口"),
            ("G-37.menu_chats_endpoint", "/api/notification/menu/chats?channel=feishu", "飞书群发现入口"),
            ("G-48.mark_missing_endpoint", "/api/pending/mark-missing", "mark_missing 入口"),
        ):
            try:
                ok, detail = _endpoint_exists(client, path)
                report.add(check, common.STATUS_PASS if ok else common.STATUS_FAIL, f"{note}：{detail}")
            except Exception as exc:  # noqa: BLE001
                report.add(check, common.STATUS_FAIL, f"{note}：异常 {exc}")

    # ── G-42：query_metrics 落表（只读 SELECT）──
    if logged_in:
        try:
            resp = client.post(
                "/query",
                json={"sql": "SELECT COUNT(*) AS c FROM query_metrics"},
                headers=client.csrf_headers(),
            )
            code = resp.status_code
            payload = common._safe_json(resp)
            rows = (payload or {}).get("rows") if isinstance(payload, dict) else None
            ok = code == 200 and bool(rows)
            count = rows[0].get("c") if ok and isinstance(rows[0], dict) else "?"
            report.add(
                "G-42.query_metrics_persisted",
                common.STATUS_PASS if ok else common.STATUS_FAIL,
                f"query_metrics 行数 = {count}（>0 说明 found/not_found 已落表）",
            )
        except Exception as exc:  # noqa: BLE001
            report.add("G-42.query_metrics_persisted", common.STATUS_FAIL, f"异常：{exc}")

    # ── G-44：通知日志可见（零渠道 skipped 行）──
    if logged_in:
        try:
            code, payload = client.get_json("/api/notification/logs?page=1&page_size=1")
            ok = code == 200 and isinstance(payload, dict) and "total" in payload
            report.add(
                "G-44.notification_logs",
                common.STATUS_PASS if ok else common.STATUS_FAIL,
                f"/api/notification/logs → {code}，total={(payload or {}).get('total', '?')}",
            )
        except Exception as exc:  # noqa: BLE001
            report.add("G-44.notification_logs", common.STATUS_FAIL, f"异常：{exc}")

    # ── G-46：渠道能力矩阵（间接：G-29/G-37 端点齐备即说明注册表已接线）──
    report.add(
        "G-46.channel_capabilities",
        common.STATUS_UNVERIFIED,
        "渠道能力矩阵需读代码侧 channel_capabilities()；本地 4 例测试锁定，生产无独立端点",
        tier=common.TIER_ADVISORY,
    )

    # ── G-14 / G-47：间接验证（健康可用 + 相关端点齐备）──
    report.add(
        "G-14.config_update_api",
        common.STATUS_UNVERIFIED,
        "配置 update/update_many 是进程内行为；本地 test_manager_update 4 例锁定，生产无独立端点",
        tier=common.TIER_ADVISORY,
    )
    report.add(
        "G-47.menu_client_registry",
        common.STATUS_UNVERIFIED,
        "菜单客户端注册表是进程内实现；G-29/G-37 端点齐备即间接证明已接线",
        tier=common.TIER_ADVISORY,
    )

    # ── 需人工验证的 11 项 ──
    for item, reason in MANUAL_ONLY.items():
        report.add(
            f"{item}.manual", common.STATUS_UNVERIFIED, reason, tier=common.TIER_ADVISORY
        )

    return report


def main() -> int:
    """入口：解析参数、跑自检、按 `--json` 输出并返回退出码。"""
    common.stdout_utf8()
    parser = argparse.ArgumentParser(description="批次 1 部署判据自检（只读）")
    common.add_common_args(parser)
    args = parser.parse_args()
    options = common.ProbeOptions(
        base_url=args.base_url,
        timeout=args.timeout,
        max_items=getattr(args, "max_items", 5),
    )
    report = run(options)
    return common.finish(report, args, title="批次 1 部署判据自检")


if __name__ == "__main__":
    raise SystemExit(main())
