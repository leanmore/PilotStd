# pilotstd/i18n/__init__.py
# 国际化模块：中文简体、中文繁体、英文

import json
import logging
import os
from typing import Dict

logger = logging.getLogger(__name__)


_translations: Dict[str, Dict[str, str]] = {}
_current: Dict[str, str] = {}
_lang: str = "zh_CN"
_loaded: bool = False


def _load() -> None:
    """从 JSON 文件加载翻译数据到 _translations（仅首次调用时执行）。"""
    global _translations
    base = os.path.dirname(__file__)
    for lang in ("zh_CN", "zh_TW", "en"):
        path = os.path.join(base, f"{lang}.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                _translations[lang] = json.load(f)
        except FileNotFoundError:
            _translations[lang] = {}
        except json.JSONDecodeError as e:
            logger.error("i18n 翻译文件 JSON 解析失败: %s — %s", path, e)
            _translations[lang] = {}


def _ensure_loaded() -> None:
    """懒加载守卫：首次调用时加载翻译文件，避免 import 时阻塞 I/O。"""
    global _loaded, _translations, _current
    if not _loaded:
        _load()
        _current = _translations.get(_lang, {})
        _loaded = True


def set_language(lang: str) -> None:
    """切换当前语言环境，更新 _current 翻译映射。"""
    global _lang, _current
    _ensure_loaded()
    _lang = lang
    _current = _translations.get(lang, {})


def get_language() -> str:
    return _lang


def _(key: str) -> str:
    _ensure_loaded()
    return _current.get(key, key)
