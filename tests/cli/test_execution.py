"""CLI 子命令执行逻辑测试 — 端到端最小验证"""

import argparse
import os
from unittest import mock

from pilotstd.cli.commands import build_parser

# ── 辅助 ──


def _args(*a: str) -> argparse.Namespace:
    """构建参数。--storage-root 是顶层参数，必须在子命令之前。"""
    return build_parser().parse_args(list(a))


def _pdf(path, name: str = "GB 12345-2020.pdf") -> str:
    fp = os.path.join(str(path), name)
    with open(fp, "w", encoding="utf-8") as f:
        f.write("%PDF-1.4")
    return fp


# ═══════════════════════════════════════════
# scan
# ═══════════════════════════════════════════


class TestScan:
    def test_csv_output(self, tmp_path, monkeypatch, capsys):
        m = mock.MagicMock()
        m.scan_directory.return_value = []
        monkeypatch.setattr("pilotstd.cli.commands.scan._make_manager", lambda **kw: m)
        from pilotstd.cli.commands.scan import cmd_scan

        _pdf(tmp_path)
        r = cmd_scan(_args("--storage-root", str(tmp_path), "scan", str(tmp_path)))
        out = capsys.readouterr().out
        assert r == 0
        assert "序号" in out  # CSV 表头

    def test_json_output(self, tmp_path, monkeypatch, capsys):
        from pilotstd.cli.commands.scan import cmd_scan

        _pdf(tmp_path)
        r = cmd_scan(_args("--storage-root", str(tmp_path), "scan", str(tmp_path), "--format", "json"))
        out = capsys.readouterr().out
        assert r == 0
        data = __import__("json").loads(out)
        assert isinstance(data, list)

    def test_multiple_paths(self, tmp_path, monkeypatch, capsys):
        m = mock.MagicMock()
        m.scan_directory.return_value = []
        monkeypatch.setattr("pilotstd.cli.commands.scan._make_manager", lambda **kw: m)
        from pilotstd.cli.commands.scan import cmd_scan

        d1 = tmp_path / "a"
        d1.mkdir()
        d2 = tmp_path / "b"
        d2.mkdir()
        _pdf(d1, "GB 1-2020.pdf")
        _pdf(d2, "GB 2-2020.pdf")
        r = cmd_scan(_args("--storage-root", str(tmp_path), "scan", str(d1), str(d2)))
        assert r == 0


# ═══════════════════════════════════════════
# normalize
# ═══════════════════════════════════════════


class TestNormalize:
    def test_csv_output(self, tmp_path, monkeypatch, capsys):
        m = mock.MagicMock()
        m.normalize_files.return_value = []
        monkeypatch.setattr("pilotstd.cli.commands.normalize._make_manager", lambda **kw: m)
        from pilotstd.cli.commands.normalize import cmd_normalize

        fp = _pdf(tmp_path)
        r = cmd_normalize(_args("--storage-root", str(tmp_path), "normalize", fp))
        out = capsys.readouterr().out
        assert r == 0
        assert "源文件" in out  # CSV 表头

    def test_json_output(self, tmp_path, monkeypatch, capsys):
        from pilotstd.cli.commands.normalize import cmd_normalize

        fp = _pdf(tmp_path)
        r = cmd_normalize(_args("--storage-root", str(tmp_path), "normalize", fp, "--format", "json"))
        out = capsys.readouterr().out
        assert r == 0
        data = __import__("json").loads(out)
        assert isinstance(data, list)

    def test_multiple_files(self, tmp_path, monkeypatch, capsys):
        m = mock.MagicMock()
        m.normalize_files.return_value = []
        monkeypatch.setattr("pilotstd.cli.commands.normalize._make_manager", lambda **kw: m)
        from pilotstd.cli.commands.normalize import cmd_normalize

        f1 = _pdf(tmp_path, "GB 1-2020.pdf")
        f2 = _pdf(tmp_path, "GB 2-2020.pdf")
        r = cmd_normalize(_args("--storage-root", str(tmp_path), "normalize", f1, f2))
        assert r == 0


# ═══════════════════════════════════════════
# move
# ═══════════════════════════════════════════


class TestMove:
    def test_dry_run(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr("pilotstd.cli.commands.move._make_manager", mock.MagicMock())
        from pilotstd.cli.commands.move import cmd_move

        fp = _pdf(tmp_path)
        r = cmd_move(_args("--storage-root", str(tmp_path), "move", fp, "--dry-run"))
        out = capsys.readouterr().out
        assert r == 0
        assert "预览" in out or "preview" in out.lower() or "移动" in out

    def test_dry_run_multiple_files(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr("pilotstd.cli.commands.move._make_manager", mock.MagicMock())
        from pilotstd.cli.commands.move import cmd_move

        f1 = _pdf(tmp_path, "GB 1-2020.pdf")
        f2 = _pdf(tmp_path, "GB 2-2020.pdf")
        r = cmd_move(_args("--storage-root", str(tmp_path), "move", f1, f2, "--dry-run"))
        assert r == 0


# ═══════════════════════════════════════════
# expire
# ═══════════════════════════════════════════


class TestExpire:
    def test_single_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("pilotstd.cli.commands.expire._make_manager", mock.MagicMock())
        from pilotstd.cli.commands.expire import cmd_expire

        fp = _pdf(tmp_path, "GB 12345-2000.pdf")
        r = cmd_expire(_args("--storage-root", str(tmp_path), "expire", fp))
        assert r == 0

    def test_multiple_files(self, tmp_path, monkeypatch):
        monkeypatch.setattr("pilotstd.cli.commands.expire._make_manager", mock.MagicMock())
        from pilotstd.cli.commands.expire import cmd_expire

        f1 = _pdf(tmp_path, "GB 1-2000.pdf")
        f2 = _pdf(tmp_path, "GB 2-2000.pdf")
        r = cmd_expire(_args("--storage-root", str(tmp_path), "expire", f1, f2))
        assert r == 0


# ═══════════════════════════════════════════
# query（mock）
# ═══════════════════════════════════════════


class TestQuery:
    def test_with_file(self, tmp_path, monkeypatch):
        # cmd_query 调 mgr.parser.parse() + mgr.query()，需返回正确类型
        m = mock.MagicMock()
        fake_parsed = mock.MagicMock()
        fake_parsed.std_name = ""
        fake_parsed.get_full_number.return_value = "GB 12345-2020"
        fake_parsed.next_action = "download"
        m.parser.parse.return_value = fake_parsed
        fake_result = mock.MagicMock()
        fake_result.standard_name = "测试标准"
        fake_result.status = "现行"
        fake_result.match_status = "exact"
        fake_stats = mock.MagicMock()
        fake_stats.found = 1
        fake_stats.adopted_restricted = 0
        m.query.return_value = ([fake_result], fake_stats)
        m.get_stage_summary.return_value = {"download": 1, "expire": 0, "pending": 0}
        monkeypatch.setattr("pilotstd.cli.commands.query._make_manager", lambda **kw: m)
        from pilotstd.cli.commands.query import cmd_query

        f = tmp_path / "s.txt"
        f.write_text("GB 12345-2020\n", encoding="utf-8")
        r = cmd_query(_args("--storage-root", str(tmp_path), "query", "--file", str(f)))
        assert r == 0

    def test_no_cache(self, tmp_path, monkeypatch):
        m = mock.MagicMock()
        fake_parsed = mock.MagicMock()
        fake_parsed.std_name = ""
        fake_parsed.get_full_number.return_value = "GB 12345-2020"
        fake_parsed.next_action = "download"
        m.parser.parse.return_value = fake_parsed
        fake_result = mock.MagicMock()
        fake_result.standard_name = "测试标准"
        fake_result.status = "现行"
        fake_result.match_status = "exact"
        fake_stats = mock.MagicMock()
        fake_stats.found = 1
        fake_stats.adopted_restricted = 0
        m.query.return_value = ([fake_result], fake_stats)
        m.get_stage_summary.return_value = {"download": 1, "expire": 0, "pending": 0}
        monkeypatch.setattr("pilotstd.cli.commands.query._make_manager", lambda **kw: m)
        from pilotstd.cli.commands.query import cmd_query

        f = tmp_path / "s.txt"
        f.write_text("GB 12345-2020\n", encoding="utf-8")
        r = cmd_query(_args("--storage-root", str(tmp_path), "query", "--file", str(f), "--no-cache"))
        assert r == 0


# ═══════════════════════════════════════════
# download（mock）
# ═══════════════════════════════════════════


class TestDownload:
    def test_with_file(self, tmp_path, monkeypatch):
        m = mock.MagicMock()
        fake_task = mock.MagicMock()
        fake_task.standard_number = "GB 12345-2020"
        fake_task.status = mock.MagicMock()
        fake_task.status.value = "downloaded"
        fake_task.saved_path = None
        fake_stats = mock.MagicMock()
        fake_stats.success = 1
        fake_stats.skipped_exists = 0
        fake_stats.skipped_adopted = 0
        fake_stats.failed = 0
        m.download_by_numbers.return_value = ([fake_task], fake_stats)
        monkeypatch.setattr("pilotstd.cli.commands.download._make_manager", lambda **kw: m)
        from pilotstd.cli.commands.download import cmd_download

        f = tmp_path / "s.txt"
        f.write_text("GB 12345-2020\n", encoding="utf-8")
        r = cmd_download(_args("--storage-root", str(tmp_path), "download", "--file", str(f)))
        assert r == 0


# ═══════════════════════════════════════════
# organize
# ═══════════════════════════════════════════


class TestOrganize:
    def test_with_source(self, tmp_path, monkeypatch):
        m = mock.MagicMock()
        m.scan_directory.return_value = []
        m.archive_standards.return_value = {"saved": 0, "skipped": 0}
        monkeypatch.setattr("pilotstd.cli.commands.organize._make_manager", lambda **kw: m)
        from pilotstd.cli.commands.organize import cmd_organize

        src = tmp_path / "src"
        src.mkdir()
        _pdf(src)
        r = cmd_organize(_args("--storage-root", str(tmp_path), "organize", "--source", str(src)))
        assert r == 0


# ═══════════════════════════════════════════
# auto
# ═══════════════════════════════════════════


class TestAuto:
    def test_basic(self, tmp_path, monkeypatch):
        m = mock.MagicMock()
        m.auto_run.return_value = None
        monkeypatch.setattr("pilotstd.cli.commands.auto._make_manager", lambda **kw: m)
        from pilotstd.cli.commands.auto import cmd_auto

        r = cmd_auto(_args("--storage-root", str(tmp_path), "auto", str(tmp_path)))
        assert r == 0
        m.auto_run.assert_called_once_with(str(tmp_path))

    def test_with_no_cache(self, tmp_path, monkeypatch):
        m = mock.MagicMock()
        m.auto_run.return_value = None
        monkeypatch.setattr("pilotstd.cli.commands.auto._make_manager", lambda **kw: m)
        from pilotstd.cli.commands.auto import cmd_auto

        r = cmd_auto(_args("--storage-root", str(tmp_path), "auto", str(tmp_path), "--no-cache"))
        assert r == 0


# ═══════════════════════════════════════════
# pending
# ═══════════════════════════════════════════


class TestPending:
    def test_basic(self, tmp_path, monkeypatch):
        m = mock.MagicMock()
        m.get_pending_items.return_value = []
        monkeypatch.setattr("pilotstd.cli.commands.pending._make_manager", lambda **kw: m)
        from pilotstd.cli.commands.pending import cmd_pending

        r = cmd_pending(_args("--storage-root", str(tmp_path), "pending"))
        assert r == 0

    def test_with_output(self, tmp_path, monkeypatch):
        m = mock.MagicMock()
        m.get_pending_items.return_value = []
        monkeypatch.setattr("pilotstd.cli.commands.pending._make_manager", lambda **kw: m)
        from pilotstd.cli.commands.pending import cmd_pending

        out = tmp_path / "p.csv"
        r = cmd_pending(_args("--storage-root", str(tmp_path), "pending", "--output", str(out)))
        assert r == 0


# ═══════════════════════════════════════════
# announce
# ═══════════════════════════════════════════


class TestAnnounce:
    def test_with_since(self, tmp_path, monkeypatch):
        m = mock.MagicMock()
        m.check_announcements_filtered.return_value = {
            "gb": {"matched": 0, "updated": 0},
        }
        monkeypatch.setattr("pilotstd.cli.commands.announce._make_manager", lambda **kw: m)
        from pilotstd.cli.commands.announce import cmd_announce

        r = cmd_announce(_args("--storage-root", str(tmp_path), "announce", "--since", "2026-01-01"))
        assert r == 0

    def test_with_type_gb(self, tmp_path, monkeypatch):
        m = mock.MagicMock()
        m.check_announcements_filtered.return_value = {
            "gb": {"matched": 0, "updated": 0},
        }
        monkeypatch.setattr("pilotstd.cli.commands.announce._make_manager", lambda **kw: m)
        from pilotstd.cli.commands.announce import cmd_announce

        r = cmd_announce(_args("--storage-root", str(tmp_path), "announce", "--type", "gb"))
        assert r == 0


# ═══════════════════════════════════════════
# task
# ═══════════════════════════════════════════


class TestTask:
    def test_basic(self, tmp_path, monkeypatch):
        m = mock.MagicMock()
        m.task_queue.list_all.return_value = []
        monkeypatch.setattr("pilotstd.cli.commands.task._make_manager", lambda **kw: m)
        from pilotstd.cli.commands.task import cmd_task

        r = cmd_task(_args("--storage-root", str(tmp_path), "task"))
        assert r == 0

    def test_with_limit(self, tmp_path, monkeypatch):
        m = mock.MagicMock()
        m.task_queue.list_all.return_value = []
        monkeypatch.setattr("pilotstd.cli.commands.task._make_manager", lambda **kw: m)
        from pilotstd.cli.commands.task import cmd_task

        r = cmd_task(_args("--storage-root", str(tmp_path), "task", "--limit", "10"))
        assert r == 0


# ═══════════════════════════════════════════
# validity
# ═══════════════════════════════════════════


class TestValidity:
    def test_basic(self, tmp_path, monkeypatch):
        m = mock.MagicMock()
        m.return_value = {"ok": True, "checked": 0, "changed": 0}
        monkeypatch.setattr("pilotstd.core.validity_checker.run_validity_check", m)
        from pilotstd.cli.commands.announce import cmd_validity

        r = cmd_validity(_args("validity"))
        assert r == 0

    def test_force(self, tmp_path, monkeypatch):
        m = mock.MagicMock()
        m.return_value = {"ok": True, "checked": 0, "changed": 0}
        monkeypatch.setattr("pilotstd.core.validity_checker.run_validity_check", m)
        from pilotstd.cli.commands.announce import cmd_validity

        r = cmd_validity(_args("validity", "--force"))
        assert r == 0
