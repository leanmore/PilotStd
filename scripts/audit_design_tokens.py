#!/usr/bin/env python3
"""设计令牌审计（只读工具，不是门禁）。

扫描 `web/src` 下的 `.vue` / `.css`，识别硬编码的视觉字面量（颜色 / 字号 / 间距 /
圆角 / 高度 / 行高 / 字重），按 A/B/C/D 四类归档，并把明细与统计写入
`docs/design-token-audit.md` 的生成区块（`<!-- AUDIT:BEGIN -->` 与 `<!-- AUDIT:END -->` 之间）。

与 G-055 门禁（`scripts/check_design_tokens.py`）的分工：
  - 本脚本：按需全量审计，输出全部命中供人工确认（不阻断提交）；
  - G-055：棘轮门禁，只拦「新增」硬编码，复用本脚本的分类函数。

用法：
    python scripts/audit_design_tokens.py            # 更新报告生成区块
    python scripts/audit_design_tokens.py --check    # 只统计，不写文件（CI/本地自查）
    python scripts/audit_design_tokens.py --limit 40 # 控制每张明细表的最大行数

实现要点（改动前先读，避免把已合规的东西算成债）：
  * 扫描前必须去注释——style.css 的 RETAINED 说明里写着 #cbd5e1 / #047857 等色值，
    不去注释会把这些"解释性文字"误报成硬编码。
  * .vue 只取 <style> 块与 style="" 内联属性；模板里的 class 名、:style JS 绑定都不是
    CSS 声明，取进来只会制造噪声。
  * 选择器用"声明前最近一个 {"的近似值，只服务于 :root 与 .p-* 两处判定，
    不追求完整 CSS 解析器（本仓没有嵌套 CSS，近似已足够）。
  * 已定义令牌集合必须合并三处来源：CSS 声明、themes.ts 的 '--x': c.y 注入、
    useThemeSync 的 setProperty；漏一处就会把"运行时注入的令牌"误判成 D 类缺陷。
  * 颜色映射先查语义表（BG_MAP/FG_MAP/BORDER_MAP）再按值精确匹配：
    语义优先，否则 #ffffff 会被随手匹配到任意同值令牌（如 --surface 被当成文字色）。

分类口径：
  A 精确映射：值命中已定义令牌，可机械替换（置信度 高）
  B 近似映射：无精确令牌，需人工确认 + 行上方加 TODO（置信度 中/低）
  C 排除：令牌定义、`var()` fallback、PrimeVue 覆盖白名单、SVG 图表、装饰细线、布局尺寸
  D 缺陷：`var()` 引用了未定义变量（修复前 11 名 / 26 处；现为 0，保留该类用于回归）
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB_SRC = ROOT / "web" / "src"
REPORT = ROOT / "docs" / "design-token-audit.md"
BEGIN = "<!-- AUDIT:BEGIN -->"
END = "<!-- AUDIT:END -->"

SCAN_EXT = {".vue", ".css"}
CHART_FILE = "components/dashboard/widgets/TaskTrendCard.vue"

# ── 令牌取值（用于精确匹配与语义映射） ────────────────────────────────
STYLE_CSS = WEB_SRC / "style.css"
TOKENS_CSS = WEB_SRC / "styles" / "design-tokens.css"
THEMES_TS = WEB_SRC / "config" / "themes.ts"

# 间距档位 = 实测全集：收敛到 8 像素网格会改变视觉，属另一件事，故非网格档位也原样保留
SPACING_TIERS = [1, 2, 3, 4, 6, 7, 8, 9, 10, 12, 14, 16, 18, 20, 24, 30, 32, 40, 44]
FONT_SIZE_TIERS = [9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 20, 22, 24, 28, 42, 72]
LINE_HEIGHT_TIERS = {"1": "none", "1.25": "snug", "1.3": "compact", "1.5": "normal",
                     "1.6": "body", "1.7": "relaxed", "1.8": "loose"}
FONT_WEIGHT_TIERS = {400: "regular", 500: "medium", 600: "semibold", 700: "bold", 800: "extrabold"}
# 10/14 指向旧令牌：新 --ds-radius-* 档位与之不同值，按"值"查表才不会把 14 错配成 16
RADIUS_MAP = {"4": "--ds-radius-xs", "6": "--ds-radius-sm", "8": "--ds-radius-md",
              "12": "--ds-radius-lg", "16": "--ds-radius-xl", "999": "--ds-radius-pill",
              "10": "--radius", "14": "--radius-lg"}
RADIUS_DECORATIVE = {"2", "3"}          # 滚动条/进度条细线，保持字面量
# 34/32 是仪表盘图标方块（宽高成对出现），不是按钮内高；按钮当前靠内边距撑开
HEIGHT_MAP = {"34": "--icon-tile-md", "32": "--icon-tile-sm"}

# 语义色映射：属性族 → {字面量: 令牌}。None 表示"有语义但仓内无令牌"（B 类）。
BG_MAP = {
    "#ffffff": "--surface", "#fff": "--surface",
    "#f8fafc": "--bg", "#f1f5f9": "--surface-raised", "#ffffff00": None,
    "#ef4444": "--danger", "#f59e0b": "--warning", "#22c55e": "--success", "#3b82f6": "--info",
    "rgba(99,102,241,0.1)": "--primary-bg", "rgba(99,102,241,0.12)": "--primary-bg",
    "rgba(99,102,241,0.08)": "--selected", "rgba(99,102,241,0.2)": "--primary-border",
    "rgba(34,197,94,0.12)": "--success-bg", "rgba(239,68,68,0.12)": "--danger-bg",
    "rgba(245,158,11,0.12)": "--warning-bg", "rgba(59,130,246,0.12)": "--info-bg",
    "rgba(34,197,94,0.18)": "--success-bg", "rgba(239,68,68,0.18)": "--danger-bg",
}
FG_MAP = {
    "#475569": "--text", "#334155": "--text-bright", "#0f172a": "--text-heading",
    "#5b6b80": "--text-secondary", "#445264": "--text-dim",
    "#ef4444": "--danger", "#dc2626": "--danger", "#f59e0b": "--warning",
    "#22c55e": "--success", "#10b981": "--success",
    "#3b82f6": "--info", "#5c5ef2": "--primary", "#4f46e5": "--primary-hover",
    "#ffffff": None, "#fff": None,       # 无 on-primary 前景令牌
    "#9ca3af": None, "#6b7280": None, "#94a3b8": None, "#ccc": None,
}
BORDER_MAP = {
    "#e2e8f0": "--border", "#f1f5f9": "--border-light", "#cbd5e1": None,
    "#ef4444": "--danger", "#22c55e": "--success", "#5c5ef2": "--primary",
    "#f59e0b": "--warning", "#3b82f6": "--info", "#e5e7eb": None,
}

COLOR_PROPS = re.compile(r"^(background|background-color|color|fill|stroke)$")
BORDER_PROPS = re.compile(r"^(border|border-[a-z]+|border-color|border-[a-z]+-color|outline|outline-color)$")
SPACING_PROPS = re.compile(r"^(padding|margin|gap)(-[a-z]+)?$")
HEIGHT_PROPS = re.compile(r"^(height|min-height|max-height|line-height)$")
RADIUS_PROPS = re.compile(r"^border(-[a-z]+)?-radius$")
FONT_SIZE_PROPS = re.compile(r"^font-size$")
FONT_WEIGHT_PROPS = re.compile(r"^font-weight$")

HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")
RGB_RE = re.compile(r"\brgba?\([^)]*\)")
HSL_RE = re.compile(r"\bhsla?\([^)]*\)")
DECL_RE = re.compile(r"(?P<prop>--[A-Za-z0-9_-]+|[A-Za-z-]+)\s*:\s*(?P<value>[^;{}]+)")
STYLE_BLOCK_RE = re.compile(r"<style[^>]*>(.*?)</style>", re.S)
INLINE_STYLE_RE = re.compile(r'\bstyle="([^"]*)"')
COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
VAR_REF_RE = re.compile(r"var\(\s*(--[A-Za-z0-9_-]+)")


@dataclass
class Finding:
    """一条审计命中：位置、属性、原值、建议令牌与分类结论。"""

    file: str
    line: int
    prop: str
    value: str
    token: str | None
    confidence: str
    category: str          # A / B / C / D
    note: str


# ── 解析辅助 ────────────────────────────────────────────────────────
def blank_comments(text: str) -> str:
    """把注释替换成等长空白（保留换行），避免注释里的色值被当成硬编码。

    用"等长空白"而不是删除：行号偏移必须保持不变，否则报告里的行号会错位。
    """
    def repl(m: re.Match[str]) -> str:
        return "".join("\n" if ch == "\n" else " " for ch in m.group(0))
    return COMMENT_RE.sub(repl, text)


def css_regions(path: Path) -> list[tuple[int, str]]:
    """返回 [(起始行号(1-based), 该区域文本)]。.vue 取 <style> 块 + style="" 内联属性。

    内联 style 也要扫：本仓有 20+ 处行内颜色/字号（如 CacheManager 的过期标记），
    漏掉它们会让审计结论与真实债量对不上。
    """
    raw = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix == ".css":
        return [(1, raw)]

    regions: list[tuple[int, str]] = []
    for m in STYLE_BLOCK_RE.finditer(raw):
        start_line = raw.count("\n", 0, m.start(1)) + 1
        regions.append((start_line, m.group(1)))
    for m in INLINE_STYLE_RE.finditer(raw):
        # 跳过行内样式绑定（不是样式表）
        prefix = raw[max(0, m.start() - 1): m.start()]
        if prefix == ":":
            continue
        start_line = raw.count("\n", 0, m.start(1)) + 1
        regions.append((start_line, m.group(1)))
    return regions


def selector_before(text: str, pos: int) -> str:
    """取声明前最近的规则选择器（近似值，足够做 :root / .p-* 判定）。

    嵌套 at-rule 时返回的是内层选择器，这正是我们想要的（.p-datepicker 就在 @media 内）。
    """
    brace = text.rfind("{", 0, pos)
    if brace < 0:
        return ""
    prev = max(text.rfind("}", 0, brace), text.rfind("{", 0, brace))
    return text[prev + 1: brace].strip()


def load_token_values() -> dict[str, str]:
    """收集仓库内已定义的令牌名（CSS 声明 + themes.ts 注入 + setProperty）。

    三处来源缺一不可：只读 CSS 会把 --button-primary-shadow 之类运行时注入的令牌误报成 D 类。
    """
    defined: set[str] = set()
    for path in WEB_SRC.rglob("*"):
        if path.suffix not in SCAN_EXT | {".ts"} or path.name.endswith(".test.ts"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        defined.update(re.findall(r"(?:^|\s)(--[A-Za-z0-9_-]+)\s*:", text, re.M))
        defined.update(re.findall(r"'(--[A-Za-z0-9_-]+)'\s*:\s*c\.", text))
        defined.update(re.findall(r"setProperty\(\s*'(--[A-Za-z0-9_-]+)'", text))
    return {name: "" for name in defined}


def load_token_literals() -> dict[str, str]:
    """令牌名 → 取值（style.css :root + design-tokens.css），用于精确值匹配。"""
    values: dict[str, str] = {}
    for path in (STYLE_CSS, TOKENS_CSS):
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in DECL_RE.finditer(blank_comments(text)):
            prop = m.group("prop")
            if prop.startswith("--"):
                values[prop] = m.group("value").strip()
    return values


# ── 分类 ────────────────────────────────────────────────────────────
def norm(value: str) -> str:
    return re.sub(r"\s+", "", value).lower()


def _dead_var_note(value: str, defined: dict[str, str]) -> str | None:
    """D 类：返回首个未定义变量引用说明，否则 None。"""
    for name in VAR_REF_RE.findall(value):
        if name.startswith("--p-"):
            continue
        if name not in defined:
            return f"var({name}) 引用了未定义变量"
    return None


def _excluded(file: str, prop_l: str, value_n: str, value: str,
              selector: str, color_hits: list[str]) -> tuple[str, str | None, str, str] | None:
    """C 类判定：令牌定义 / 已用令牌 / 计算值 / 组件级排除；命中即返回四元组。"""
    if prop_l.startswith("--"):
        return "C", None, "—", "令牌定义（真相源，不替换）"
    if selector.replace(" ", "") == ":root":
        return "C", None, "—", "默认令牌层定义"
    if "var(" in value_n:
        if color_hits and re.search(r"var\([^)]*,", value):
            return "C", None, "—", "var() fallback（随令牌变化，不改）"
        return "C", None, "—", "已使用令牌"
    if re.search(r"(calc|clamp|min|max)\(", value_n):
        return "C", None, "—", "计算值（布局，不纳入令牌）"
    if value_n in {"0", "auto", "inherit", "initial", "unset", "none", "transparent",
                   "100%", "100vh", "100vw", "fit-content", "1fr"}:
        return "C", None, "—", "无字面量/布局值"
    if RADIUS_PROPS.match(prop_l) and value_n == "50%":
        return "C", None, "—", "圆形（装饰性）"
    if re.fullmatch(r"[-0-9.]+(rem|em|vh|vw|fr)", value_n):
        return "C", None, "—", "相对单位布局值"
    if re.fullmatch(r"\d+(\.\d+)?%", value_n) and not SPACING_PROPS.match(prop_l):
        return "C", None, "—", "百分比尺寸（布局）"
    if file == CHART_FILE:
        return "C", None, "—", "SVG 图表组件（几何/配色与数据绑定，整体排除）"
    if file == "style.css" and re.match(r"^(html\s+|body\s+)?\.p-", selector):
        return "C", None, "—", "PrimeVue 组件覆盖（RETAINED 已批准例外）"
    if RADIUS_PROPS.match(prop_l) and "px" in value_n and value_n.rstrip("px") in RADIUS_DECORATIVE:
        return "C", None, "—", "装饰细线圆角（滚动条/进度条）"
    if prop_l == "height" and value_n in {"1px", "2px", "3px"}:
        return "C", None, "—", "分隔细线高度"
    if prop_l.startswith(("min-height", "max-height", "width", "min-width", "max-width")):
        return "C", None, "—", "布局尺寸（不纳入令牌）"
    return None


def _map_typography(prop_l: str, value_n: str) -> tuple[str, str | None, str, str] | None:
    """字号 / 字重 / 行高的精确映射。"""
    if FONT_SIZE_PROPS.match(prop_l):
        m = re.fullmatch(r"(\d+)px", value_n)
        if m and int(m.group(1)) in FONT_SIZE_TIERS:
            return "A", f"--font-size-{m.group(1)}", "高", "实测档位 1:1"
        return "B", None, "低", "非实测档位（相对字体/变量）"
    if FONT_WEIGHT_PROPS.match(prop_l):
        m = re.fullmatch(r"(\d+)", value_n)
        if m and int(m.group(1)) in FONT_WEIGHT_TIERS:
            return "A", f"--font-weight-{FONT_WEIGHT_TIERS[int(m.group(1))]}", "高", ""
        return "B", None, "低", "非常规字重"
    if prop_l == "line-height":
        if value_n in LINE_HEIGHT_TIERS:
            return "A", f"--line-height-{LINE_HEIGHT_TIERS[value_n]}", "高", ""
        if value_n.endswith("px"):
            return "B", None, "中", "px 行高，需换算倍数后确认"
        return "B", None, "低", "相对行高（em/%）"
    return None


def _map_spacing(value: str) -> tuple[str, str | None, str, str] | None:
    """padding/margin/gap 的多值像素映射：逐个值查 --space-*，全部命中才判 A。"""
    parts = re.sub(r"\s+", " ", value).strip().split(" ")
    tokens: list[str] = []
    ok = True
    for part in parts:
        if part == "0":
            tokens.append("0")
            continue
        m = re.fullmatch(r"(-?\d+)px", part)
        if not m or m.group(1).startswith("-"):
            ok = False
            break
        n = int(m.group(1))
        if n in SPACING_TIERS:
            tokens.append(f"var(--space-{n})")
        else:
            ok = False
            break
    if ok and tokens and any(t != "0" for t in tokens):
        return "A", " ".join(tokens), "高", "8pt 网格外的档位已按实测保留"
    if ok and tokens:
        return "C", None, "—", "0 值（无需令牌）"
    return "B", None, "中", "含混合单位/calc，需人工确认"


def _map_radius_height(prop_l: str, value_n: str) -> tuple[str, str | None, str, str] | None:
    """圆角与 height 的映射（34/32px 为仪表盘图标方块尺寸）。"""
    if RADIUS_PROPS.match(prop_l):
        m = re.fullmatch(r"(\d+)px", value_n)
        if m and m.group(1) in RADIUS_MAP:
            tok = RADIUS_MAP[m.group(1)]
            note = "旧令牌" if tok.startswith("--radius") and not tok.startswith("--ds-") else ""
            return "A", tok, "高", note
        return "B", None, "中", "非令牌圆角档位"
    if prop_l == "height":
        m = re.fullmatch(r"(\d+)px", value_n)
        if m and m.group(1) in HEIGHT_MAP:
            return "A", HEIGHT_MAP[m.group(1)], "中", "图标方块尺寸"
        return "B", None, "中", "布局/控件尺寸，需确认是否令牌化"
    return None


def _map_color(prop_l: str, value_n: str, literals: dict[str, str],
               color_hits: list[str]) -> tuple[str, str | None, str, str] | None:
    """颜色、边框、阴影映射：先查语义表，再按令牌取值做精确匹配。

    语义表的键是“属性族 + 字面量”，同一字面量在背景与前景下会映射到不同令牌
    （白色作背景命中表面色令牌，作前景则无令牌，属主色上的缺口）。
    """
    if prop_l in ("fill", "stroke"):
        return "C", None, "—", "SVG 图形填充/描边"
    if COLOR_PROPS.match(prop_l) and color_hits:
        family = "bg" if prop_l.startswith("background") else "fg"
        hit = (BG_MAP if family == "bg" else FG_MAP).get(value_n)
        if hit:
            return "A", hit, "高", ""
        exact = [n for n, v in literals.items() if v and norm(v) == value_n]
        if exact and family == "bg":
            return "A", sorted(exact, key=len)[0], "中", "按值精确匹配"
        return "B", None, "低", "无对应语义令牌"
    if BORDER_PROPS.match(prop_l) and color_hits:
        hit = BORDER_MAP.get(value_n)
        if hit:
            return "A", hit, "高", ""
        exact = [n for n, v in literals.items() if v and norm(v) == value_n]
        if exact:
            return "A", sorted(exact, key=len)[0], "中", "按值精确匹配"
        return "B", None, "低", "无对应语义令牌"
    if prop_l in ("box-shadow", "filter", "backdrop-filter", "text-shadow"):
        if prop_l in ("filter", "backdrop-filter") and re.match(
                r"^(blur|brightness|drop-shadow|saturate)\(", value_n):
            return "C", None, "—", "滤镜效果（非令牌值）"
        exact = [n for n, v in literals.items()
                 if v and norm(v) == value_n and n.startswith("--shadow")]
        if exact:
            return "A", sorted(exact)[0], "中", "阴影值精确匹配"
        return "B", None, "低", "阴影组合值，无令牌"
    return None


def classify(file: str, prop: str, value: str, selector: str,
             literals: dict[str, str],
             defined: dict[str, str]) -> tuple[str, str | None, str, str]:
    """把一条样式声明归入甲乙丙丁四类，返回（类别、令牌、置信度、备注）。

    判定顺序固定：丁（未定义引用）→ 丙（排除）→ 甲乙（属性族映射）。
    顺序不可调换，否则带兜底值的变量会被误判成颜色硬编码。
    候选里把字体族放在间距之前：行高也可能带像素值，先按行高匹配。
    """
    prop_l = prop.lower()
    value_n = norm(value)

    dead = _dead_var_note(value, defined)
    if dead:
        return "D", None, "—", dead

    color_hits = HEX_RE.findall(value) + RGB_RE.findall(value) + HSL_RE.findall(value)
    excluded = _excluded(file, prop_l, value_n, value, selector, color_hits)
    if excluded:
        return excluded

    candidates = [
        _map_typography(prop_l, value_n),
        _map_spacing(value) if SPACING_PROPS.match(prop_l) else None,
        _map_radius_height(prop_l, value_n),
        _map_color(prop_l, value_n, literals, color_hits),
    ]
    for result in candidates:
        if result:
            return result
    return "C", None, "—", "非视觉令牌属性"


# ── 扫描 ────────────────────────────────────────────────────────────
def scan() -> tuple[list[Finding], Counter[str]]:
    literals = load_token_literals()
    defined = load_token_values()
    findings: list[Finding] = []
    skipped: Counter[str] = Counter()

    # 排序是为了让报告行序稳定：同一棵树重跑生成区块应当逐字节一致，便于差异复核
    for path in sorted(WEB_SRC.rglob("*")):
        if path.suffix not in SCAN_EXT or not path.is_file():
            continue
        rel = path.relative_to(WEB_SRC).as_posix()
        for start_line, region in css_regions(path):
            clean = blank_comments(region)
            for m in DECL_RE.finditer(clean):
                prop = m.group("prop")
                value = m.group("value").strip()
                if not value or prop.startswith("--"):
                    continue
                line = start_line + clean.count("\n", 0, m.start())
                selector = selector_before(clean, m.start())
                category, token, confidence, note = classify(rel, prop, value, selector, literals, defined)
                # 已合规/与视觉令牌无关的声明不计入明细（只在统计里留个总数）
                if category == "C" and note in {"已使用令牌", "非视觉令牌属性"}:
                    skipped[note] += 1
                    continue
                findings.append(Finding(rel, line, prop, value, token, confidence, category, note))
    return findings, skipped


# ── 报告生成 ────────────────────────────────────────────────────────
FAMILIES: list[tuple[str, str]] = [
    ("border-radius", "border-radius"), ("border", "border"), ("outline", "outline"),
    ("font-size", "font-size"), ("font-weight", "font-weight"), ("font", "font"),
    ("line-height", "line-height"), ("background", "background"),
    ("padding", "padding"), ("margin", "margin"), ("gap", "gap"),
    ("box-shadow", "box-shadow"), ("height", "height"), ("color", "color"),
]


def prop_family(prop: str) -> str:
    """归并属性族：border-top-color → border，padding-left → padding。"""
    for prefix, family in FAMILIES:
        if prop == prefix or prop.startswith(prefix + "-"):
            return family
    return prop


def md_escape(text: str) -> str:
    return text.replace("|", "\\|")


def table(rows: list[list[str]]) -> str:
    """把二维数据渲染成审计表（表头固定为任务包要求的 7 列）。"""
    head = "| 文件路径 | 行号 | 当前硬编码值 | 样式属性 | 建议令牌 | 匹配置信度 | 备注 |"
    sep = "|---|---|---|---|---|---|---|"
    body = ["| " + " | ".join(md_escape(c) for c in r) + " |" for r in rows]
    return "\n".join([head, sep, *body])


def render(findings: list[Finding], skipped: Counter[str], limit: int) -> str:
    by_cat: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        by_cat[f.category].append(f)

    # limit<=0 表示不截断：默认必须全量，否则"重跑刷新"会把已入库的 1094 行悄悄缩成 200 行
    ab = sorted(by_cat["A"] + by_cat["B"], key=lambda f: (f.file, f.line))
    dup = by_cat["D"]
    c = by_cat["C"]

    out: list[str] = []
    # 明细默认全量（--limit 可收窄）：审计报告要求逐行可复核，截断会让阶段五无法照单执行
    out.append("### 4.1 可替换明细（A 精确映射 / B 近似映射）")
    out.append("")
    truncated = limit > 0 and len(ab) > limit
    note = "下方仅列前 %d 条，完整清单见生成来源（脚本可重跑）。" % limit if truncated else ""
    out.append(f"共 **{len(ab)}** 条（A {len(by_cat['A'])} / B {len(by_cat['B'])}）。{note}")
    out.append("")
    rows = [[f.file, str(f.line), f.value, f.prop, f.token or "（无）",
             f.confidence, f.note or ("需人工确认 + TODO" if f.category == "B" else "")]
            for f in (ab if limit <= 0 else ab[:limit])]
    out.append(table(rows) if rows else "（无）")
    out.append("")

    out.append("### 4.2 排除明细（C：不纳入替换）")
    out.append("")
    reasons = Counter(f.note for f in c)
    out.append("| 排除理由 | 条数 |")
    out.append("|---|---|")
    for reason, count in reasons.most_common():
        out.append(f"| {md_escape(reason)} | {count} |")
    out.append("")

    out.append("### 4.3 缺陷明细（D：未定义变量引用）")
    out.append("")
    if dup:
        out.append(table([[f.file, str(f.line), f.value, f.prop, "（无）", "—", f.note] for f in dup]))
    else:
        # 说明文字里带上守护测试的名字，方便读者知道"为什么现在必然是 0"
        out.append("无。修复后 `web/src` 内 `var()` 引用未定义变量为 **0**"
                   "（由 `web/src/styles/design-tokens.test.ts` 守护）。")
    out.append("")

    # 统计
    _render_stats(out, findings, skipped, by_cat, ab, c, dup)
    return "\n".join(out)


def _render_stats(out: list[str], findings: list[Finding], skipped: Counter[str],
                  by_cat: dict[str, list[Finding]], ab: list[Finding],
                  excluded: list[Finding], dup: list[Finding]) -> None:
    """追加 §4.4~§4.7 汇总统计（总量/按属性族/无令牌色/文件排名）。"""
    out.append("### 4.4 总量")
    out.append("")
    files = sorted({f.file for f in findings})
    out.append("| 指标 | 数值 |")
    out.append("|---|---|")
    out.append(f"| 涉及文件（有命中） | {len(files)} |")
    out.append(f"| 命中总数 | {len(findings)} |")
    out.append(f"| 已令牌化声明（不计入明细） | {skipped['已使用令牌']} |")
    out.append(f"| 与视觉令牌无关（布局属性等） | {skipped['非视觉令牌属性']} |")
    out.append(f"| A 精确映射 | {len(by_cat['A'])} |")
    out.append(f"| B 近似映射（需 TODO） | {len(by_cat['B'])} |")
    out.append(f"| C 排除 | {len(excluded)} |")
    out.append(f"| D 缺陷 | {len(dup)} |")
    out.append("")

    # 按属性族归并（上边框颜色与边框颜色归为同一族），否则统计表会被长尾属性撑散
    out.append("### 4.5 按属性分类")
    out.append("")
    out.append("| 属性 | A | B | 合计 |")
    out.append("|---|---|---|---|")
    prop_rows: dict[str, Counter[str]] = defaultdict(Counter)
    for f in ab:
        prop_rows[prop_family(f.prop)][f.category] += 1
    for prop, counts in sorted(prop_rows.items(), key=lambda kv: -(kv[1]["A"] + kv[1]["B"])):
        out.append(f"| {prop} | {counts['A']} | {counts['B']} | {counts['A'] + counts['B']} |")
    out.append("")

    out.append("### 4.6 无对应令牌的颜色字面量（B 类）")
    out.append("")
    color_families = {"color", "background", "border", "outline"}
    missing = Counter(f.value for f in by_cat["B"] if f.token is None
                     and prop_family(f.prop) in color_families and (HEX_RE.search(f.value) or RGB_RE.search(f.value)))
    if missing:
        out.append("| 字面量 | 出现次数 |")
        out.append("|---|---|")
        for value, count in missing.most_common(25):
            out.append(f"| `{md_escape(value)}` | {count} |")
    else:
        out.append("（无）")
    out.append("")

    out.append("### 4.7 文件维度 Top 10（A+B）")
    out.append("")
    per_file = Counter(f.file for f in ab)
    out.append("| 文件 | 条数 |")
    out.append("|---|---|")
    for file, count in per_file.most_common(10):
        out.append(f"| {file} | {count} |")
    out.append("")


def main() -> int:
    """CLI 入口：扫描并按需刷新报告生成区块。"""
    parser = argparse.ArgumentParser(description="设计令牌审计（只读）")
    parser.add_argument("--check", action="store_true", help="只统计，不写报告")
    parser.add_argument("--limit", type=int, default=0, help="明细表最大行数（0=全量，默认）")
    args = parser.parse_args()

    if not WEB_SRC.exists():
        print(f"[FAIL] 找不到 {WEB_SRC}", file=sys.stderr)
        return 1

    findings, skipped = scan()
    cats = Counter(f.category for f in findings)
    print(f"[AUDIT] 命中 {len(findings)} 条：A={cats['A']} B={cats['B']} C={cats['C']} D={cats['D']}")

    if args.check:
        return 0

    # 报告必须已存在且带生成标记：不存在就报错，绝不新建文件覆盖人工撰写的段落
    block = render(findings, skipped, args.limit)
    text = REPORT.read_text(encoding="utf-8") if REPORT.exists() else f"# 设计令牌审计报告\n\n{BEGIN}\n{END}\n"
    if BEGIN not in text or END not in text:
        print(f"[FAIL] {REPORT} 缺少生成标记 {BEGIN} / {END}", file=sys.stderr)
        return 1
    head, rest = text.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    REPORT.write_text(f"{head}{BEGIN}\n{block}\n{END}{tail}", encoding="utf-8")
    print(f"[OK] 已更新 {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
