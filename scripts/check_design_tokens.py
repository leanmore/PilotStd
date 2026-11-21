#!/usr/bin/env python3
"""G-055 设计令牌门禁（棘轮 / ratchet）。

规则（只拦新增，不要求存量清零）：
  * **A 类**（值精确命中已定义令牌）= 必须为 **0**；出现即阻断 —— 说明有人写了本可映射
    却未映射的硬编码。
  * **B / C 类**（已确认的存量例外）= 必须出现在基线中，且**当前次数 ≤ 基线次数**；
    超出即阻断（新增硬编码）。
  * 当前次数 **< 基线次数** = 基线条目过期：只提示人工同步，**不自动改基线**（禁止脚本写基线）。

基线：`scripts/design_token_baseline.json`，只由人工确认后提交；本脚本提供
`--suggest-baseline` 打印候选 JSON 到 stdout，**不落盘**。

与审计工具的分工：分类逻辑复用 `scripts/audit_design_tokens.py`（同一套 classify），
本脚本只负责"与基线比对 + 阻断"，避免两份实现漂移。

用法：
  python scripts/check_design_tokens.py                  # 检查（--fast / CI 调用）
  python scripts/check_design_tokens.py --suggest-baseline
  python scripts/check_design_tokens.py --root <dir> --baseline <file>   # 受控测试用
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_design_tokens as audit  # noqa: E402  复用分类，不复制规则

ROOT = Path(__file__).resolve().parent.parent
WEB_SRC = ROOT / "web" / "src"
BASELINE = ROOT / "scripts" / "design_token_baseline.json"

# 分类备注 → 基线分组。分组只用于可读性与评审，匹配键是 (文件, 属性, 值)。
C_GROUPS = {
    "PrimeVue 组件覆盖（RETAINED 已批准例外）": "primevue-retained",
    "SVG 图表组件（几何/配色与数据绑定，整体排除）": "svg-chart",
    "var() fallback（随令牌变化，不改）": "var-fallback",
    "布局尺寸（不纳入令牌）": "layout-dimension",
    "百分比尺寸（布局）": "layout-dimension",
    "相对单位布局值": "relative-unit",
    "计算值（布局，不纳入令牌）": "calculation",
    "无字面量/布局值": "no-literal",
    "圆形（装饰性）": "decorative-radius",
    "装饰细线圆角（滚动条/进度条）": "decorative-radius",
    "分隔细线高度": "hairline",
    "默认令牌层定义": "token-definition",
    "滤镜效果（非令牌值）": "filter-effect",
    "0 值（无需令牌）": "zero-value",
}
B_GROUPS = {
    "无对应语义令牌": "b-no-token",
    "布局/控件尺寸，需确认是否令牌化": "b-layout-size",
    "含混合单位/calc，需人工确认": "b-mixed-unit",
    "阴影组合值，无令牌": "b-shadow",
    "非令牌圆角档位": "b-radius",
    "非常规字重": "b-font-weight",
    "非实测档位（相对字体/变量）": "b-font-size",
    "px 行高，需换算倍数后确认": "b-line-height",
    "相对行高（em/%）": "b-line-height",
}

GROUP_REASONS = {
    "primevue-retained": "PrimeVue 组件覆盖：Aura 作用域 token 不在 :root，根注入无效；均为 a11y 修复产物",
    "svg-chart": "SVG 图表：配色与数据绑定（柱高/阈值色），令牌化会与数据语义耦合",
    "var-fallback": "var() fallback：随令牌变化，替换会破坏降级路径",
    "layout-dimension": "布局尺寸：width/百分比等，不是视觉令牌（任务包明确排除）",
    "relative-unit": "相对单位：rem/em/vh/vw，与根字号/视口相关",
    "calculation": "calc()/clamp()/min()/max() 计算值",
    "no-literal": "0/auto/inherit/none/transparent 等无字面量值",
    "decorative-radius": "装饰性圆角/圆形（滚动条、进度条、圆点）",
    "hairline": "1~3px 分隔细线高度",
    "token-definition": "令牌定义块（:root）自身的非自定义属性声明",
    "filter-effect": "滤镜效果参数（blur/drop-shadow 等）",
    "zero-value": "间距全为 0，无需令牌",
    "b-no-token": "B 类：无对应语义令牌（如需替换须先补令牌并过对比度契约）",
    "b-layout-size": "B 类：布局/控件尺寸，是否令牌化待定",
    "b-mixed-unit": "B 类：含混合单位，需人工确认",
    "b-shadow": "B 类：阴影组合值，无令牌",
    "b-radius": "B 类：非令牌圆角档位",
    "b-font-weight": "B 类：非常规字重",
    "b-font-size": "B 类：非实测字号档位",
    "b-line-height": "B 类：行高需人工换算",
    "b-other": "B 类：其他无精确令牌项",
    "c-other": "C 类：其他排除项",
    "inline-whitelist": "内联 style 白名单：HTML 属性无法插 CSS 注释，待后续模板重构（禁止为此新增 class）",
}

# 内联白名单：按 (文件, 属性, 值) 精确匹配。
# 只登记"HTML 属性里无法插 CSS 注释"的 2 条；新增同类必须人工评估并占基线条目，
# 禁止按目录或文件整体忽略（否则等于给整个文件开后门）。
INLINE_WHITELIST = {
    ("views/PendingView.vue", "height", "20px"),
    ("views/SystemResources.vue", "height", "24px"),
}

TOKEN_HINT = (
    "请改用 web/src/styles/design-tokens.css 的令牌（间距 --space-*、字号 --font-size-*、"
    "圆角 --ds-radius-*、字重 --font-weight-*）或已有语义色令牌（--text / --danger / --success …）"
)


def group_of(finding: audit.Finding) -> str:
    """把一条命中归入可读分组（内联白名单优先，其次按分类备注）。

    分组只服务于"基线文件可读可审"；匹配与阻断用的是 key_of 的三元组，不依赖分组。
    因此把某条错分到别的组不会放过违规，只会让报告分组难看——这是有意的取舍。
    """
    key = (finding.file, finding.prop.lower(), finding.value.strip())
    if key in INLINE_WHITELIST:
        return "inline-whitelist"
    table = B_GROUPS if finding.category == "B" else C_GROUPS
    return table.get(finding.note, "b-other" if finding.category == "B" else "c-other")


def key_of(finding: audit.Finding) -> tuple[str, str, str]:
    """基线匹配键：文件 + 属性 + 值（不含行号，允许格式化导致的行号漂移）。

    刻意不放行号：改注释、加空行都会让行号整体平移，按行号匹配的基线会天天误报。
    也不放选择器：类名重命名是正常重构，若进了键，重构就会被门禁拦住。
    """
    return (finding.file, finding.prop.lower(), finding.value.strip())


def collect(root: Path) -> list[audit.Finding]:
    """扫描并只保留需要纳入门禁的命中。

    D 类（var() 引用未定义变量）不进门禁：它是缺陷而非样式债，由前端
    `web/src/styles/design-tokens.test.ts` 直接判红，比在这里做基线更合适。
    """
    findings, _skipped = audit.scan(root)
    return [f for f in findings if f.category in ("A", "B", "C")]


def suggest_baseline(root: Path) -> dict:
    """生成候选基线（只返回结构，由调用方打印；脚本**不写文件**）。

    A 类被显式排除：基线的语义是"已确认的存量例外"，把可映射硬编码写进基线
    等于宣布"这笔债不用还"，与门禁目的相反。故 A 类永远不可能是合法基线项。
    """
    findings = collect(root)
    counts = Counter(f.category for f in findings)
    buckets: dict[str, dict[tuple[str, str, str], int]] = {}
    for f in findings:
        if f.category == "A":
            continue  # A 类不入门禁基线：必须为 0
        group = group_of(f)
        bucket = buckets.setdefault(group, {})
        bucket[key_of(f)] = bucket.get(key_of(f), 0) + 1
    groups = []
    for group in sorted(buckets):
        entries = [
            {"file": k[0], "prop": k[1], "value": k[2], "count": n}
            for k, n in sorted(buckets[group].items())
        ]
        groups.append({
            "id": group,
            "class": "B" if group.startswith("b-") or group == "inline-whitelist" else "C",
            "reason": GROUP_REASONS.get(group, ""),
            "entries": entries,
        })
    return {
        "version": 1,
        "gate": "G-055",
        "generated_at": "2026-11-21",
        "note": "人工确认后提交；禁止脚本自动更新。匹配键 = 文件 + 属性 + 值，计数为上限。",
        "counts": {"A": 0, "B": counts.get("B", 0), "C": counts.get("C", 0)},
        "groups": groups,
    }


def load_baseline(path: Path) -> dict[tuple[str, str, str], int]:
    """把基线摊平成 {匹配键: 允许次数}。

    同一 (文件, 属性, 值) 若因分组调整在多组出现，次数累加——容错但不放宽上限。
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    limits: dict[tuple[str, str, str], int] = {}
    for group in data.get("groups", []):
        for entry in group.get("entries", []):
            key = (entry["file"], entry["prop"].lower(), entry["value"].strip())
            limits[key] = limits.get(key, 0) + int(entry.get("count", 1))
    return limits


def check(root: Path, baseline_path: Path) -> tuple[list[str], list[str]]:
    """执行门禁，返回 (违规, 基线过期提示)。违规为 0 时退出码 0。"""
    # 逐条按基线消耗名额：seen 记录"当前第几次出现"，超过 limit 即新增
    limits = load_baseline(baseline_path)
    findings = collect(root)
    seen: Counter[tuple[str, str, str]] = Counter()
    violations: list[str] = []

    for f in sorted(findings, key=lambda x: (x.file, x.line)):
        key = key_of(f)
        seen[key] += 1
        if f.category == "A":
            violations.append(
                f"{f.file}:{f.line}  {f.prop}: {f.value}  → 建议 {f.token or '（无）'}"
                f"  [A 类可映射硬编码，必须替换]{'；' + f.note if f.note else ''}"
            )
            continue
        limit = limits.get(key, 0)
        if seen[key] > limit:
            extra = "（基线外新增）" if limit == 0 else f"（基线 {limit} 次，当前第 {seen[key]} 次）"
            violations.append(
                f"{f.file}:{f.line}  {f.prop}: {f.value}{extra}  [{f.category} 类 · {f.note}]"
            )

    stale = [
        f"{key[0]}  {key[1]}: {key[2]}  基线 {limits[key]} 次 / 当前 {seen.get(key, 0)} 次"
        for key in sorted(limits)
        if seen.get(key, 0) < limits[key]
    ]
    return violations, stale


def main() -> int:
    """CLI 入口。"""
    parser = argparse.ArgumentParser(description="G-055 设计令牌门禁（只拦新增）")
    parser.add_argument("--suggest-baseline", action="store_true", help="打印候选基线 JSON（不写文件）")
    parser.add_argument("--root", type=Path, default=WEB_SRC, help="扫描根（默认 web/src）")
    parser.add_argument("--baseline", type=Path, default=BASELINE, help="基线文件")
    args = parser.parse_args()

    # --suggest-baseline 只打印候选给人工评审；脚本没有写基线的分支，杜绝自动回填
    if args.suggest_baseline:
        print(json.dumps(suggest_baseline(args.root), ensure_ascii=False, indent=2))
        return 0

    # 退出码：0 通过 / 1 违规 / 2 基线缺失（与 check_all.sh 的 if 判定兼容）
    if not args.baseline.exists():
        print(f"[FAIL] 基线文件不存在: {args.baseline}（先用 --suggest-baseline 生成候选并人工提交）", file=sys.stderr)
        return 2

    violations, stale = check(args.root, args.baseline)
    for line in stale:
        print(f"[STALE] {line}  —— 数量已减少，请人工同步基线（脚本不会自动改）")
    if violations:
        print(f"\n[FAIL] G-055 设计令牌门禁：{len(violations)} 处新增硬编码", file=sys.stderr)
        for line in violations:
            print(f"  {line}", file=sys.stderr)
        print(f"\n{TOKEN_HINT}", file=sys.stderr)
        return 1
    print(f"[PASS] G-055 设计令牌门禁（A=0；B/C 均在基线内；过期提示 {len(stale)} 条）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
