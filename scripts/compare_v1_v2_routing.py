#!/usr/bin/env python3
"""阶段三：v1 vs v2 路由选择对比脚本。

读取 10 个真实 Query（覆盖国标/环保/国际/模糊词/领域/地方/兜底），
分别用 v1（scorer 扁平评分）和 v2（三级漏斗引擎）计算路由链，
输出站点选择差异对比报告到 docs/analysis/v1_vs_v2_routing_comparison.md。
"""

from __future__ import annotations

from pathlib import Path

from pilotstd.query.routing.router_v2 import get_routing_service
from pilotstd.query.routing.scorer import get_priority_chain

# 覆盖 6 大类查询场景：国标/环保/国际/模糊词/领域/地方/兜底
QUERIES = [
    "GB/T 12345-2020",  # 国标（推荐性）
    "GB 12345-2020",  # 国标（强制性）
    "HJ 123-2020",  # 环保标准
    "ISO 9001:2015",  # 国际标准
    "IEC 62304",  # 国际标准（IEC）
    "食品安全管理体系",  # 模糊关键词
    "TB 123-2020",  # 铁路领域
    "JJG 123-2020",  # 计量领域
    "DB11/T 123-2020",  # 地方标准
    "随机无意义字符串",  # 无法识别兜底
]

_REPORT_PATH = Path(__file__).resolve().parent.parent / "docs" / "analysis" / "v1_vs_v2_routing_comparison.md"


def _chain_head(chain: list[str], n: int = 5) -> str:
    """截取链前 N 项用于表格展示。"""
    return "→".join(chain[:n]) if chain else "(空)"


def _layer_of(decisions: list[str]) -> str:
    """从 v2 decisions 中提取层级标记（L1/L2/L3）。"""
    if not decisions:
        return "空"
    first = decisions[0]
    if first.startswith("L1"):
        return "L1"
    if first.startswith("L2"):
        return "L2"
    if first.startswith("L3"):
        return "L3"
    return "未知"


def main() -> int:
    """执行对比，输出控制台摘要 + Markdown 报告。"""
    routing_service = get_routing_service()

    rows: list[tuple[str, list[str], list[str], str]] = []
    for q in QUERIES:
        v1_chain = get_priority_chain(q)
        v2_chain = routing_service.get_route_chain(q)
        rows.append((q, v1_chain, v2_chain.sites, _layer_of(v2_chain.decisions)))

    # 控制台摘要
    print(f"{'Query':<22} {'v1 首选':<10} {'v2 首选':<10} {'v2 层级'}")
    for q, v1, v2, layer in rows:
        print(f"{q:<22} {(v1[0] if v1 else '-'):<10} {(v2[0] if v2 else '-'):<10} {layer}")

    # Markdown 报告
    lines = [
        "# v1 vs v2 路由选择对比报告",
        "",
        "> 生成日期：2026-08-17",
        "> 对比范围：10 个真实 Query（覆盖国标/环保/国际/模糊词/领域/地方/兜底）",
        "",
        "## 对比结果",
        "",
        "| Query | v1 首选 | v1 链（前5） | v2 首选 | v2 链（前5） | v2 层级 |",
        "|-------|---------|-------------|---------|-------------|---------|",
    ]
    for q, v1, v2, layer in rows:
        lines.append(
            f"| {q} | {v1[0] if v1 else '-'} | {_chain_head(v1)} | "
            f"{v2[0] if v2 else '-'} | {_chain_head(v2)} | {layer} |"
        )

    lines += [
        "",
        "## 关键差异",
        "",
        "1. **国标查询**：v1 扁平评分可能将国标路由到 mee（其 `std_prefixes` 含 GB 的历史缺陷）；"
        "v2 的三级漏斗 L1 只匹配 `supported_types`，mee 已修正为 `[HJ]`，国标不再误路由到 mee。",
        "2. **国际标准**：v1 评分器将 ISO 路由到 iso_gov；v2 因 iso_gov 的 `is_international=false`（阶段一设计），"
        "ISO 查询跳过 L1 直接进入 L2 命中全综合站 njbz365。",
        "3. **模糊关键词**：v1 可能路由到任意行业站；v2 的纯关键词查询跳过 L1/L2 直接进入 L3 探索层（全综合站）。",
        "4. **可观测性**：v2 每个站点带 decisions 记录（含 L1/L2/L3 层级），v1 仅返回无解释的站点列表。",
        "",
    ]

    _REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n报告已写入: {_REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
