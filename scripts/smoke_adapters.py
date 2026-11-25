#!/usr/bin/env python3
"""适配器节点 A2：4 站路由/解析/在线检索冒烟工具（本地手动执行，不进 CI 快闸）。

## 为什么单独一个脚本

`tests/test_adapter_site_conformance.py` 覆盖**离线**一致性（解析→路由→适配器契约，CI 可跑）；
但「站点真实可达且返回真实数据」只能联网验证，CI 默认禁网，所以放在这里由人手动执行。

## 用法

```bash
python scripts/smoke_adapters.py              # 只打印解析+路由链（离线，零网络）
python scripts/smoke_adapters.py --live       # 额外做 3 站真实检索（API/ASME/重庆）
python scripts/smoke_adapters.py --live --number "API 610-2004"
```

福建站（`fj`）当前 **BLOCKED**：`pt.fjbz.org.cn` / `www.fjbz.org.cn`（220.160.53.32）全端口 TCP 超时，
本脚本只输出该结论、不发起重试（避免误以为可用）。详见 `docs/plans/2026-11-24-p2-recon-cq-fj.md`。

退出码：0 冒烟通过；1 有站点检索异常（联网模式）；2 环境/配置不可用。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pilotstd.core.std_utils import parse_std_number  # noqa: E402
from pilotstd.query.routing.router_v2 import RoutingService  # noqa: E402

SAMPLES = [
    "API 610-2004",
    "API SPEC 6D-2021",
    "API 579-1/ASME FFS-1",
    "ASME B16.5-2020",
    "ASME PTC 4-2013",
    "ASME BPVC Section VIII Div.1-2021",
    "DB50/T 1234-2021",
    "GB/T 1.1-2020",
]

# 站点 → (模块, 类名, 联网样例号)
LIVE_CASES = {
    "api_webstore": ("pilotstd.query.adapters.api_webstore", "ApiWebstoreAdapter", "API 610-2004"),
    "asme": ("pilotstd.query.adapters.asme", "AsmeAdapter", "ASME B16.5-2020"),
    "cqis": ("pilotstd.query.adapters.cqis", "CqisAdapter", "DB50/T"),
}


def _sites(routing: RoutingService, query: str) -> list[str]:
    chain = routing.get_route_chain(query)
    return [getattr(s, "site_name", getattr(s, "site_id", str(s))) for s in getattr(chain, "sites", [])]


def print_offline(routing: RoutingService) -> None:
    """打印解析结果与路由链（零网络）。"""
    print("=== 解析 + 路由链（离线） ===")
    for q in SAMPLES:
        parsed = parse_std_number(q)
        fields = ("code", "number", "part", "year", "num_prefix", "num_suffix")
        brief = {k: v for k, v in parsed.items() if v and k in fields}
        print(f"  {q:36s} {brief} -> {_sites(routing, q)[:5]}")


def run_live(case_filter: str = "") -> int:
    """3 站真实检索（联网）；返回失败站点数。"""
    failures = 0
    print("\n=== 在线检索（联网，单站超时由 adapter 自身控制） ===")
    for site, (mod_name, cls_name, number) in LIVE_CASES.items():
        if case_filter and case_filter != site:
            continue
        try:
            module = __import__(mod_name, fromlist=[cls_name])
            adapter = getattr(module, cls_name)()
            results = adapter.query_standards(number)
        except Exception as exc:  # noqa: BLE001  联网冒烟需如实报告异常类型
            print(f"  [{site}] {number} 异常: {type(exc).__name__}: {str(exc)[:120]}")
            failures += 1
            continue
        ok = [r for r in results if getattr(r, "standard_number", "")]
        print(f"  [{site}] {number} -> {len(results)} 条（{len(ok)} 有条号）")
        for row in results[:3]:
            num = getattr(row, "standard_number", "")
            name = str(getattr(row, "standard_name", ""))[:40]
            status = getattr(row, "status", "")
            print(f"      - {num} | {name} | {status}")
        if not ok:
            failures += 1
    print("\n[福建] BLOCKED：220.160.53.32 全端口 TCP 超时（DNS 可解析），不重试")
    return failures


def main(argv: list[str] | None = None) -> int:
    """入口：离线打印解析+路由；--live 时额外做 3 站真实检索。"""
    ap = argparse.ArgumentParser(description="4 站适配器冒烟")
    ap.add_argument("--live", action="store_true", help="额外做真实联网检索")
    ap.add_argument("--site", default="", help="只跑某一个站点（api_webstore/asme/cqis）")
    args = ap.parse_args(argv)

    cap = ROOT / "config" / "site_capabilities.yaml"
    if not cap.exists():
        print(f"[FAIL] 能力模型缺失: {cap}")
        return 2
    routing = RoutingService(str(cap))
    print_offline(routing)
    if not args.live:
        print("\n（离线模式；加 --live 做真实检索）")
        return 0
    failures = run_live(args.site)
    print(f"\n结果：失败站点 {failures}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
