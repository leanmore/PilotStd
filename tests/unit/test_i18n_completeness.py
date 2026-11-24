"""i18n 键完整性守卫（2026-11-25，方向 C 第四轮深扫）。

背景：`pilotstd.i18n.t()` 缺键时**返回键名本身**（fail-loud），
所以「生产代码用了某键但词典没有」= 用户界面/通知里出现原始 key。
本轮实测发现 `notification.channel.wechat.token_failed` 三语全缺（用户可见 bug），
并为 zh_TW 补齐 83 个 GUI 文案。本测试锁死这一类问题：
生产代码里所有字面量 `t("...")` 键，必须在 **三个词典** 中都存在。
"""

from __future__ import annotations

import ast
import json
import os

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
I18N_DIR = os.path.join(REPO_ROOT, "pilotstd", "i18n")
LANGS = ("zh_CN.json", "zh_TW.json", "en.json")


def _load(lang: str) -> set[str]:
    with open(os.path.join(I18N_DIR, lang), encoding="utf-8") as f:
        return set(json.load(f).keys())


def _used_keys() -> dict[str, set[str]]:
    """扫描生产代码里的字面量 `t("...")` / `_("...")` 键。"""
    used: dict[str, set[str]] = {}
    for root in ("pilotstd", "docker"):
        for dirpath, _dirs, names in os.walk(os.path.join(REPO_ROOT, root)):
            if "__pycache__" in dirpath or f"{os.sep}templates{os.sep}" in dirpath:
                continue
            if f"{os.sep}i18n" in dirpath:  # 词典目录自身
                continue
            for name in names:
                if not name.endswith(".py"):
                    continue
                path = os.path.join(dirpath, name)
                rel = os.path.relpath(path, REPO_ROOT).replace("\\", "/")
                try:
                    tree = ast.parse(open(path, encoding="utf-8").read())
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if not isinstance(node, ast.Call):
                        continue
                    fn = node.func
                    fname = fn.id if isinstance(fn, ast.Name) else ""
                    if fname not in ("t", "_"):
                        continue
                    if not node.args:
                        continue
                    arg = node.args[0]
                    if not isinstance(arg, ast.Constant) or not isinstance(arg.value, str):
                        continue
                    key = arg.value
                    # 只校验「像层级键」的（含点号或下划线全小写），排除普通中文句子
                    if "." in key or (key.isascii() and key.replace("_", "").isalnum()):
                        used.setdefault(key, set()).add(rel)
    return used


@pytest.mark.parametrize("lang", LANGS)
def test_all_used_keys_exist_in_dictionary(lang: str) -> None:
    """生产代码用到的每个 i18n 键都必须在该语言词典中存在（否则显示原始键名）。"""
    dictionary = _load(lang)
    used = _used_keys()
    missing = {k: sorted(v)[:2] for k, v in used.items() if k not in dictionary}
    assert not missing, (
        f"{lang} 缺失 {len(missing)} 个被使用的 i18n 键（t() 会原样返回键名）：\n"
        + "\n".join(f"  - {k}  ← {src}" for k, src in list(missing.items())[:20])
    )


def test_wechat_token_failed_key_present_in_all_languages() -> None:
    """具体回归：本轮修复的 `wechat.token_failed` 三语必须都存在且非键名。"""
    for lang in LANGS:
        dictionary = _load(lang)
        assert "notification.channel.wechat.token_failed" in dictionary, f"{lang} 缺 wechat.token_failed"


def test_zh_tw_has_no_missing_keys_vs_zh_cn() -> None:
    """zh_TW ⊆ zh_CN 的对齐守卫：此前 zh_TW 缺 83 个 GUI 文案（显示原始键名）。"""
    zh_cn = _load("zh_CN.json")
    zh_tw = _load("zh_TW.json")
    missing = sorted(zh_cn - zh_tw)
    assert not missing, f"zh_TW 缺 {len(missing)} 个键：{missing[:20]}"
