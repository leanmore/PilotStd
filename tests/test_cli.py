# tests/test_cli.py

import os
import sys

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import io
import json
import shutil
import tempfile
import unittest

from pilotstd.cli.commands import build_parser


class TestCLIParser(unittest.TestCase):
    def test_scan_parser(self):
        parser = build_parser()
        args = parser.parse_args(["scan", "/tmp/test"])
        self.assertEqual(args.command, "scan")
        self.assertEqual(args.paths, ["/tmp/test"])
        self.assertEqual(args.format, "csv")

    def test_scan_parser_json(self):
        parser = build_parser()
        args = parser.parse_args(["scan", "--format", "json", "/tmp/a", "/tmp/b"])
        self.assertEqual(args.paths, ["/tmp/a", "/tmp/b"])
        self.assertEqual(args.format, "json")

    def test_query_parser(self):
        parser = build_parser()
        args = parser.parse_args(["query", "--file", "standards.txt"])
        self.assertEqual(args.command, "query")
        self.assertEqual(args.file, "standards.txt")

    def test_download_parser(self):
        parser = build_parser()
        args = parser.parse_args(["download", "-f", "list.txt"])
        self.assertEqual(args.file, "list.txt")
        self.assertEqual(args.command, "download")

    def test_move_parser(self):
        parser = build_parser()
        args = parser.parse_args(["move", "-r", "/tmp/root", "a.pdf", "b.pdf"])
        self.assertEqual(args.root, "/tmp/root")
        self.assertEqual(args.files, ["a.pdf", "b.pdf"])

    def test_expire_parser(self):
        parser = build_parser()
        args = parser.parse_args(["expire", "old1.pdf"])
        self.assertEqual(args.files, ["old1.pdf"])

    def test_no_command_returns_none(self):
        parser = build_parser()
        args = parser.parse_args([])
        self.assertIsNone(args.command)


class TestCLIScan(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pilotstd_test_")
        self.test_file = os.path.join(self.tmp, "GB 19001-2020 质量管理.pdf")
        with open(self.test_file, "w") as f:
            f.write("test")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_cmd_scan_csv(self):
        from pilotstd.cli.commands import CLI

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            args = type("Args", (), {"paths": [self.tmp], "format": "csv"})()
            ret = CLI.cmd_scan(args)
            output = sys.stdout.getvalue()
            self.assertEqual(ret, 0)
            self.assertIn("GB", output)
            self.assertIn("19001", output)
        finally:
            sys.stdout = old_stdout

    def test_cmd_scan_json(self):
        from pilotstd.cli.commands import CLI

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            args = type("Args", (), {"paths": [self.tmp], "format": "json"})()
            ret = CLI.cmd_scan(args)
            self.assertEqual(ret, 0)
            data = json.loads(sys.stdout.getvalue())
            self.assertIsInstance(data, list)
        finally:
            sys.stdout = old_stdout


class TestCLIMove(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pilotstd_test_")
        self.test_file = os.path.join(self.tmp, "GB 19001-2020 质量管理.pdf")
        with open(self.test_file, "w") as f:
            f.write("test")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_cmd_move(self):
        from pilotstd.cli.commands import CLI

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            args = type(
                "Args",
                (),
                {"files": [self.test_file], "root": self.tmp, "dry_run": False},
            )()
            ret = CLI.cmd_move(args)
            self.assertEqual(ret, 0)
        finally:
            sys.stdout = old_stdout

    def test_cmd_expire(self):
        from pilotstd.cli.commands import CLI

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            args = type("Args", (), {"files": [self.test_file], "root": self.tmp})()
            ret = CLI.cmd_expire(args)
            self.assertEqual(ret, 0)
        finally:
            sys.stdout = old_stdout


# === _shared.py 覆盖 ===


class TestSharedMakeManager(unittest.TestCase):
    """_make_manager() 工具函数测试。"""

    def test_make_manager_returns_instance(self):
        """_make_manager 返回 StandardManager 实例，无参数时不崩溃。"""
        from pilotstd.cli.commands._shared import _make_manager
        from pilotstd.manager.facade import StandardManager

        mgr = _make_manager()
        self.assertIsInstance(mgr, StandardManager)

    def test_make_manager_custom_storage_root(self):
        """storage_root 参数应传递给配置（用临时目录，避免盘符根目录残留）。"""
        from pilotstd.cli.commands._shared import _make_manager

        with tempfile.TemporaryDirectory(prefix="pilotstd_test_") as td:
            storage_root = os.path.join(td, "custom", "path")
            mgr = _make_manager(storage_root=storage_root)
            self.assertEqual(mgr.cfg.get("storage.root_dir"), storage_root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
