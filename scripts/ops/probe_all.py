#!/usr/bin/env python3
"""一键部署自检：串起 health / pending_paths / credentials / db_counts 四个只读探测。

设计取舍：

  * **不重新实现**任何探测逻辑——直接调用各 probe 的 `run(options, session)`，共用同一个
    已登录会话（省掉 4 次登录），也保证单跑与合跑口径完全一致；
  * **环境不可达短路**：`/api/health` 连不上时不再逐个跑（每个都会超时），直接给退出码 2
    并打印具体原因（`G-050` 口径：失败必须可见，不静默）；
  * **汇总表**：按「必跑 / 诊断」两级列出每个 probe 的通过/失败/无法验证条数，末尾给
    「阻断项清单」，可直接贴进部署记录；
  * `--json` 输出单一 JSON（含每个 probe 的明细），供 CI 消费。

用法：
  python scripts/ops/probe_all.py                                    # 对默认地址跑全部
  python scripts/ops/probe_all.py --base-url http://192.168.1.18:9028
  python scripts/ops/probe_all.py --json > report.json
  python scripts/ops/probe_all.py --only health,pending_paths        # 只跑子集

退出码：0 全部通过 / 1 有失败或必跑项无法验证 / 2 环境不可达。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _probe_common as common  # noqa: E402  共享层（凭据/HTTP/报告）

# 子探测注册表：名称 → 模块名（延迟 import，避免单个 probe 的依赖影响 --help）
PROBES = {
    "health": "probe_health",
    "pending_paths": "probe_pending_paths",
    "credentials": "probe_credentials",
    "db_counts": "probe_db_counts",
}


def _load(name: str):
    """按名称导入子 probe 模块（同目录模块，`sys.path` 已注入 scripts/ops）。"""
    import importlib

    return importlib.import_module(PROBES[name])


def _select(names: str) -> list[str]:
    """解析 `--only`：逗号分隔，校验名称合法；空串表示全部。"""
    if not names.strip():
        return list(PROBES)
    picked = [part.strip() for part in names.split(",") if part.strip()]
    unknown = [part for part in picked if part not in PROBES]
    if unknown:
        raise SystemExit(f"未知探测名 {unknown}；可选 {list(PROBES)}")
    return picked


def _reachable(options: common.ProbeOptions, session) -> tuple[bool, str]:
    """先探一次 `/api/health`：不可达时给出原因，避免后续 4 个 probe 各等一次超时。"""
    creds = common.read_creds()
    base_url = common.resolve_base_url(options.base_url, creds)
    client = common.HttpClient(base_url, timeout=options.timeout, session=session, creds=creds)
    try:
        status_code, payload = client.get_json("/api/health")
    except common.EnvironmentUnreachable as exc:
        return False, f"{base_url} 不可达：{exc}"
    if status_code not in (200, 207):
        return False, f"{base_url}/api/health 返回 {status_code}（期望 200/207）"
    return True, f"{base_url} 可达（status={(payload or {}).get('status')}）"


def run_all(options: common.ProbeOptions, names: list[str], session=None) -> tuple[list[common.Report], str]:
    """依次跑选中的 probe，返回 `(报告列表, 不可达原因)`；不可达时报告列表为空。"""
    ok, reason = _reachable(options, session)
    if not ok:
        return [], reason
    reports: list[common.Report] = []
    for name in names:
        module = _load(name)
        # 每个 probe 共用同一个 session：登录一次即可，且便于测试注入假会话
        reports.append(module.run(options, session=session))
    return reports, ""


def summarize(reports: list[common.Report], strict: bool) -> dict:
    """汇总各 probe 的计数与阻断项，返回可直接 JSON 序列化的字典。"""
    summary = {
        "probes": [],
        "blocking": [],
        "exit_code": common.EXIT_OK,
    }
    for report in reports:
        blocking = report.blocking(strict)
        summary["probes"].append(
            {
                "probe": report.probe,
                "base_url": report.base_url,
                "counts": report.as_dict(strict)["counts"],
                "blocking": [c.name for c in blocking],
            }
        )
        summary["blocking"].extend(f"{report.probe}:{c.name}（{c.status}）{c.detail}" for c in blocking)
    summary["exit_code"] = common.EXIT_FAIL if summary["blocking"] else common.EXIT_OK
    return summary


def render_summary(reports: list[common.Report], summary: dict) -> None:
    """打印人读汇总：每个 probe 一行 + 阻断项清单 + 判读提示。"""
    print("=" * 78)
    print("PilotStd 部署自检汇总（只读）")
    print("=" * 78)
    print(f"{'探测':<16}{'通过':>6}{'失败':>6}{'无法验证':>8}{'不适用':>8}  阻断项")
    for item in summary["probes"]:
        counts = item["counts"]
        blocking = "、".join(item["blocking"]) or "-"
        print(
            f"{item['probe']:<16}{counts['pass']:>6}{counts['fail']:>6}"
            f"{counts['unverified']:>10}{counts['skip']:>9}  {blocking}"
        )
    print("-" * 78)
    if summary["blocking"]:
        print(f"阻断项 {len(summary['blocking'])} 条（上线前必须清零）：")
        for line in summary["blocking"]:
            print(f"  - {line}")
    else:
        print("无阻断项：所有必跑项通过。")
    print("-" * 78)
    print("判读：pass=通过；fail=明确不通过；unverified=条件不足无法验证（不假装通过，需补齐条件）")
    print(f"退出码 {summary['exit_code']}（0 通过 / 1 有失败或必跑项无法验证 / 2 环境不可达）")


def main(argv: list[str] | None = None) -> int:
    """命令行入口：解析参数 → 逐 probe 执行 → 汇总输出 → 返回退出码。"""
    common.stdout_utf8()
    parser = argparse.ArgumentParser(description="PilotStd 部署自检一键入口（全部只读）")
    common.add_common_args(parser)
    parser.add_argument(
        "--only",
        default="",
        help=f"只跑指定探测（逗号分隔，可选 {','.join(PROBES)}；默认全部）",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=20,
        help="pending 路径抽样条数（透传给 probe_pending_paths，默认 20）",
    )
    parser.add_argument(
        "--allow-unconfigured-channels",
        action="store_true",
        help="把「渠道未启用且未配置」记为不适用（skip）而不是无法验证；默认关闭（不假装通过）",
    )
    args = parser.parse_args(argv)
    names = _select(args.only)
    options = common.ProbeOptions(
        base_url=args.base_url,
        timeout=args.timeout,
        max_items=args.max_items,
        strict=args.strict,
        include_advisory=True,
        allow_unconfigured_channels=args.allow_unconfigured_channels,
    )
    reports, unreachable = run_all(options, names)
    if unreachable:
        # 环境不可达：不逐个跑（每个都会超时），明确打印原因并给退出码 2
        print(f"[UNREACHABLE] {unreachable}", file=sys.stderr)
        print("退出码 2（环境不可达，不计为探测失败；请确认容器已启动、网络可达）", file=sys.stderr)
        if args.json:
            print(
                json.dumps(
                    {
                        "probe": "all",
                        "base_url": options.base_url,
                        "unreachable": unreachable,
                        "exit_code": common.EXIT_UNREACHABLE,
                        "probes": [],
                        "blocking": [],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        return common.EXIT_UNREACHABLE

    summary = summarize(reports, args.strict)
    if args.json:
        print(
            json.dumps(
                {
                    "probe": "all",
                    "base_url": reports[0].base_url if reports else options.base_url,
                    "unreachable": "",
                    "exit_code": summary["exit_code"],
                    "summary": summary,
                    "details": [report.as_dict(args.strict) for report in reports],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        for report in reports:
            report.render()
            print()
        render_summary(reports, summary)
    return int(summary["exit_code"])


if __name__ == "__main__":
    sys.exit(main())
