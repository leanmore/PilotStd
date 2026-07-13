"""验证命令行参数解析正确性 — 覆盖全部 12 个子命令"""

from pilotstd.cli.commands import build_parser


class TestCLIScan:
    def test_scan_single_path(self):
        parser = build_parser()
        args = parser.parse_args(["scan", "/tmp/test"])
        assert args.command == "scan"
        assert args.paths == ["/tmp/test"]

    def test_scan_multiple_paths(self):
        parser = build_parser()
        args = parser.parse_args(["scan", "/tmp/a", "/tmp/b", "/tmp/c"])
        assert args.command == "scan"
        assert args.paths == ["/tmp/a", "/tmp/b", "/tmp/c"]

    def test_scan_with_format_json(self):
        parser = build_parser()
        args = parser.parse_args(["scan", "/tmp/test", "--format", "json"])
        assert args.format == "json"

    def test_scan_default_format_is_csv(self):
        parser = build_parser()
        args = parser.parse_args(["scan", "/tmp/test"])
        assert args.format == "csv"


class TestCLIQuery:
    def test_query_with_file(self):
        parser = build_parser()
        args = parser.parse_args(["query", "--file", "std_list.txt"])
        assert args.command == "query"
        assert args.file == "std_list.txt"

    def test_query_short_flag(self):
        parser = build_parser()
        args = parser.parse_args(["query", "-f", "std_list.txt"])
        assert args.file == "std_list.txt"

    def test_query_no_cache(self):
        parser = build_parser()
        args = parser.parse_args(["query", "--file", "std_list.txt", "--no-cache"])
        assert args.no_cache is True

    def test_query_no_cache_default_false(self):
        parser = build_parser()
        args = parser.parse_args(["query", "-f", "std_list.txt"])
        assert args.no_cache is False


class TestCLIDownload:
    def test_download_with_file(self):
        parser = build_parser()
        args = parser.parse_args(["download", "--file", "std_list.txt"])
        assert args.command == "download"
        assert args.file == "std_list.txt"

    def test_download_short_flag(self):
        parser = build_parser()
        args = parser.parse_args(["download", "-f", "std_list.txt"])
        assert args.file == "std_list.txt"


class TestCLIOrganize:
    def test_organize_with_source(self):
        parser = build_parser()
        args = parser.parse_args(["organize", "--source", "/tmp/data"])
        assert args.command == "organize"
        assert args.source == "/tmp/data"

    def test_organize_short_flag(self):
        parser = build_parser()
        args = parser.parse_args(["organize", "-s", "/tmp/data"])
        assert args.source == "/tmp/data"

    def test_organize_default_format(self):
        parser = build_parser()
        args = parser.parse_args(["organize", "-s", "/tmp/data"])
        assert args.format == "csv"


class TestCLIAuto:
    def test_auto_basic(self):
        parser = build_parser()
        args = parser.parse_args(["auto", "/tmp/data"])
        assert args.command == "auto"
        assert args.path == "/tmp/data"

    def test_auto_with_no_cache(self):
        parser = build_parser()
        args = parser.parse_args(["auto", "/tmp/data", "--no-cache"])
        assert args.no_cache is True

    def test_auto_with_format(self):
        parser = build_parser()
        args = parser.parse_args(["auto", "/tmp/data", "--format", "json"])
        assert args.format == "json"

    def test_auto_default_format_is_csv(self):
        parser = build_parser()
        args = parser.parse_args(["auto", "/tmp/data"])
        assert args.format == "csv"


class TestCLIPending:
    def test_pending_basic(self):
        parser = build_parser()
        args = parser.parse_args(["pending"])
        assert args.command == "pending"

    def test_pending_with_output(self):
        parser = build_parser()
        args = parser.parse_args(["pending", "--output", "report.csv"])
        assert args.output == "report.csv"

    def test_pending_short_output_flag(self):
        parser = build_parser()
        args = parser.parse_args(["pending", "-o", "report.csv"])
        assert args.output == "report.csv"


class TestCLINormalize:
    def test_normalize_single_file(self):
        parser = build_parser()
        args = parser.parse_args(["normalize", "file1.pdf"])
        assert args.command == "normalize"
        assert args.files == ["file1.pdf"]

    def test_normalize_multiple_files(self):
        parser = build_parser()
        args = parser.parse_args(["normalize", "a.pdf", "b.pdf", "c.pdf"])
        assert args.files == ["a.pdf", "b.pdf", "c.pdf"]


class TestCLIAnnounce:
    def test_announce_basic(self):
        parser = build_parser()
        args = parser.parse_args(["announce"])
        assert args.command == "announce"
        assert args.limit == 10

    def test_announce_with_since(self):
        parser = build_parser()
        args = parser.parse_args(["announce", "--since", "2026-01-01"])
        assert args.since == "2026-01-01"

    def test_announce_with_limit(self):
        parser = build_parser()
        args = parser.parse_args(["announce", "--limit", "5"])
        assert args.limit == 5

    def test_announce_with_type(self):
        parser = build_parser()
        args = parser.parse_args(["announce", "--type", "gb"])
        assert args.type == "gb"

    def test_announce_type_hb(self):
        parser = build_parser()
        args = parser.parse_args(["announce", "--type", "hb"])
        assert args.type == "hb"

    def test_announce_type_db(self):
        parser = build_parser()
        args = parser.parse_args(["announce", "--type", "db"])
        assert args.type == "db"


class TestCLITask:
    def test_task_basic(self):
        parser = build_parser()
        args = parser.parse_args(["task"])
        assert args.command == "task"
        assert args.limit == 50

    def test_task_with_limit(self):
        parser = build_parser()
        args = parser.parse_args(["task", "--limit", "10"])
        assert args.limit == 10


class TestCLIMove:
    def test_move_basic(self):
        parser = build_parser()
        args = parser.parse_args(["move", "file.pdf"])
        assert args.command == "move"
        assert args.files == ["file.pdf"]

    def test_move_with_root(self):
        parser = build_parser()
        args = parser.parse_args(["move", "file.pdf", "--root", "/library"])
        assert args.root == "/library"

    def test_move_dry_run(self):
        parser = build_parser()
        args = parser.parse_args(["move", "file.pdf", "--dry-run"])
        assert args.dry_run is True

    def test_move_dry_run_default_false(self):
        parser = build_parser()
        args = parser.parse_args(["move", "file.pdf"])
        assert args.dry_run is False


class TestCLIExpire:
    def test_expire_basic(self):
        parser = build_parser()
        args = parser.parse_args(["expire", "file.pdf"])
        assert args.command == "expire"
        assert args.files == ["file.pdf"]

    def test_expire_with_root(self):
        parser = build_parser()
        args = parser.parse_args(["expire", "file.pdf", "--root", "/library"])
        assert args.root == "/library"


class TestCLIValidity:
    def test_validity_basic(self):
        parser = build_parser()
        args = parser.parse_args(["validity"])
        assert args.command == "validity"

    def test_validity_force(self):
        parser = build_parser()
        args = parser.parse_args(["validity", "--force"])
        assert args.force is True

    def test_validity_short_force_flag(self):
        parser = build_parser()
        args = parser.parse_args(["validity", "-f"])
        assert args.force is True

    def test_validity_force_default_false(self):
        parser = build_parser()
        args = parser.parse_args(["validity"])
        assert args.force is False


class TestCLIGlobalOptions:
    def test_storage_root_option(self):
        parser = build_parser()
        args = parser.parse_args(["--storage-root", "/library", "scan", "/tmp"])
        assert args.storage_root == "/library"

    def test_storage_root_short_flag(self):
        parser = build_parser()
        args = parser.parse_args(["-r", "/library", "scan", "/tmp"])
        assert args.storage_root == "/library"

    def test_no_command_shows_help(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.command is None
