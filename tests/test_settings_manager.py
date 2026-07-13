# tests/test_settings_manager.py
# UserPreferenceManager 单元测试 — _deep_merge / _deep_update / 缓存读写

import json
from unittest.mock import MagicMock, patch

from pilotstd.manager.settings_manager import UserPreferenceManager


class TestDeepMerge:
    """_deep_merge 递归合并测试"""

    def test_simple_override(self):
        defaults = {"a": 1, "b": 2}
        overrides = {"b": 3}
        result = UserPreferenceManager._deep_merge(defaults, overrides)
        assert result["a"] == 1
        assert result["b"] == 3

    def test_nested_partial_override(self):
        defaults = {"ui": {"theme": "light", "language": "zh-CN"}, "search": {"default_type": "GB/T"}}
        overrides = {"ui": {"theme": "dark"}}
        result = UserPreferenceManager._deep_merge(defaults, overrides)
        assert result["ui"]["theme"] == "dark"
        assert result["ui"]["language"] == "zh-CN"
        assert result["search"]["default_type"] == "GB/T"

    def test_new_top_level_key(self):
        defaults = {"a": 1}
        overrides = {"b": 2}
        result = UserPreferenceManager._deep_merge(defaults, overrides)
        assert result["a"] == 1
        assert result["b"] == 2

    def test_new_nested_key(self):
        defaults = {"ui": {"theme": "light"}}
        overrides = {"ui": {"language": "en"}}
        result = UserPreferenceManager._deep_merge(defaults, overrides)
        assert result["ui"]["theme"] == "light"
        assert result["ui"]["language"] == "en"

    def test_empty_overrides_returns_deep_copy(self):
        defaults = {"a": 1, "b": {"c": 2}}
        result = UserPreferenceManager._deep_merge(defaults, {})
        assert result == defaults
        result["b"]["c"] = 999
        assert defaults["b"]["c"] == 2  # 原对象未被修改


class TestDeepUpdate:
    """_deep_update 原地递归更新测试"""

    def test_simple_update(self):
        source = {"a": 1, "b": 2}
        UserPreferenceManager._deep_update(source, {"b": 3})
        assert source["a"] == 1
        assert source["b"] == 3

    def test_nested_partial_update(self):
        source = {"ui": {"theme": "light", "language": "zh-CN"}, "search": {"default_type": "GB/T"}}
        UserPreferenceManager._deep_update(source, {"ui": {"theme": "dark"}})
        assert source["ui"]["theme"] == "dark"
        assert source["ui"]["language"] == "zh-CN"
        assert source["search"]["default_type"] == "GB/T"

    def test_new_key_added(self):
        source = {"a": 1}
        UserPreferenceManager._deep_update(source, {"b": 2})
        assert source["a"] == 1
        assert source["b"] == 2


class TestPreferencesCache:
    """缓存读写测试"""

    def setup_method(self):
        UserPreferenceManager._cache = {}

    @patch("pilotstd.manager.settings_manager.Database")
    @patch("pilotstd.manager.settings_manager.get_db_path")
    def test_cache_hit_no_db_query(self, mock_get_db_path, mock_db_class):
        mock_get_db_path.return_value = "/fake/path"
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db

        UserPreferenceManager._cache[1] = {"ui": {"theme": "dark"}}
        result = UserPreferenceManager.get_preferences(1)
        assert result == {"ui": {"theme": "dark"}}
        mock_db.fetchone.assert_not_called()

    @patch("pilotstd.manager.settings_manager.Database")
    @patch("pilotstd.manager.settings_manager.get_db_path")
    def test_cache_miss_loads_from_db_and_merges_defaults(self, mock_get_db_path, mock_db_class):
        mock_get_db_path.return_value = "/fake/path"
        mock_db = MagicMock()
        mock_db.fetchone.return_value = {"settings": json.dumps({"ui": {"theme": "dark"}})}
        mock_db_class.return_value = mock_db

        result = UserPreferenceManager.get_preferences(1)
        assert result["ui"]["theme"] == "dark"
        assert result["ui"]["language"] == "zh-CN"
        assert result["search"]["default_standard_type"] == "GB/T"
        # _ensure_table_exists 也会调用 fetchone，调用次数 >= 2
        assert mock_db.fetchone.call_count >= 2

    @patch("pilotstd.manager.settings_manager.Database")
    @patch("pilotstd.manager.settings_manager.get_db_path")
    def test_new_user_returns_full_defaults(self, mock_get_db_path, mock_db_class):
        mock_get_db_path.return_value = "/fake/path"
        mock_db = MagicMock()
        mock_db.fetchone.return_value = None
        mock_db_class.return_value = mock_db

        result = UserPreferenceManager.get_preferences(1)
        assert result["ui"]["theme"] == "light"
        assert result["search"]["default_standard_type"] == "GB/T"
        mock_db.execute.assert_called()

    @patch("pilotstd.manager.settings_manager.Database")
    @patch("pilotstd.manager.settings_manager.get_db_path")
    def test_update_preferences_refreshes_cache(self, mock_get_db_path, mock_db_class):
        mock_get_db_path.return_value = "/fake/path"
        mock_db = MagicMock()
        mock_db.fetchone.return_value = {"settings": json.dumps({"ui": {"theme": "light"}})}
        mock_db_class.return_value = mock_db

        result = UserPreferenceManager.update_preferences(1, {"ui": {"theme": "dark"}})
        assert result["ui"]["theme"] == "dark"
        assert result["ui"]["language"] == "zh-CN"
        assert UserPreferenceManager._cache[1]["ui"]["theme"] == "dark"

    @patch("pilotstd.manager.settings_manager.Database")
    @patch("pilotstd.manager.settings_manager.get_db_path")
    def test_reset_preferences_clears_and_reloads(self, mock_get_db_path, mock_db_class):
        mock_get_db_path.return_value = "/fake/path"
        mock_db = MagicMock()
        mock_db.fetchone.return_value = {"settings": json.dumps({})}
        mock_db_class.return_value = mock_db

        result = UserPreferenceManager.reset_preferences(1)
        assert mock_db.execute.call_count >= 1
        assert result["ui"]["theme"] == "light"
        assert result["ui"]["language"] == "zh-CN"
        # 重置后返回完整的默认值
        assert result["ui"]["theme"] == "light"

    def test_clear_cache_single_user(self):
        UserPreferenceManager._cache = {1: {"a": 1}, 2: {"b": 2}}
        UserPreferenceManager.clear_cache(1)
        assert 1 not in UserPreferenceManager._cache
        assert 2 in UserPreferenceManager._cache

    def test_clear_cache_all_users(self):
        UserPreferenceManager._cache = {1: {"a": 1}, 2: {"b": 2}}
        UserPreferenceManager.clear_cache()
        assert UserPreferenceManager._cache == {}
