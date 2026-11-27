#!/usr/bin/env python3
"""P0 聚合搜索「站点 × 查询类型」矩阵验证（3 站抽样，默认不联网）。

目的：在开并发之前先摸清各站对「精确号 / 半精确 / 关键词模糊」的真实支持度与延迟，
作为 `AggregationService` 候选站点与置信度的输入依据（报告见 `docs/plans/2026-11-27-aggregate-matrix-3sites.md`）。

用法：
  python scripts/query_aggregate_matrix.py                 # 只打印计划（零网络，CI 可跑）
  python scripts/query_aggregate_matrix.py --live          # 真实联网验证（手动执行）
  python scripts/query_aggregate_matrix.py --live --sites std_gov,dbba,api_webstore

退出码：0 正常（离线或联网完成）；2 参数/环境不可用。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 三站抽样：国标综合 / 地方标准库 / 国际特色（POST 检索）
DEFAULT_SITES = ("std_gov", "dbba", "api_webstore")

# 每站的查询用例：精确号 / 半精确（缺年份或空格差异） / 关键词模糊
CASES: dict[str, list[tuple[str, str]]] = {
    "std_gov": [
        ("exact", "GB/T 1.1-2020"),
        ("semi", "GB/T 1.1"),
        ("keyword", "压力容器"),
    ],
    "dbba": [
        ("exact", "DB50/T 950-2026"),
        ("semi", "DB50/T 950"),
        ("keyword", "地方标准"),
    ],
    "api_webstore": [
        ("exact", "API 610-2004"),
        ("semi", "API 610"),
        ("keyword", "centrifugal pump"),
    ],
}


def _build_adapters(names: tuple[str, ...]) -> dict[str, Any]:
    """只实例化矩阵需要的站点（避免全网实例化）。"""
    from pilotstd.query.adapters.registry import ALL_ADAPTERS

    adapters: dict[str, Any] = {}
    for name in names:
        cls = ALL_ADAPTERS.get(name)
        if cls is None:
            print(f"[WARN] 未注册站点: {name}")
            continue
        try:
            adapters[name] = cls()
        except Exception as exc:  # noqa: BLE001  矩阵脚本需如实报告异常
            print(f"[WARN] {name} 实例化失败: {type(exc).__name__}: {exc}")
    return adapters


def run_live(sites: tuple[str, ...], output_json: Path) -> int:
    """真实联网跑矩阵；结果写 JSON 并打印表格。"""
    adapters = _build_adapters(sites)
    results: dict[str, dict[str, dict[str, object]]] = {}
    for site, cases in CASES.items():
        if site not in sites or site not in adapters:
            continue
        adapter = adapters[site]
        results[site] = {}
        for kind, term in cases:
            started = time.monotonic()
            try:
                rows = adapter._search_candidates(term) or []
                elapsed = int((time.monotonic() - started) * 1000)
                first = getattr(rows[0], "standard_number", "") if rows else ""
                results[site][kind] = {
                    "term": term,
                    "ok": True,
                    "count": len(rows),
                    "elapsed_ms": elapsed,
                    "first_number": first,
                }
            except Exception as exc:  # noqa: BLE001
                results[site][kind] = {
                    "term": term,
                    "ok": False,
                    "count": 0,
                    "elapsed_ms": int((time.monotonic() - started) * 1000),
                    "error": f"{type(exc).__name__}: {str(exc)[:80]}",
                }
    output_json.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    print("| 站点 | 查询类型 | 用例 | 结果 | 条数 | 耗时 ms | 首条号 |")
    print("|---|---|---|---|---:|---:|---|")
    for site, by_kind in results.items():
        for kind, info in by_kind.items():
            status = "✅" if info.get("ok") and info.get("count") else ("空" if info.get("ok") else "❌")
            print(
                f"| {site} | {kind} | `{info['term']}` | {status} | {info.get('count', 0)} | "
                f"{info.get('elapsed_ms', 0)} | {info.get('first_number', '') or info.get('error', '')} |"
            )
    print(f"\n[OK] 矩阵结果写入: {output_json}")
    return 0


def main(argv: list[str] | None = None) -> int:
    # 入口：离线只打印计划；带参数时才联网（避免流水线与误执行时打真实站点）
    ap = argparse.ArgumentParser(description="聚合搜索 3 站矩阵验证")
    ap.add_argument("--live", action="store_true", help="真实联网验证（默认只打印计划）")
    ap.add_argument("--sites", default=",".join(DEFAULT_SITES), help="逗号分隔站点名")
    ap.add_argument("--json", default="C:/Temp/aggregate_matrix.json", help="JSON 输出路径")
    args = ap.parse_args(argv)
    sites = tuple(s.strip() for s in args.sites.split(",") if s.strip())

    print("聚合搜索矩阵计划：")
    for site in sites:
        for kind, term in CASES.get(site, []):
            print(f"  {site:14s} {kind:8s} {term}")
    if not args.live:
        print("\n（离线模式：加 --live 执行真实联网验证）")
        return 0
    return run_live(sites, Path(args.json))


if __name__ == "__main__":
    raise SystemExit(main())
