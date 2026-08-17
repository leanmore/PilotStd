#!/usr/bin/env python3
"""阶段四：路由决策日志解析与指标聚合脚本。

从 logs/router_v2_decisions.jsonl 提取站点级路由指标，
输出与 site_capabilities.yaml 兼容的 YAML 摘要。
容错：空日志、畸形行跳过并警告，不中断执行。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


def _parse_time_range(since: str | None, until: str | None, ts: str) -> bool:
    """判断时间戳是否落在 [since, until] 区间（ISO8601 字符串比较）。"""
    if since and ts < since:
        return False
    if until and ts > until:
        return False
    return True


def analyze(jsonl_path: str, since: str | None, until: str | None) -> dict[str, Any]:
    """解析 JSONL 日志，返回站点级指标。

    逐行读取，畸形行跳过并计数；按 hit/attempt/配额跳过聚合各站点指标。
    """
    hit_count: dict[str, int] = defaultdict(int)  # 命中次数
    attempt_count: dict[str, int] = defaultdict(int)  # 尝试次数
    latency_sum: dict[str, float] = defaultdict(float)  # 延迟累加
    total_queries = 0
    fallback_queries = 0
    quota_skip_count: dict[str, int] = defaultdict(int)  # 配额跳过次数
    skipped_lines = 0

    for line in Path(jsonl_path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        # 畸形行容错：跳过并计数，不中断解析
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            skipped_lines += 1
            continue
        # 时间范围过滤（字符串比较 ISO8601）
        ts = rec.get("timestamp", "")
        if not _parse_time_range(since, until, ts):
            continue
        total_queries += 1

        # 提取命中/尝试/配额跳过，按站点聚合
        attempted = rec.get("attempted_sites", [])
        hit = rec.get("hit_site")
        latency = rec.get("total_latency_ms", 0)
        for site in attempted:
            attempt_count[site] += 1
        if hit:
            hit_count[hit] += 1
            if isinstance(latency, (int, float)):
                latency_sum[hit] += latency
        if rec.get("fallback_count", 0) > 0:
            fallback_queries += 1
        for site in rec.get("quota_skipped_sites", []):
            quota_skip_count[site] += 1

    sites: dict[str, dict[str, Any]] = {}
    all_sites = set(attempt_count) | set(hit_count) | set(quota_skip_count)
    for site in sorted(all_sites):
        attempts = attempt_count[site]
        hits = hit_count[site]
        sites[site] = {
            "historical_hit_rate": round(hits / attempts, 4) if attempts else 0.0,
            "avg_latency_ms": round(latency_sum[site] / hits, 1) if hits else 0,
        }

    return {
        "sites": sites,
        "summary": {
            "total_queries": total_queries,
            "fallback_trigger_rate": round(fallback_queries / total_queries, 4) if total_queries else 0.0,
            "quota_exhaustion_rate": {
                site: round(quota_skip_count[site] / total_queries, 4)
                for site in sorted(quota_skip_count)
            },
            "skipped_lines": skipped_lines,
        },
    }


def _to_yaml(data: dict[str, Any]) -> str:
    """将指标字典转为 YAML 文本（手写，避免依赖 yaml 模块的额外配置）。"""
    lines = ["# 由 analyze_router_logs.py 生成", "sites:"]
    for site, metrics in data["sites"].items():
        lines.append(f"  {site}:")
        lines.append(f"    historical_hit_rate: {metrics['historical_hit_rate']}")
        lines.append(f"    avg_latency_ms: {metrics['avg_latency_ms']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    """入口：解析命令行参数，输出站点级指标 YAML。"""
    parser = argparse.ArgumentParser(description="解析路由决策 JSONL 日志，输出站点级指标 YAML")
    parser.add_argument("jsonl", help="JSONL 日志路径")
    parser.add_argument("--since", default=None, help="起始时间（ISO8601，含）")
    parser.add_argument("--until", default=None, help="结束时间（ISO8601，含）")
    args = parser.parse_args()

    if not Path(args.jsonl).exists():
        print(f"❌ 日志文件不存在: {args.jsonl}", file=sys.stderr)
        return 1

    result = analyze(args.jsonl, args.since, args.until)
    print(_to_yaml(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
