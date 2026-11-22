"""跨端令牌一致性守护：Win 端产物必须与 Web 源同步（改了 Web 忘了重新生成 → 红）。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "gen_win_tokens.py"


def test_win_tokens_in_sync() -> None:
    """`--check` 模式：产物与 design-tokens.css / themes.ts 逐字节一致。"""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
    )
    assert result.returncode == 0, (
        "Win 端令牌与 Web 源不一致，请运行 python scripts/gen_win_tokens.py 后提交。\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )


def test_generated_tokens_cover_required_keys() -> None:
    """产物必须包含按钮层级用到的关键键，否则 BaseButton 会在运行时炸。"""
    from pilotstd.ui import tokens_generated as T

    assert len(T.TOKENS) >= 50, f"尺度令牌过少：{len(T.TOKENS)}"
    for name in ("btn_height_lg", "btn_height_md", "btn_height_sm", "ds_radius_md", "space_16"):
        assert name in T.TOKENS, f"缺少尺度令牌 {name}"

    assert set(T.THEME_COLORS) == {"light", "dark", "green", "blue"}
    for theme, colors in T.THEME_COLORS.items():
        for key in ("bg", "surface", "text", "textOnPrimary", "danger", "primaryFill"):
            assert key in colors, f"主题 {theme} 缺少颜色键 {key}"
