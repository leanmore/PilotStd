#!/usr/bin/env python3
"""G-054：GUI（Vue）单文件覆盖率棘轮（P2-08）。

背景：前端整体阈值在 `web/vite.config.ts` 的 `test.coverage.thresholds`（全局 lines 48.07），
但"全局 48%"掩盖了单文件差异——TaskView.vue 74.56% 而 TaskHistoryList.vue 只有 9.09%。
本门禁只看**登记在基线里的单文件行覆盖率**，规则是棘轮：只能不降，降了就红。

设计取舍（2026-11-14，用户裁定）：
- **不发明固定阈值**：基线存仓库、版本化，取"当前实测值"；上涨只提醒收紧，不阻断；
- **0.5 个百分点缓冲**：覆盖率是统计量，避免 flaky 误红（v8 对分支/宏展开敏感）；
- **只收运行时文件**：`types.ts` 这类纯类型文件没有可执行行（total=0 → 100%），
  纳入分母只会稀释信号，故列在 `type_only` 里，只做"存在性 + 100%"软提醒；
- 文件清单宁窄勿宽：第一批只收 TaskView 链路，`TaskProgress.vue`/`TaskManager.vue`
  待确认是否落在同一失败/恢复分支后再扩（见 docs/onboarding/27 实施记录）。

用法：
    python scripts/check_gui_coverage_ratchet.py            # 门禁判定
    python scripts/check_gui_coverage_ratchet.py --json     # 打印机器可读结果

前置（CI 与本机同口径）：
    cd web && npx vitest run --coverage --coverage.reporter=json-summary
产物：`web/coverage/coverage-summary.json`（v8 reporter 输出，key 是绝对路径）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SUMMARY = ROOT / "web" / "coverage" / "coverage-summary.json"
DEFAULT_BASELINE = ROOT / "scripts" / "gui_coverage_baseline.json"


def normalize_key(raw: str) -> str:
    """把 v8 summary 的绝对路径 key 归一成仓库相对路径（`src/...`）。"""
    path = raw.replace("\\", "/")
    marker = "/src/"
    idx = path.find(marker)
    if idx >= 0:
        return path[idx + 1 :]
    return path


def load_summary(path: Path) -> dict[str, float]:
    """读取 `coverage-summary.json`，返回 {相对路径: lines.pct}。

    v8 的 key 是本机绝对路径（Windows 反斜杠 / Linux 斜杠），必须统一归一，
    否则 CI（Linux）与本机（Windows）的基线永远对不上。
    """
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, float] = {}
    for key, value in data.items():
        if key == "total":
            continue
        lines = (value or {}).get("lines") or {}
        pct = lines.get("pct")
        if isinstance(pct, (int, float)):
            out[normalize_key(key)] = float(pct)
    return out


def check(
    summary: dict[str, float], baseline: dict[str, Any], tolerance: float
) -> tuple[list[str], list[str], list[str]]:
    """返回 (违规, 可收紧提醒, 备注)。违规非空即 FAIL。"""
    failures: list[str] = []
    warns: list[str] = []
    notes: list[str] = []

    # files 只装运行时文件；type_only 单独处理，避免纯类型文件的 0/0 稀释分母
    files: dict[str, Any] = baseline.get("files") or {}
    type_only: list[str] = list(baseline.get("type_only") or [])

    for rel, meta in sorted(files.items()):
        floor = float(meta.get("lines", 0.0)) if isinstance(meta, dict) else float(meta)
        if rel not in summary:
            failures.append(f"{rel}: 未出现在覆盖率报告里（文件改名/移走？请同步基线）")
            continue
        current = summary[rel]
        if current < floor - tolerance:
            failures.append(f"{rel}: {floor:.2f}% → {current:.2f}%（下降超过 {tolerance}pp）")
        elif current > floor + tolerance:
            warns.append(f"{rel}: {floor:.2f}% → {current:.2f}%（已提升，可收紧基线）")

    for rel in type_only:
        if rel not in summary:
            notes.append(f"{rel}: 纯类型文件未出现在报告（不影响判定）")
        elif summary[rel] < 100.0:
            warns.append(f"{rel}: 纯类型文件行覆盖率 {summary[rel]:.2f}%（应为 100%，检查是否有可执行代码混入）")

    return failures, warns, notes


def main(argv: list[str] | None = None) -> int:
    """CLI 入口：读覆盖率报告 + 基线，输出 PASS/FAIL，返回退出码。

    退出码约定：0 = 通过（可带 WARN/NOTE）；1 = 有文件回退或基线文件消失；
    2 = 产物缺失（先跑覆盖率命令），便于 CI 区分"没跑"与"跑输了"。
    """
    # 参数默认值都指向仓库内固定路径，CI 无需传参即可复现本地口径
    parser = argparse.ArgumentParser(description="G-054 GUI 单文件覆盖率棘轮")
    parser.add_argument("--summary", default=str(DEFAULT_SUMMARY), help="coverage-summary.json 路径")
    parser.add_argument("--baseline", default=str(DEFAULT_BASELINE), help="基线 JSON 路径")
    parser.add_argument(
        "--tolerance", type=float, default=None, help="允许的下降百分点（默认取基线 _meta.tolerance_pp）"
    )
    parser.add_argument("--json", action="store_true", help="以 JSON 打印结果")
    args = parser.parse_args(argv)

    summary_path = Path(args.summary)
    baseline_path = Path(args.baseline)
    if not summary_path.exists():
        print(f"FAIL: 覆盖率报告不存在: {summary_path}")
        print("先跑: cd web && npx vitest run --coverage --coverage.reporter=json-summary")
        return 2
    baseline: dict[str, Any] = json.loads(baseline_path.read_text(encoding="utf-8"))
    meta = baseline.get("_meta") or {}
    tolerance = args.tolerance if args.tolerance is not None else float(meta.get("tolerance_pp", 0.5))

    # 三档结果：failures 阻断；warns 只提醒收紧基线；notes 记录不影响判定的情况
    summary = load_summary(summary_path)
    failures, warns, notes = check(summary, baseline, tolerance)

    if args.json:
        print(json.dumps({"failures": failures, "warnings": warns, "notes": notes}, ensure_ascii=False))
    else:
        tracked = ", ".join(sorted((baseline.get("files") or {}).keys()))
        print(f"G-054 GUI 覆盖率棘轮：{len(baseline.get('files') or {})} 个运行时文件（{tolerance}pp 缓冲）")
        print(f"  跟踪: {tracked}")
        for note in notes:
            print(f"  [NOTE] {note}")
        for warn in warns:
            print(f"  [WARN] {warn}")
        for fail in failures:
            print(f"  [FAIL] {fail}")
        if not failures:
            print("PASS: 无单文件覆盖率回退")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
