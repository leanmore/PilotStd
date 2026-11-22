"""BaseButton 单测（无显示环境用 offscreen）。"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from pilotstd.ui import tokens_generated as T  # noqa: E402
from pilotstd.ui.widgets.base_button import BaseButton  # noqa: E402


@pytest.fixture(scope="module")
def app():
    """Qt 需要 QApplication 实例（offscreen 下可无窗口）。"""
    inst = QApplication.instance() or QApplication([])
    yield inst


def test_default_is_secondary_m(app) -> None:
    btn = BaseButton("确定")
    assert btn.kind == "secondary"
    assert btn.size_name == "m"
    assert btn.text() == "确定"


def test_all_kinds_render_style(app) -> None:
    for kind in ("primary", "secondary", "danger", "ghost"):
        btn = BaseButton("x", kind=kind)
        qss = btn.styleSheet()
        assert "QPushButton" in qss
        assert btn.property("variant") == kind


def test_all_sizes_use_btn_height_tokens(app) -> None:
    for size, token_name in (("l", "btn_height_lg"), ("m", "btn_height_md"), ("s", "btn_height_sm")):
        btn = BaseButton("x", size=size)
        expected = T.token(token_name)
        assert expected, f"令牌 {token_name} 缺失"
        assert expected in btn.styleSheet(), f"{size} 档未使用 {token_name}"


def test_style_comes_from_generated_tokens(app) -> None:
    """QSS 里的颜色必须能在生成令牌里找到（防止手写色值）。"""
    btn = BaseButton("x", kind="danger", theme="light")
    qss = btn.styleSheet()
    danger = T.color("light", "danger")
    assert danger in qss
    # 令牌里没有的字面色值不应出现
    assert "#ff0000" not in qss.lower()


def test_unknown_kind_raises(app) -> None:
    with pytest.raises(ValueError, match="unknown kind"):
        BaseButton("x", kind="tertiary")


def test_unknown_size_raises(app) -> None:
    with pytest.raises(ValueError, match="unknown size"):
        BaseButton("x", size="xl")


def test_missing_token_raises(app, monkeypatch) -> None:
    """令牌缺失必须显式报错，不能静默降级成默认样式。"""
    monkeypatch.setattr(T, "token", lambda name, default="": "")
    with pytest.raises(KeyError, match="missing scale token"):
        BaseButton("x", size="m")
