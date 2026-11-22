#!/usr/bin/env python3
"""跨端设计令牌生成器：Web 真相源 → Win（PyQt）可用令牌模块。

输入（只读）：
  web/src/styles/design-tokens.css   尺度/圆角/字重/行高/尺寸
  web/src/config/themes.ts           四主题颜色（light/dark/green/blue）
输出（只写）：
  pilotstd/ui/tokens_generated.py

约束：
  * 只读源文件，绝不回写；产物为纯数据，不 import Qt；
  * 确定性：两次生成逐字节一致（键排序固定）；
  * 源缺失/解析为空 → exit 1，绝不生成空文件。

用法：
  python scripts/gen_win_tokens.py            # 生成并写盘
  python scripts/gen_win_tokens.py --check    # 只校验（CI 用）：不一致 exit 1
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKENS_CSS = ROOT / "web" / "src" / "styles" / "design-tokens.css"
THEMES_TS = ROOT / "web" / "src" / "config" / "themes.ts"
OUT_PY = ROOT / "pilotstd" / "ui" / "tokens_generated.py"

# ── 解析用正则 ─────────────────────────────────────────────
# CSS 变量行：`--name: value;`
# 主题块起始：两空格缩进的 `name: {`
# 颜色行：六空格缩进的 `key: 'value',`
# CSS 变量名 → Python 常量名（连字符转下划线，去掉前导 --）
_CSS_VAR = re.compile(r"^\s*(--[a-z0-9-]+)\s*:\s*([^;]+);\s*$")
# themes.ts 里 `colors: { ... }` 内的 `key: 'value',`
_THEME_START = re.compile(r"^\s{2}(\w+):\s*\{\s*$")
_COLOR_KEY = re.compile(r"^\s{6}([a-zA-Z][a-zA-Z0-9]*):\s*'([^']*)',")


def _fail(msg: str) -> None:
    print(f"[FAIL] {msg}", file=sys.stderr)
    raise SystemExit(1)


def parse_tokens_css() -> dict[str, str]:
    """解析 `:root` 内的尺度令牌（跳过引用型 `var(...)` 与颜色）。"""
    if not TOKENS_CSS.exists():
        _fail(f"令牌源不存在: {TOKENS_CSS}")
    text = TOKENS_CSS.read_text(encoding="utf-8")
    start = text.find(":root")
    if start < 0:
        _fail("design-tokens.css 未找到 :root 块")
    end = text.find("}", start)
    block = text[start:end]

    tokens: dict[str, str] = {}
    for line in block.splitlines():
        m = _CSS_VAR.match(line)
        if not m:
            continue
        name, value = m.group(1), m.group(2).strip()
        # 只收尺度类（像素数值或纯数字倍数），颜色与变量引用留给主题侧
        if value.startswith("#") or value.startswith("var(") or value.startswith("rgb"):
            continue
        tokens[name] = value
    if not tokens:
        _fail("design-tokens.css 未解析出任何尺度令牌")
    return dict(sorted(tokens.items()))


def parse_themes() -> dict[str, dict[str, str]]:
    """解析 themes.ts 的四个主题 colors 块。"""
    if not THEMES_TS.exists():
        _fail(f"主题源不存在: {THEMES_TS}")
    lines = THEMES_TS.read_text(encoding="utf-8").splitlines()

    themes: dict[str, dict[str, str]] = {}
    current: str | None = None
    in_colors = False
    for line in lines:
        m = _THEME_START.match(line)
        if m and m.group(1) in {"light", "dark", "green", "blue"}:
            current = m.group(1)
            continue
        if current and line.strip() == "colors: {":
            in_colors = True
            themes.setdefault(current, {})
            continue
        if in_colors:
            if line.strip() == "},":
                in_colors = False
                current = None
                continue
            cm = _COLOR_KEY.match(line)
            if cm:
                themes[current][cm.group(1)] = cm.group(2)
    if len(themes) != 4:
        _fail(f"期望解析出 4 个主题，实际 {len(themes)}: {sorted(themes)}")
    for name, colors in themes.items():
        if len(colors) < 10:
            _fail(f"主题 {name} 颜色过少（{len(colors)}），疑似解析失败")
    return {k: dict(sorted(v.items())) for k, v in sorted(themes.items())}


def render(tokens: dict[str, str], themes: dict[str, dict[str, str]]) -> str:
    """生成 Python 模块文本（确定性输出）。"""
    out: list[str] = [
        '"""跨端设计令牌（自动生成，勿手改）。',
        "",
        "来源：Web 端尺度令牌样式表 + 主题配置（由生成脚本读取，勿手改本文件）",
        "生成：python scripts/gen_win_tokens.py",
        "校验：python scripts/gen_win_tokens.py --check（CI 与 check_all.sh 同批）",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "# ── 尺度令牌 ────────────────────────────────────────────",
        "# 来源：Web 端尺度令牌样式表的根选择器块",
        "# 键名规则：变量名去掉前导双横线后，连字符转下划线",
        "# 用途：Win 端 BaseButton 等控件的尺寸/圆角/字号，禁止手写数值",
        "TOKENS: dict[str, str] = {",
    ]
    for name, value in tokens.items():
        py_name = name.lstrip("-").replace("-", "_")
        out.append(f'    "{py_name}": "{value}",')
    out.append("}")
    out.append("")
    out.append("# ── 主题颜色 ────────────────────────────────────────────")
    out.append("# 来源：web/src/config/themes.ts 的 THEMES 对象（四主题）")
    out.append("# 键名与 ThemeConfig.colors 完全一致，便于两端按同名键取值")
    out.append("THEME_COLORS: dict[str, dict[str, str]] = {")
    for theme, colors in themes.items():
        out.append(f'    "{theme}": {{')
        for key, value in colors.items():
            out.append(f'        "{key}": "{value}",')
        out.append("    },")
    out.append("}")
    out.append("")
    out.append("")
    out.append("def token(name: str, default: str = \"\") -> str:")
    out.append('    """取尺度令牌；名字可用 CSS 形式（--space-8）或 Python 形式（space_8）。"""')
    out.append('    key = name.lstrip("-").replace("-", "_")')
    out.append("    return TOKENS.get(key, default)")
    out.append("")
    out.append("")
    out.append("def color(theme: str, key: str, default: str = \"\") -> str:")
    out.append('    """取指定主题的颜色；主题不存在时回退 light。"""')
    out.append('    return THEME_COLORS.get(theme, THEME_COLORS.get("light", {})).get(key, default)')
    out.append("")
    return "\n".join(out)


def main() -> int:
    """入口：解析两端源文件并生成/校验产物。

    返回 0 表示成功；源缺失或产物不一致时以非零退出，绝不静默通过。
    """
    ap = argparse.ArgumentParser(description="生成 Win 端设计令牌")
    ap.add_argument("--check", action="store_true", help="只校验产物是否与源一致")
    args = ap.parse_args()

    tokens = parse_tokens_css()
    themes = parse_themes()
    content = render(tokens, themes)

    if args.check:
        if not OUT_PY.exists():
            _fail(f"产物不存在: {OUT_PY}（先跑 python scripts/gen_win_tokens.py）")
        if OUT_PY.read_text(encoding="utf-8") != content:
            _fail("产物与源不一致：请运行 python scripts/gen_win_tokens.py 后提交")
        print(f"[PASS] Win 端令牌与 Web 源一致（{len(tokens)} 个尺度令牌 / {len(themes)} 个主题）")
        return 0

    OUT_PY.parent.mkdir(parents=True, exist_ok=True)
    OUT_PY.write_text(content, encoding="utf-8", newline="\n")
    print(f"[OK] 已生成 {OUT_PY.relative_to(ROOT)}：{len(tokens)} 尺度令牌 / {len(themes)} 主题")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
