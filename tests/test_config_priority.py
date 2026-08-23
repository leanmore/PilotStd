# tests/test_config_priority.py — PriorityConfigManager 测试

import json
import os
import sys
import tempfile
import unittest

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from pilotstd.core.config.priority import (
    ConfigPriority,
    PriorityConfigManager,
    get_priority_config,
)


class TestConfigPriorityEnum(unittest.TestCase):
    def test_values(self):
        self.assertEqual(ConfigPriority.FACTORY, 0)
        self.assertEqual(ConfigPriority.FILE, 1)
        self.assertEqual(ConfigPriority.ENV_LEGACY, 2)
        self.assertEqual(ConfigPriority.ENV_NEW, 2)

    def test_ordering(self):
        self.assertLess(ConfigPriority.FACTORY, ConfigPriority.FILE)
        self.assertLess(ConfigPriority.FILE, ConfigPriority.ENV_NEW)


class TestParseEnvValue(unittest.TestCase):
    def test_true_false(self):
        self.assertTrue(PriorityConfigManager._parse_env_value("true"))
        self.assertTrue(PriorityConfigManager._parse_env_value("True"))
        self.assertFalse(PriorityConfigManager._parse_env_value("false"))
        self.assertFalse(PriorityConfigManager._parse_env_value("FALSE"))

    def test_integer(self):
        self.assertEqual(PriorityConfigManager._parse_env_value("42"), 42)
        self.assertEqual(PriorityConfigManager._parse_env_value("0"), 0)

    def test_string(self):
        self.assertEqual(PriorityConfigManager._parse_env_value("hello"), "hello")
        self.assertEqual(PriorityConfigManager._parse_env_value(""), "")


class TestPriorityConfigManager(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmpdir, "test_config.json")

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_factory_defaults(self):
        mgr = PriorityConfigManager(self.config_path)
        self.assertEqual(mgr.get("STANDARD_ROOT"), "/data/standards")
        self.assertFalse(mgr.get("OCR_ENABLED"))
        self.assertEqual(mgr.get("PAGE_SIZE"), 20)
        self.assertEqual(mgr.get("LOG_LEVEL"), "INFO")

    def test_get_nonexistent_key_returns_default(self):
        mgr = PriorityConfigManager(self.config_path)
        self.assertIsNone(mgr.get("NONEXISTENT_KEY"))
        self.assertEqual(mgr.get("NONEXISTENT_KEY", "fallback"), "fallback")

    def test_file_overrides_factory(self):
        custom_root = os.path.join(self.tmpdir, "custom", "path")
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump({"STANDARD_ROOT": custom_root}, f)
        mgr = PriorityConfigManager(self.config_path)
        self.assertEqual(mgr.get("STANDARD_ROOT"), custom_root)

    def test_env_new_overrides_file(self):
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump({"TEST_KEY": "file_value"}, f)
        os.environ["PILOTSTD_TEST_KEY"] = "env_value"
        try:
            mgr = PriorityConfigManager(self.config_path)
            self.assertEqual(mgr.get("TEST_KEY"), "env_value")
        finally:
            del os.environ["PILOTSTD_TEST_KEY"]

    def test_env_legacy_vars(self):
        os.environ["STANDARD_ROOT"] = "/env/root"
        try:
            mgr = PriorityConfigManager(self.config_path)
            self.assertEqual(mgr.get("STANDARD_ROOT"), "/env/root")
        finally:
            del os.environ["STANDARD_ROOT"]

    def test_env_legacy_bool_parsing(self):
        os.environ["SUPERUSER"] = "true"
        try:
            mgr = PriorityConfigManager(self.config_path)
            self.assertTrue(mgr.get("SUPERUSER"))
        finally:
            del os.environ["SUPERUSER"]

    def test_get_with_source(self):
        mgr = PriorityConfigManager(self.config_path)
        result = mgr.get_with_source("STANDARD_ROOT")
        self.assertEqual(result["value"], "/data/standards")
        self.assertEqual(result["source"], "FACTORY")

    def test_get_with_source_env(self):
        os.environ["PILOTSTD_TEST_SRC_KEY"] = "src_value"
        try:
            mgr = PriorityConfigManager(self.config_path)
            result = mgr.get_with_source("TEST_SRC_KEY")
            self.assertEqual(result["value"], "src_value")
            self.assertIn(result["source"], ("ENV_NEW", "ENV_LEGACY"))
        finally:
            del os.environ["PILOTSTD_TEST_SRC_KEY"]

    def test_get_with_source_not_found(self):
        mgr = PriorityConfigManager(self.config_path)
        result = mgr.get_with_source("NONEXISTENT")
        self.assertIsNone(result["value"])
        self.assertEqual(result["source"], "NOT_FOUND")

    def test_set_file(self):
        mgr = PriorityConfigManager(self.config_path)
        self.assertTrue(mgr.set_file("NEW_KEY", "new_value"))
        self.assertEqual(mgr.get("NEW_KEY"), "new_value")
        # 验证持久化
        with open(self.config_path, "r", encoding="utf-8") as f:
            saved = json.load(f)
        self.assertEqual(saved["NEW_KEY"], "new_value")

    def test_reload(self):
        mgr = PriorityConfigManager(self.config_path)
        self.assertEqual(mgr.get("STANDARD_ROOT"), "/data/standards")
        # 直接修改文件
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump({"STANDARD_ROOT": "/reloaded/path"}, f)
        mgr.reload()
        self.assertEqual(mgr.get("STANDARD_ROOT"), "/reloaded/path")

    def test_get_all_effective(self):
        mgr = PriorityConfigManager(self.config_path)
        all_cfg = mgr.get_all_effective()
        self.assertIn("STANDARD_ROOT", all_cfg)
        self.assertIn("OCR_ENABLED", all_cfg)
        self.assertEqual(all_cfg["STANDARD_ROOT"]["source"], "FACTORY")

    def test_cache_behavior(self):
        mgr = PriorityConfigManager(self.config_path)
        first = mgr.get("STANDARD_ROOT")
        # 直接修改内部缓存——不应影响 get()（缓存命中）
        second = mgr.get("STANDARD_ROOT")
        self.assertEqual(first, second)


class TestGlobalSingleton(unittest.TestCase):
    def setUp(self):
        import pilotstd.core.config.priority as mod

        mod._default_manager = None

    def test_get_priority_config_returns_singleton(self):
        mgr1 = get_priority_config()
        mgr2 = get_priority_config()
        self.assertIs(mgr1, mgr2)


if __name__ == "__main__":
    unittest.main()
