"""i18n 模块单元测试 — 目标: 100% 覆盖所有 fallback 路径"""

from unittest.mock import mock_open, patch

import pytest

import pilotstd.i18n as i18n


@pytest.fixture(autouse=True)
def _reset_i18n_state():
    """每个测试前重置模块级全局状态。"""
    i18n._translations = {}
    i18n._current = {}
    i18n._lang = "zh_CN"
    i18n._loaded = False
    yield


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
        """首次调用 → 触发 _load + 设置 _current。"""
        assert i18n._loaded is False
        i18n._ensure_loaded()
        assert i18n._loaded is True
        assert isinstance(i18n._current, dict)

    def test_second_call_is_noop(self):
        """二次调用 → 不重复加载。"""
        i18n._ensure_loaded()
        with patch.object(i18n, "_load") as mock_load:
            i18n._ensure_loaded()
            mock_load.assert_not_called()

    def test_current_set_from_translations(self):
        """加载后 _current 指向当前语言翻译表。"""
        i18n._translations = {"zh_CN": {"hello": "你好"}}
        with patch.object(i18n, "_load"):  # 阻止 _load 覆盖 translations
            i18n._ensure_loaded()
        assert i18n._current == {"hello": "你好"}

    def test_current_empty_when_lang_missing(self):
        """当前语言不在翻译表中 → _current = {}。"""
        i18n._lang = "fr_FR"
        i18n._translations = {"zh_CN": {"hello": "你好"}}
        i18n._ensure_loaded()
        assert i18n._current == {}


# ════════════════════════════════════════════════════════════
# set_language() — 语言切换
# ════════════════════════════════════════════════════════════

class TestSetLanguage:
    def test_switch_to_known_language(self):
        """切换到已知语言 → _current 更新。"""
        i18n._loaded = True  # 跳过 _load() 加载真实文件
        i18n._translations = {
            "zh_CN": {"hello": "你好"},
            "en": {"hello": "Hello"},
        }
        i18n.set_language("en")
        assert i18n._lang == "en"
        assert i18n._current["hello"] == "Hello"

    def test_switch_to_unknown_language_gets_empty_dict(self):
        """切换到未知语言 → _current = {}。"""
        i18n._translations = {"zh_CN": {"hello": "你好"}}
        i18n.set_language("fr_FR")
        assert i18n._lang == "fr_FR"
        assert i18n._current == {}

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


# ════════════════════════════════════════════════════════════
# _() — 翻译函数（核心 API）
# ════════════════════════════════════════════════════════════

class TestTranslate:
    def test_translates_known_key(self):
        """已知 key → 返回翻译文本。"""
        i18n._loaded = True  # 跳过 _load() 加载真实文件
        i18n._current = {"hello": "你好", "world": "世界"}
        assert i18n._("hello") == "你好"

    def test_returns_key_itself_when_missing(self):
        """未知 key → 返回 key 自身（fallback）。"""
        i18n._current = {"hello": "你好"}
        assert i18n._("unknown_key") == "unknown_key"

    def test_empty_key_returns_empty(self):
        """空字符串 key → 返回空字符串。"""
        i18n._current = {}
        assert i18n._("") == ""

    def test_triggers_lazy_load(self):
        """首次调用 _() → 触发懒加载。"""
        assert i18n._loaded is False
        i18n._("any_key")
        assert i18n._loaded is True
