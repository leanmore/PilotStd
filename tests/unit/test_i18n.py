"""i18n 模块单元测试 — 覆盖加载、懒加载、语言切换与翻译的 fallback 路径。

## 本文件为何整体重写（stale 测试修正）

本文件原建立于 `b30cfd61`（"语言状态改用 ContextVar"）**之前**的状态模型上：
断言读取 `i18n._lang`、写入/读取 `i18n._current`。该提交把语言状态迁移到
`contextvars.ContextVar`（`_lang_var`）后，**这两个属性已从实现中移除**——
实测 `hasattr(i18n, "_lang") is False`、`hasattr(i18n, "_current") is False`。

旧 fixture 自行 `i18n._current = {}` / `i18n._lang = "zh_CN"`，**凭空创建**了这两个属性，
于是部分用例"偶然通过"（写进 `_current` 的值恰好等于期望值），另一些必然失败
（`set_language()` 只写 `_lang_var`，永不更新 `_lang`）。

**现在实现只读三个状态**（`pilotstd/i18n/__init__.py`）：
- `_lang_var`（`ContextVar`，当前语言；默认 `DEFAULT_LANGUAGE`）；
- `_translations`（`dict[lang, dict]`，懒加载缓存）；
- `_loaded`（懒加载一次性标志）。
`_()` / `t()` 的取值为 `_translations.get(_lang_var.get(), {}).get(key, key)` —— **不读任何 `_current`**。

故本文件改为：
1. fixture 只重置**真实存在**的状态（`_translations` / `_loaded` / `_lang_var`）；
2. 所有断言改读公开 API（`get_language()` / `_()` / `t()`）或真实状态名；
3. 保留原有用例的**意图**（懒加载、fallback、空 key 等），并补足判别力护栏。
"""
from unittest.mock import mock_open, patch

import pytest

import pilotstd.i18n as i18n


@pytest.fixture(autouse=True)
def _reset_i18n_state():
    """每个用例前重置 i18n 的**真实**状态，保证互不串扰。

    只重置当前实现实际读取的三项：`_lang_var` / `_translations` / `_loaded`。
    退出时恢复加载缓存，避免每个用例都重复读 JSON。

    `_lang_var` 是 `ContextVar`，`set()` 只影响本用例的上下文；用 `token` + `reset()`
    精确还原，避免把语言泄漏给后续用例。
    """
    saved = (i18n._translations, i18n._loaded)
    token = i18n._lang_var.set(i18n.DEFAULT_LANGUAGE)
    i18n._translations = {}
    i18n._loaded = False
    yield
    i18n._lang_var.reset(token)
    i18n._translations, i18n._loaded = saved


# ════════════════════════════════════════════════════════════
# _load() — JSON 文件加载
# ════════════════════════════════════════════════════════════

class TestLoad:
    def test_loads_all_three_languages(self):
        """正常加载 zh_CN/zh_TW/en 三个语言文件（真实 JSON）。"""
        i18n._load()
        assert "zh_CN" in i18n._translations
        assert "zh_TW" in i18n._translations
        assert "en" in i18n._translations
        assert isinstance(i18n._translations["zh_CN"], dict)
        assert len(i18n._translations["zh_CN"]) > 0

    def test_file_not_found_uses_empty_dict(self):
        """语言文件不存在 → _translations[lang] = {}。"""
        # 修改 __file__ 指向不存在的目录来触发 FileNotFoundError
        with patch.object(i18n, "__file__", "/nonexistent/__init__.py"):
            i18n._load()
        assert i18n._translations["zh_CN"] == {}
        assert i18n._translations["en"] == {}

    def test_json_decode_error_uses_empty_dict(self):
        """JSON 解析失败 → _translations[lang] = {} + 日志记录。"""
        mock_open_handler = mock_open(read_data="{invalid json")
        with patch("builtins.open", mock_open_handler), patch.object(
            i18n.logger, "error"
        ) as mock_log:
            i18n._load()
        assert i18n._translations["zh_CN"] == {}
        assert i18n._translations["zh_TW"] == {}
        assert i18n._translations["en"] == {}
        # 每个语言文件都触发一次 error 日志
        assert mock_log.call_count == 3


# ════════════════════════════════════════════════════════════
# _ensure_loaded() — 懒加载守卫
# ════════════════════════════════════════════════════════════

class TestEnsureLoaded:
    def test_first_call_triggers_load(self):
        """首次调用 → 触发 `_load()`，并把三个语言都装入 `_translations`。

        **原断言为何不再成立**：原为 `isinstance(i18n._current, dict)`——`_current`
        已随 ContextVar 迁移移除。改为断言真实状态：`_loaded` 置位，且
        `_translations` 装齐 `SUPPORTED_LANGUAGES`（这才是 `_ensure_loaded()` 的实际职责）。
        """
        assert i18n._loaded is False
        i18n._ensure_loaded()
        assert i18n._loaded is True
        assert set(i18n._translations) == set(i18n.SUPPORTED_LANGUAGES)

    def test_second_call_is_noop(self):
        """二次调用 → 不重复加载。"""
        i18n._ensure_loaded()
        with patch.object(i18n, "_load") as mock_load:
            i18n._ensure_loaded()
            mock_load.assert_not_called()

    def test_ensure_loaded_keeps_current_language(self):
        """加载后**不改变**当前语言（原用例名 `test_current_set_from_translations`）。

        **旧用例为何不再成立**：它断言 `i18n._current == {"hello": "你好"}`——
        即"加载会派生一份与当前语言对应的翻译表副本"。实现已取消该副本
        （模块 docstring 明示"不缓存翻译映射……只保留一个真实来源 `_lang_var`"），
        改为按需 `_translations.get(_lang_var.get(), {})` 取值。

        故等价的新断言是：加载后当前语言不变，且**该语言可被 `_()` 正确解析**。
        """
        i18n._translations = {"zh_CN": {"hello": "你好"}}
        i18n._lang_var.set("zh_CN")
        with patch.object(i18n, "_load"):  # 阻止 _load 覆盖 translations
            i18n._ensure_loaded()
        assert not hasattr(i18n, "_current"), "实现不应再有 _current 副本"
        assert i18n.get_language() == "zh_CN"
        assert i18n._("hello") == "你好"

    def test_translation_lookup_empty_when_lang_missing(self):
        """当前语言不在翻译表中 → 取值为空表（原断言 `_current == {}`）。

        **旧用例为何不再成立**：它设 `i18n._lang = "fr_FR"` 并断言 `i18n._current == {}`。
        `_lang` 已移除，改为设置真实的 `_lang_var`，并断言其**可观测后果**：
        `_()` 在该语言下回退返回**键名本身**——这正是模块 docstring 所言
        "fail-loud 返回键名"的行为。
        """
        i18n._lang_var.set("fr_FR")  # 直接写 ContextVar：该语言码不受 _normalize 约束
        i18n._translations = {"zh_CN": {"hello": "你好"}}
        i18n._loaded = True  # 阻止懒加载覆盖上面的 translations
        assert i18n._translations.get(i18n.get_language(), {}) == {}
        assert i18n._("hello") == "hello"


# ════════════════════════════════════════════════════════════
# set_language() — 语言切换
# ════════════════════════════════════════════════════════════

class TestSetLanguage:
    def test_switch_to_known_language(self):
        """切换到已知语言 → `get_language()` 更新，且翻译随之改变。

        **旧断言为何不再成立**：原为 `i18n._lang == "en"`。`set_language()` 现在只写
        `_lang_var`（ContextVar），`_lang` 已移除。改为断言公开 API + 可观测翻译结果。
        """
        i18n._loaded = True  # 跳过 _load() 加载真实文件
        i18n._translations = {
            "zh_CN": {"hello": "你好"},
            "en": {"hello": "Hello"},
        }
        i18n.set_language("en")
        assert i18n.get_language() == "en"
        assert i18n._("hello") == "Hello"

    def test_switch_to_unknown_language_falls_back_to_default(self):
        """切换到**不支持**的语言 → 回退 `DEFAULT_LANGUAGE`（不静默保留）。

        **旧用例为何不再成立**：原名 `test_switch_to_unknown_language_gets_empty_dict`，
        断言 `i18n._lang == "fr_FR"`（原样保留）与 `i18n._current == {}`。两者都基于
        已移除的状态，且"原样保留"与现行 `_normalize` 的 fail-loud 回退契约**相反**。
        现按真实契约断言：回退默认语言，且该语言下翻译可正常解析。
        """
        # 必须先置 `_loaded = True`：`set_language()` 内部先调 `_ensure_loaded()`，
        # 否则懒加载会用**真实 JSON** 覆盖下面这份精简的 `_translations`。
        i18n._loaded = True
        i18n._translations = {"zh_CN": {"hello": "你好"}}
        i18n.set_language("fr_FR")
        assert i18n.get_language() == i18n.DEFAULT_LANGUAGE
        assert i18n._("hello") == "你好"

    def test_triggers_lazy_load(self):
        """set_language 触发懒加载。"""
        assert i18n._loaded is False
        i18n.set_language("en")
        assert i18n._loaded is True


# ════════════════════════════════════════════════════════════
# get_language()
# ════════════════════════════════════════════════════════════

class TestGetLanguage:
    def test_returns_current_language(self):
        assert i18n.get_language() == "zh_CN"
        i18n.set_language("en")
        assert i18n.get_language() == "en"

    def test_language_isolated_from_previous_test_a(self):
        """★ 夹具契约（前半）：把语言设为**非默认**值，并留下脏的模块级状态。

        与下一个用例**配对**，锁定夹具"每个用例都从干净状态开始"的保证。
        判别力：夹具去掉 `_translations` / `_loaded` 重置 → 下一个用例读到这里的脏值而 FAIL。
        """
        i18n.set_language("en")
        assert i18n.get_language() == "en"
        # 故意留下脏的模块级状态（这两个是 globals，不随 ContextVar 隔离）
        i18n._translations = {"dirty": {"leaked": "LEAKED"}}
        i18n._loaded = True

    def test_state_isolated_from_previous_test_b(self):
        """★ 夹具契约（后半）：进入本用例时模块级状态必须已被夹具复位。

        依赖上一个用例（`..._a`）留下的脏值。这是**有意**的顺序耦合——测试按定义顺序
        执行，而该耦合正是"夹具是否复位"的可证伪判据。

        **注意（实测结论）**：语言（`_lang_var`）**不需要**夹具复位——pytest 让每个用例
        运行在独立 `Context`，`ContextVar` 天然跨用例隔离（实测：上一个用例设 `"en"` 后，
        本用例进入时 `get_language()` 已是 `'zh_CN'`）。真正会泄漏的是**模块级 globals**
        `_translations` / `_loaded`，故判别力对准这两项。

        判别力：夹具去掉 `_translations = {}` 或 `_loaded = False` → 本用例 FAIL。
        """
        assert i18n._loaded is False, "夹具必须把 _loaded 复位为 False"
        assert i18n._translations == {}, f"夹具必须清空 _translations；实际 {i18n._translations!r}"
        assert i18n.get_language() == i18n.DEFAULT_LANGUAGE

    def test_never_returns_none(self):
        """`get_language()` 永不返回 None（ContextVar 默认值即 DEFAULT_LANGUAGE）。"""
        assert i18n.get_language() is not None
        i18n.set_language("unsupported_lang")
        assert i18n.get_language() == i18n.DEFAULT_LANGUAGE


# ════════════════════════════════════════════════════════════
# _() — 翻译函数（核心 API）
# ════════════════════════════════════════════════════════════

class TestTranslate:
    def test_translates_known_key(self):
        """已知 key → 返回翻译文本。

        **旧断言为何不再成立**：原先设 `i18n._current = {...}` 再断言
        `i18n._("hello") == "你好"`。而 `_()` 的实现是
        `_translations.get(_lang_var.get(), {}).get(key, key)` —— **不读 `_current`**，
        那条设置一直是无效果的；去掉它后须按真实取值路径准备 `_translations`。
        """
        i18n._loaded = True  # 跳过 _load() 加载真实文件
        i18n._lang_var.set("zh_CN")
        i18n._translations = {"zh_CN": {"hello": "你好", "world": "世界"}}
        assert i18n._("hello") == "你好"
        assert i18n._("world") == "世界"

    def test_returns_key_itself_when_missing(self):
        """未知 key → 返回 key 自身（fallback）。"""
        i18n._loaded = True
        i18n._translations = {"zh_CN": {"hello": "你好"}}
        assert i18n._("unknown_key") == "unknown_key"

    def test_empty_key_returns_empty(self):
        """空字符串 key → 返回空字符串。"""
        i18n._loaded = True
        i18n._translations = {"zh_CN": {}}
        assert i18n._("") == ""

    def test_triggers_lazy_load(self):
        """首次调用 _() → 触发懒加载。"""
        assert i18n._loaded is False
        i18n._("any_key")
        assert i18n._loaded is True

    def test_t_reads_same_source_as_underscore(self):
        """★ 判别力护栏：`t()` 与 `_()` 同源取值（都走 `_lang_var` + `_translations`）。

        若实现被改回读某个 `_current` 副本、或两入口取值分叉，本用例 FAIL。
        """
        i18n._loaded = True
        i18n._lang_var.set("en")
        i18n._translations = {"en": {"k": "V"}}
        assert i18n._("k") == "V"
        assert i18n.t("k") == "V"
