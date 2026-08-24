#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""事件通知全链路审计工具（Vibe Coding 治理样板 · 可复用）· 入口。

纯静态分析（不连接数据库、不发网络请求），仅使用 Python 标准库。
扫描逻辑位于 audit_notification_chain_scan.py，本文件负责：
  1. 命令行参数解析
  2. 调用扫描库提取事件/构建器/调用点/吞错
  3. 按模块前缀过滤 + 问题聚合
  4. 输出（人类可读文本或结构化 JSON）

用法：
  python scripts/audit_notification_chain.py                 # 全量审计
  python scripts/audit_notification_chain.py --module favorite
  python scripts/audit_notification_chain.py --json -o out.json

退出码：0 = 无问题；1 = 发现问题（含缺守卫/吞错/空串风险）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from audit_notification_chain_scan import (
    EVENTS_FILE,
    MODULE_KEYWORDS,
    ROOT,
    detect_swallowed_exceptions,
    extract_builders,
    extract_call_sites,
    extract_events,
)

# ── 主流程 ─────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    """解析命令行参数并返回参数对象。"""
    parser = argparse.ArgumentParser(
        description="事件通知全链路静态审计（纯标准库，不连数据库/网络）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  python scripts/audit_notification_chain.py\n"
            "  python scripts/audit_notification_chain.py --module favorite\n"
            "  python scripts/audit_notification_chain.py --json -o audit.json\n"
            "退出码：0=无问题 1=发现问题"
        ),
    )
    parser.add_argument(
        "--module", "-m", default="",
        help="模块前缀过滤：favorite/download/archive/announce/query/validity/scan/normalize/backup",
    )
    parser.add_argument(
        "--scope", default="notification", choices=["notification", "all"],
        help="吞错扫描范围：notification=仅通知目录（默认），all=全库",
    )
    parser.add_argument("--json", action="store_true", help="输出结构化 JSON")
    parser.add_argument("-o", "--output", default="", help="JSON 输出文件路径（与 --json 搭配）")
    return parser.parse_args()


def _match_module(key: str | None, keywords: tuple[str, ...] | None) -> bool:
    """判断事件名或构建器名是否命中模块前缀过滤（无过滤时全部通过）。"""
    if not key:
        return True
    if keywords is None:
        return True
    return any(k in key for k in keywords)


def _collect_problems(builders: list[dict], exceptions: list[dict]) -> list[dict]:
    """聚合构建器与吞错扫描发现的问题清单。"""
    problems: list[dict] = []
    for b in builders:
        if b["missing_null_guards"]:
            problems.append(
                {
                    "severity": "P2",
                    "type": "missing_null_guard",
                    "message": f"构建器 {b['builder']} 对字段 {b['missing_null_guards']} 无空值守卫",
                    "file": b["file"],
                    "lineno": b["lineno"],
                }
            )
        if b["empty_text_risk"]:
            problems.append(
                {
                    "severity": "P1",
                    "type": "empty_text_risk",
                    "message": f"构建器 {b['builder']} 未填充 body 字段或存在空串返回（聚合/回退路径可能渲染空文本）",
                    "file": b["file"],
                    "lineno": b["lineno"],
                }
            )
    for exc in exceptions:
        problems.append(
            {
                "severity": exc["severity"],
                "type": "swallowed_exception",
                "message": f"静默吞错 {exc['pattern']}",
                "file": exc["file"],
                "lineno": exc["lineno"],
            }
        )
    return problems


def _build_report(
    module: str,
    events: list[dict],
    builders: list[dict],
    call_sites: list[dict],
    exceptions: list[dict],
    problems: list[dict],
) -> dict:
    """按事件/构建器/调用点/问题组装结构化报告。"""
    return {
        "tool": "audit_notification_chain",
        "module_filter": module or "all",
        "scan_root": str(ROOT),
        "summary": {
            "events": len(events),
            "builders": len(builders),
            "call_sites": len(call_sites),
            "swallowed_exceptions": len(exceptions),
            "problems": len(problems),
            "p0": sum(1 for p in problems if p["severity"] == "P0"),
            "p1": sum(1 for p in problems if p["severity"] == "P1"),
            "p2": sum(1 for p in problems if p["severity"] == "P2"),
        },
        "events": events,
        "builders": builders,
        "call_sites": call_sites,
        "problems": problems,
    }


def _render_text(report: dict) -> None:
    """以人类可读文本形式输出审计结果。"""
    module = report["module_filter"]
    summary = report["summary"]
    print("═" * 70)
    print(f"事件通知全链路审计  module={module}  根目录={ROOT}")
    print("═" * 70)
    print(
        f"事件数: {summary['events']}  构建器数: {summary['builders']}  "
        f"调用点数: {summary['call_sites']}"
    )
    print(f"吞错模式: {summary['swallowed_exceptions']}  问题总数: {summary['problems']}")
    print()
    if report["events"]:
        print("── 事件清单 ──")
        for e in report["events"]:
            flag = " [bypass聚合]" if e.get("bypass_aggregation") else ""
            print(f"  {e['key']}{flag}")
    if report["builders"]:
        print()
        print("── 构建器映射 ──")
        for b in report["builders"]:
            print(
                f"  {b['builder']:<45} → {b.get('event_type') or '?'}  "
                f"[{b['file']}:{b['lineno']}]"
            )
    if report["call_sites"]:
        print()
        print("── 调用点 ──")
        for s in report["call_sites"]:
            print(f"  {s['file']}:{s['lineno']}  {s['function']}({s.get('event_type') or '?'})")
    if report["problems"]:
        print()
        print("── 问题清单 ──")
        for p in report["problems"]:
            print(
                f"  [{p['severity']}] {p['type']:<22} {p['file']}:{p['lineno']}  {p['message']}"
            )
    print()
    print("退出码:", 1 if report["problems"] else 0)


def main() -> int:
    args = _parse_args()

    # 模块过滤：无 --module 时全量审计；关键词表未命中时按原词做子串匹配
    module = (args.module or "").strip().lower()
    keywords = MODULE_KEYWORDS.get(module, (module,)) if module else None

    # 四路扫描并行收集（均为纯静态 AST 分析，无网络/DB 依赖）
    events = extract_events(EVENTS_FILE)
    builders = extract_builders()
    exceptions = detect_swallowed_exceptions(args.scope)
    call_sites = extract_call_sites()

    # 按模块前缀过滤（构建器以事件名或函数名兜底匹配）
    events = [e for e in events if _match_module(e["key"], keywords)]
    builders = [b for b in builders if _match_module(b.get("event_type") or b["builder"], keywords)]
    call_sites = [s for s in call_sites if _match_module(s.get("event_type"), keywords)]

    problems = _collect_problems(builders, exceptions)
    report = _build_report(module, events, builders, call_sites, exceptions, problems)

    # 输出分流：--json 供其他工具解析，默认人类可读文本
    if args.json:
        text = json.dumps(report, ensure_ascii=False, indent=2)
        if args.output:
            Path(args.output).write_text(text, encoding="utf-8")
            print(f"报告已写入: {args.output}")
        else:
            print(text)
    else:
        _render_text(report)

    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
