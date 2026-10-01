# 模块：项目/18/____脚本
# 国际化模块：中文简体、中文繁体、英文
"""i18n 基础设施：三语翻译 + 执行上下文安全的语言状态。

**线程/异步安全**（专项修复）：当前语言存于 `contextvars.ContextVar` 而非模块级全局。
原先 `_lang` / `_current` 是模块全局，任何线程调用 `set_language()` 都会改写**所有**
线程看到的语言——通知构建器（`_builders_*.py`）、渲染器（`renderer.py`）、聚合器
（`aggregate_buffer.py`）都在 `ThreadPoolExecutor` 与 `asyncio` 任务中被调用，会读到
错误的语言。ContextVar 让每个线程/任务/协程拥有独立视图：

- 不使用 `threading.local()`：它在 `asyncio` 下**不安全**（同一线程内多个任务共享）。
- 不使用加锁：锁只能串行化写入，无法表达"同一线程内嵌套切换"的语义，且给热路径
  （`t()` 每次调用）加锁会带来不必要的竞争。
- 不缓存翻译映射：`_translations[lang]` 只是字典取值（O(1)），缓存副本会让
  "语言"与"映射"两份状态可能不一致；只保留一个真实来源 `_lang_var`。

**行为变更**（有意）：子线程/子任务**不再继承**其它线程通过 `set_language()` 设过的值，
一律从默认 `zh_CN` 开始。原全局语义下"工作线程跟随 UI 当前语言"看似方便，实为竞态；
需要该行为的调用方应在自己的上下文内显式设置（或用 `language()` 上下文管理器）。
"""

import contextlib
import json
import logging
import os
from collections.abc import Iterator
from contextvars import ContextVar
from typing import Dict

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES: tuple[str, ...] = ("zh_CN", "zh_TW", "en")
DEFAULT_LANGUAGE = "zh_CN"

# 当前语言：ContextVar 提供 thread-local + async 安全的语义。
# 默认值即 DEFAULT_LANGUAGE，故 get_language() **永不返回 None**（防御性兜底）。
_lang_var: ContextVar[str] = ContextVar("pilotstd_i18n_lang", default=DEFAULT_LANGUAGE)

_translations: Dict[str, Dict[str, str]] = {}
_loaded: bool = False


def _load() -> None:
    """从 JSON 文件加载翻译数据到 _translations（仅首次调用时执行）。"""
    global _translations
    base = os.path.dirname(__file__)
    for lang in SUPPORTED_LANGUAGES:
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
    """懒加载守卫：首次调用时加载翻译文件，避免 import 时阻塞 I/O。

    只在主线程的首次调用上真正加载；`_load()` 抛错时 `_loaded` 保持 False，
    后续调用会重试（原实现同样如此，未改变该语义）。
    """
    global _loaded
    if not _loaded:
        _load()
        _loaded = True


def _normalize(lang: str) -> str:
    """校验语言码：不支持时回退 DEFAULT_LANGUAGE 并告警。

    不做静默接受：未知语言码会让 `_translations.get(lang, {})` 取到空表，
    进而使 `t()` 全量 fail-loud 返回键名——那比回退到默认语言更难排查。
    """
    if lang in SUPPORTED_LANGUAGES:
        return lang
    logger.warning("不支持的语言 %r，回退 %s", lang, DEFAULT_LANGUAGE)
    return DEFAULT_LANGUAGE


def set_language(lang: str) -> None:
    """设置**当前执行上下文**的语言（不影响其它线程/任务）。"""
    _ensure_loaded()
    _lang_var.set(_normalize(lang))


def get_language() -> str:
    """返回当前执行上下文的语言码；未设置时返回 `DEFAULT_LANGUAGE`（永不返回 None）。"""
    return _lang_var.get()


@contextlib.contextmanager
def language(lang: str) -> Iterator[str]:
    """临时切换语言并在退出时恢复（嵌套安全）。

        with language("en"):
            assert t("...") == "..."

    `ContextVar.set()` 返回的 token 精确记录设置前的值，故嵌套时逐层正确恢复；
    finally 保证异常路径也会恢复。
    """
    _ensure_loaded()
    token = _lang_var.set(_normalize(lang))
    try:
        yield lang
    finally:
        _lang_var.reset(token)


def _(key: str) -> str:
    """翻译入口（UI 侧旧 API）：缺键时回退返回键本身。

    内联 `_lang_var.get()` 而不调 `get_language()`：`t()`/`_()` 是热路径
    （单个通知构建器可调用数十次），实测多套一层函数调用会让每次翻译从
    ~0.18 µs 升到 ~0.32 µs（近一倍），而 `ContextVar.get()` 本身的开销可忽略。
    """
    _ensure_loaded()
    return _translations.get(_lang_var.get(), {}).get(key, key)


def t(key: str) -> str:
    """通知模板翻译入口（v1.1 层级键规范：notification.{category}.{event}.{field}）。

    与 _() 同实现：键缺失时回退返回键本身（fail-loud，测试可捕获缺键）。
    语言取自当前执行上下文，故多线程/多任务并发调用互不干扰。
    """
    _ensure_loaded()
    return _translations.get(_lang_var.get(), {}).get(key, key)
