# tests/gui/test_settings_io_flow_engine.py
"""SettingsConfigIOEngine 单元测试 — 纯 Python，不启动 QApplication。

覆盖 8 个静态方法（4 序列化 + 4 反序列化）的：
- 正常路径：完整数据输入/输出
- 边界值：空 dict、None、缺失键、空列表
- 类型错误：错误类型的值回退默认值
- 往返一致性：serialize → deserialize 结果与原始一致
"""

from __future__ import annotations

import pytest

from pilotstd.ui.core.handlers.settings_io_flow_engine import SettingsConfigIOEngine


@pytest.fixture
def engine() -> SettingsConfigIOEngine:
    return SettingsConfigIOEngine()


# ═══════════════════════════════════════════════════════════════════
# DEFAULT 常量完整性
# ═══════════════════════════════════════════════════════════════════


class TestDefaults:
    def test_default_general_keys(self):
        assert "appearance.language" in SettingsConfigIOEngine.DEFAULT_GENERAL
        assert "appearance.skip_welcome" in SettingsConfigIOEngine.DEFAULT_GENERAL
        assert "appearance.column_visibility" in SettingsConfigIOEngine.DEFAULT_GENERAL
        assert SettingsConfigIOEngine.DEFAULT_GENERAL["appearance.column_visibility"] == [True] * 9

    def test_default_appearance_keys(self):
        assert "appearance.theme" in SettingsConfigIOEngine.DEFAULT_APPEARANCE
        assert "appearance.icon_theme" in SettingsConfigIOEngine.DEFAULT_APPEARANCE

    def test_default_library_keys(self):
        d = SettingsConfigIOEngine.DEFAULT_LIBRARY
        assert "storage.root_dir" in d
        assert "scan.skip_folders" in d
        assert "scan.extensions" in d
        assert "scan.exclude_patterns" in d

    def test_default_advanced_keys(self):
        d = SettingsConfigIOEngine.DEFAULT_ADVANCED
        assert "network.proxy" in d
        assert "ocr.baidu_api_key" in d
        assert "query.announcement_url" in d


# ═══════════════════════════════════════════════════════════════════
# serialize_general
# ═══════════════════════════════════════════════════════════════════


class TestSerializeGeneral:
    def test_normal(self, engine):
        data = {"appearance.language": "en", "appearance.skip_welcome": True}
        result = engine.serialize_general(data)
        assert result["appearance.language"] == "en"
        assert result["appearance.skip_welcome"] is True
        assert "appearance.column_visibility" in result

    def test_empty_dict_returns_all_defaults(self, engine):
        result = engine.serialize_general({})
        assert result == SettingsConfigIOEngine.DEFAULT_GENERAL

    def test_none_returns_all_defaults(self, engine):
        result = engine.serialize_general(None)  # type: ignore[arg-type]
        assert result == SettingsConfigIOEngine.DEFAULT_GENERAL

    def test_partial_fills_missing(self, engine):
        result = engine.serialize_general({"appearance.language": "zh_TW"})
        assert result["appearance.language"] == "zh_TW"
        assert result["appearance.skip_welcome"] is False
        assert result["appearance.column_visibility"] == [True] * 9

    def test_extra_keys_filtered(self, engine):
        result = engine.serialize_general({"appearance.language": "en", "unknown_key": 999})
        assert "unknown_key" not in result
        assert result["appearance.language"] == "en"


# ═══════════════════════════════════════════════════════════════════
# deserialize_general
# ═══════════════════════════════════════════════════════════════════


class TestDeserializeGeneral:
    def test_normal(self, engine):
        data = {"appearance.language": "en", "appearance.skip_welcome": True}
        result = engine.deserialize_general(data)
        assert result["appearance.language"] == "en"

    def test_none_returns_defaults(self, engine):
        result = engine.deserialize_general(None)
        assert result == SettingsConfigIOEngine.DEFAULT_GENERAL

    def test_string_returns_defaults(self, engine):
        result = engine.deserialize_general("bad")  # type: ignore[arg-type]
        assert result == SettingsConfigIOEngine.DEFAULT_GENERAL

    def test_missing_key_fills_default(self, engine):
        result = engine.deserialize_general({})
        assert result["appearance.language"] == "zh_CN"

    def test_type_mismatch_returns_default_for_key(self, engine):
        result = engine.deserialize_general({"appearance.language": 123})
        assert result["appearance.language"] == "zh_CN"

    def test_override_default(self, engine):
        result = engine.deserialize_general(
            {},
            {"appearance.language": "zh_TW"},
        )
        assert result["appearance.language"] == "zh_TW"

    def test_data_overrides_both_defaults(self, engine):
        result = engine.deserialize_general(
            {"appearance.language": "en"},
            {"appearance.language": "zh_TW"},
        )
        assert result["appearance.language"] == "en"

    def test_column_visibility_empty_list_preserved(self, engine):
        """空列表是合法值（用户可能隐藏所有列），不过滤。"""
        result = engine.deserialize_general({"appearance.column_visibility": []})
        assert result["appearance.column_visibility"] == []


# ═══════════════════════════════════════════════════════════════════
# serialize_appearance / deserialize_appearance
# ═══════════════════════════════════════════════════════════════════


class TestSerializeAppearance:
    def test_normal(self, engine):
        result = engine.serialize_appearance({"appearance.theme": "暗夜模式"})
        assert result["appearance.theme"] == "暗夜模式"
        assert result["appearance.icon_theme"] == "default"

    def test_empty_returns_defaults(self, engine):
        result = engine.serialize_appearance({})
        assert result == SettingsConfigIOEngine.DEFAULT_APPEARANCE


class TestDeserializeAppearance:
    def test_normal(self, engine):
        result = engine.deserialize_appearance({"appearance.theme": "暗夜模式"})
        assert result["appearance.theme"] == "暗夜模式"

    def test_none_returns_defaults(self, engine):
        result = engine.deserialize_appearance(None)
        assert result == SettingsConfigIOEngine.DEFAULT_APPEARANCE

    def test_type_mismatch(self, engine):
        result = engine.deserialize_appearance({"appearance.theme": 456})
        assert result["appearance.theme"] == "经典白"

    def test_override_default(self, engine):
        result = engine.deserialize_appearance({}, {"appearance.theme": "暗夜模式"})
        assert result["appearance.theme"] == "暗夜模式"


# ═══════════════════════════════════════════════════════════════════
# serialize_library / deserialize_library
# ═══════════════════════════════════════════════════════════════════


class TestSerializeLibrary:
    def test_normal(self, engine):
        data = {"storage.root_dir": "/data", "organize.auto_clean_source": True}
        result = engine.serialize_library(data)
        assert result["storage.root_dir"] == "/data"
        assert result["organize.auto_clean_source"] is True
        assert "scan.skip_folders" in result

    def test_list_values(self, engine):
        data = {"scan.skip_folders": ["a", "b"], "scan.extensions": [".pdf"]}
        result = engine.serialize_library(data)
        assert result["scan.skip_folders"] == ["a", "b"]
        assert result["scan.extensions"] == [".pdf"]

    def test_empty_returns_all_defaults(self, engine):
        result = engine.serialize_library({})
        assert result == SettingsConfigIOEngine.DEFAULT_LIBRARY


class TestDeserializeLibrary:
    def test_normal(self, engine):
        result = engine.deserialize_library({"storage.root_dir": "/mnt/data"})
        assert result["storage.root_dir"] == "/mnt/data"

    def test_none_returns_defaults(self, engine):
        result = engine.deserialize_library(None)
        assert result == SettingsConfigIOEngine.DEFAULT_LIBRARY

    def test_type_mismatch_list_vs_str(self, engine):
        result = engine.deserialize_library({"scan.skip_folders": "not_a_list"})
        assert result["scan.skip_folders"] == ["过期作废"]

    def test_type_mismatch_bool_vs_str(self, engine):
        result = engine.deserialize_library({"organize.auto_clean_source": "yes"})
        assert result["organize.auto_clean_source"] is False

    def test_override_default(self, engine):
        result = engine.deserialize_library({}, {"storage.root_dir": "/custom"})
        assert result["storage.root_dir"] == "/custom"

    def test_data_overrides_override(self, engine):
        result = engine.deserialize_library(
            {"storage.root_dir": "/data"},
            {"storage.root_dir": "/custom"},
        )
        assert result["storage.root_dir"] == "/data"


# ═══════════════════════════════════════════════════════════════════
# serialize_advanced / deserialize_advanced
# ═══════════════════════════════════════════════════════════════════


class TestSerializeAdvanced:
    def test_normal(self, engine):
        data = {"network.proxy": "http://proxy:8080", "query.use_cache": False}
        result = engine.serialize_advanced(data)
        assert result["network.proxy"] == "http://proxy:8080"
        assert result["query.use_cache"] is False
        assert "ocr.baidu_api_key" in result

    def test_empty_returns_all_defaults(self, engine):
        result = engine.serialize_advanced({})
        assert result == SettingsConfigIOEngine.DEFAULT_ADVANCED

    def test_sensitive_keys(self, engine):
        result = engine.serialize_advanced({"ocr.baidu_api_key": "sk-xxx"})
        assert result["ocr.baidu_api_key"] == "sk-xxx"
        assert result["ocr.baidu_secret_key"] == ""


class TestDeserializeAdvanced:
    def test_normal(self, engine):
        result = engine.deserialize_advanced({"network.proxy": "socks5://localhost"})
        assert result["network.proxy"] == "socks5://localhost"

    def test_none_returns_defaults(self, engine):
        result = engine.deserialize_advanced(None)
        assert result == SettingsConfigIOEngine.DEFAULT_ADVANCED

    def test_list_returns_all_defaults(self, engine):
        result = engine.deserialize_advanced([1, 2, 3])  # type: ignore[arg-type]
        assert result == SettingsConfigIOEngine.DEFAULT_ADVANCED

    def test_type_mismatch_bool_vs_int(self, engine):
        result = engine.deserialize_advanced({"query.use_cache": 1})
        assert result["query.use_cache"] is True  # int ≠ bool 类型检查

    def test_override_default(self, engine):
        result = engine.deserialize_advanced({}, {"network.proxy": "http://overridden"})
        assert result["network.proxy"] == "http://overridden"


# ═══════════════════════════════════════════════════════════════════
# 往返测试
# ═══════════════════════════════════════════════════════════════════


class TestRoundtrip:
    def test_general_roundtrip(self, engine):
        original = {
            "appearance.language": "en",
            "appearance.skip_welcome": True,
            "appearance.column_visibility": [True, False] + [True] * 7,
            "appearance.hyphen_style": False,
        }
        serialized = engine.serialize_general(original)
        restored = engine.deserialize_general(serialized)
        for key in original:
            assert restored[key] == original[key]

    def test_appearance_roundtrip(self, engine):
        original = {"appearance.theme": "暗夜模式", "appearance.icon_theme": "compass_book"}
        serialized = engine.serialize_appearance(original)
        restored = engine.deserialize_appearance(serialized)
        assert restored == original

    def test_library_roundtrip(self, engine):
        original = {
            "storage.root_dir": "/data/docs",
            "storage.expire_folder": "旧版",
            "scan.skip_folders": ["tmp", "bak"],
            "scan.extensions": [".pdf"],
        }
        serialized = engine.serialize_library(original)
        restored = engine.deserialize_library(serialized)
        for key in original:
            assert restored[key] == original[key]

    def test_advanced_roundtrip(self, engine):
        original = {
            "network.proxy": "http://localhost:3128",
            "query.use_cache": False,
            "ocr.baidu_api_key": "key123",
            "query.announcement_url": "http://api.example.com",
        }
        serialized = engine.serialize_advanced(original)
        restored = engine.deserialize_advanced(serialized)
        for key in original:
            assert restored[key] == original[key]


# ═══════════════════════════════════════════════════════════════════
# 新增：模块级常量
# ═══════════════════════════════════════════════════════════════════


class TestModuleConstants:
    def test_icon_options_has_four_entries(self):
        from pilotstd.ui.core.handlers.settings_io_flow_engine import ICON_OPTIONS

        assert len(ICON_OPTIONS) == 4
        assert ICON_OPTIONS["默认"] == "default"

    def test_lang_codes_order(self):
        from pilotstd.ui.core.handlers.settings_io_flow_engine import LANG_CODES

        assert LANG_CODES == ["zh_CN", "zh_TW", "en"]

    def test_ocr_credential_fields_structure(self):
        from pilotstd.ui.core.handlers.settings_io_flow_engine import OCR_CREDENTIAL_FIELDS

        assert len(OCR_CREDENTIAL_FIELDS) == 6
        for item in OCR_CREDENTIAL_FIELDS:
            assert len(item) == 3
            attr, key, hint = item
            assert attr.startswith("_ocr_")
            assert key.startswith("ocr.")


# ═══════════════════════════════════════════════════════════════════
# 新增：图标主题映射
# ═══════════════════════════════════════════════════════════════════


class TestIconMapping:
    def test_get_icon_internal_key_known(self, engine):
        assert engine.get_icon_internal_key("指南针") == "compass_book"
        assert engine.get_icon_internal_key("默认") == "default"

    def test_get_icon_internal_key_unknown_returns_default(self, engine):
        assert engine.get_icon_internal_key("不存在") == "default"
        assert engine.get_icon_internal_key("") == "default"

    def test_get_icon_display_name_known(self, engine):
        assert engine.get_icon_display_name("compass_book") == "指南针"
        assert engine.get_icon_display_name("lighthouse_folder") == "灯塔"

    def test_get_icon_display_name_unknown_returns_default(self, engine):
        assert engine.get_icon_display_name("nonexistent") == "默认"
        assert engine.get_icon_display_name("") == "默认"

    def test_icon_roundtrip(self, engine):
        """显示名 → 内部键 → 显示名 应一致。"""
        for display in ["默认", "指南针", "放大镜", "灯塔"]:
            key = engine.get_icon_internal_key(display)
            back = engine.get_icon_display_name(key)
            assert back == display


# ═══════════════════════════════════════════════════════════════════
# 新增：语言代码解析
# ═══════════════════════════════════════════════════════════════════


class TestLanguageCode:
    def test_resolve_valid_indices(self, engine):
        assert engine.resolve_language_code(0) == "zh_CN"
        assert engine.resolve_language_code(1) == "zh_TW"
        assert engine.resolve_language_code(2) == "en"

    def test_resolve_out_of_bounds_returns_default(self, engine):
        assert engine.resolve_language_code(-1) == "zh_CN"
        assert engine.resolve_language_code(3) == "zh_CN"
        assert engine.resolve_language_code(999) == "zh_CN"


# ═══════════════════════════════════════════════════════════════════
# 新增：逗号分隔文本解析
# ═══════════════════════════════════════════════════════════════════


class TestParseCommaSeparated:
    def test_normal(self, engine):
        assert engine.parse_comma_separated("a, b, c") == ["a", "b", "c"]

    def test_no_spaces(self, engine):
        assert engine.parse_comma_separated("pdf,doc,txt") == ["pdf", "doc", "txt"]

    def test_extra_whitespace(self, engine):
        assert engine.parse_comma_separated("  a  ,  b  ,  c  ") == ["a", "b", "c"]

    def test_empty_string(self, engine):
        assert engine.parse_comma_separated("") == []

    def test_whitespace_only(self, engine):
        assert engine.parse_comma_separated("   ") == []

    def test_none_input(self, engine):
        assert engine.parse_comma_separated(None) == []  # type: ignore[arg-type]

    def test_single_item(self, engine):
        assert engine.parse_comma_separated(".pdf") == [".pdf"]

    def test_empty_items_filtered(self, engine):
        assert engine.parse_comma_separated("a,,b, ,c") == ["a", "b", "c"]


class TestParseCommaSeparatedWithFallback:
    def test_normal_ignores_fallback(self, engine):
        result = engine.parse_comma_separated_with_fallback("a, b", ["x"])
        assert result == ["a", "b"]

    def test_empty_uses_fallback(self, engine):
        result = engine.parse_comma_separated_with_fallback("", [".pdf", ".doc"])
        assert result == [".pdf", ".doc"]

    def test_whitespace_only_uses_fallback(self, engine):
        result = engine.parse_comma_separated_with_fallback("   ", ["fallback"])
        assert result == ["fallback"]

    def test_fallback_not_mutated(self, engine):
        """验证 fallback 列表不被原方法修改。"""
        fb = ["x", "y"]
        engine.parse_comma_separated_with_fallback("", fb)
        assert fb == ["x", "y"]
