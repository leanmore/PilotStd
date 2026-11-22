"""Win 端按钮统一守护（DS 阶段二）：源码内不得再出现 QPushButton 构造调用。

对应 G-029「UI 变更需同步测试」：本文件即 `pilotstd/ui/**` 按钮替换的守护用例。
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
UI_ROOT = ROOT / "pilotstd" / "ui"

CALL = re.compile(r"(?<![\w.])QPushButton\(")


def _ui_sources() -> list[Path]:
    """返回 pilotstd/ui 下所有 py 源文件（排除缓存）。"""
    return [p for p in sorted(UI_ROOT.rglob("*.py")) if "__pycache__" not in p.parts]


def test_no_raw_qpushbutton_instantiation() -> None:
    """不得再用 QPushButton(...) 构造按钮；统一走 BaseButton。"""
    offenders = []
    for p in _ui_sources():
        text = p.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), 1):
            if CALL.search(line):
                offenders.append(f"{p.relative_to(ROOT)}:{i}: {line.strip()[:80]}")
    assert not offenders, "发现未替换的 QPushButton 构造：\n" + "\n".join(offenders)


def test_base_button_module_exists() -> None:
    """BaseButton 必须存在且可从 widgets 包导入（跨端令牌产物就绪）。"""
    module = ROOT / "pilotstd" / "ui" / "widgets" / "base_button.py"
    assert module.exists(), f"缺少 {module}"
    text = module.read_text(encoding="utf-8")
    assert "class BaseButton" in text
    assert "tokens_generated" in text, "BaseButton 必须从跨端令牌产物取样式"


def test_generated_tokens_have_button_sizes() -> None:
    """跨端令牌必须提供按钮三档高度，否则 BaseButton 会在运行时报错。"""
    import importlib.util

    path = ROOT / "pilotstd" / "ui" / "tokens_generated.py"
    spec = importlib.util.spec_from_file_location("_tokens_for_ui_test", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for name in ("btn_height_lg", "btn_height_md", "btn_height_sm", "ds_radius_md"):
        assert name in mod.TOKENS, f"缺少令牌 {name}"
