# tests/test_config_migrate.py — 配置迁移模块测试

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from pilotstd.core.config.migrate import export_rules, import_rules


class TestExportRules(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.export_path = os.path.join(self.tmpdir, 'exported_rules.json')

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_export_empty_rules(self):
        config = MagicMock()
        config.get.return_value = '[]'
        result = export_rules(config, self.export_path)
        self.assertTrue(result)
        self.assertTrue(os.path.exists(self.export_path))
        with open(self.export_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.assertEqual(data['version'], '1.0')
        self.assertEqual(data['rules'], [])

    def test_export_with_rules(self):
        config = MagicMock()
        config.get.return_value = '[{"name": "test_rule"}]'
        result = export_rules(config, self.export_path)
        self.assertTrue(result)
        with open(self.export_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.assertEqual(len(data['rules']), 1)

    def test_export_list_rules(self):
        config = MagicMock()
        config.get.return_value = [{'name': 'rule1'}]
        result = export_rules(config, self.export_path)
        self.assertTrue(result)

    def test_export_invalid_dir(self):
        config = MagicMock()
        config.get.return_value = '[]'
        bad_path = os.path.join(self.tmpdir, 'nonexistent', 'deep', 'rules.json')
        result = export_rules(config, bad_path)
        self.assertTrue(result)


class TestImportRules(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.import_path = os.path.join(self.tmpdir, 'import_rules.json')

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_import_nonexistent_file(self):
        config = MagicMock()
        result = import_rules(config, '/nonexistent/path/rules.json')
        self.assertEqual(result, -1)

    def test_import_valid_file(self):
        with open(self.import_path, 'w', encoding='utf-8') as f:
            json.dump({'rules': [{'name': 'new_rule', 'type': 'xpath'}]}, f)
        config = MagicMock()
        config.get.return_value = '[]'
        result = import_rules(config, self.import_path)
        self.assertEqual(result, 1)
        self.assertTrue(config.set.called)
        self.assertTrue(config.save.called)

    def test_import_invalid_json(self):
        with open(self.import_path, 'w', encoding='utf-8') as f:
            f.write('not valid json{{{')
        config = MagicMock()
        result = import_rules(config, self.import_path)
        self.assertEqual(result, -1)

    def test_import_skips_duplicates(self):
        with open(self.import_path, 'w', encoding='utf-8') as f:
            json.dump({'rules': [{'name': 'existing_rule'}]}, f)
        config = MagicMock()
        config.get.return_value = '[{"name": "existing_rule"}]'
        result = import_rules(config, self.import_path)
        self.assertEqual(result, 0)


if __name__ == '__main__':
    unittest.main()
