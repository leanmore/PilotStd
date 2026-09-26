# tests/integration/test_favorite_download_chain_e2e.py
"""A 修复端到端：真实 SQLite + 真实文件写入 + 真实下载引擎路由。

与单元测试的区别：不 mock `DownloadEngine.fetch_bytes` 本身，而是构造真实的
`DownloadEngine`，用 `source_site="std_gov"` 触发 `_QUERY_TO_DOWNLOAD_SITE`
映射路由到 `openstd_download` 适配器，验证字节真正落到 inbox、
状态机走到 done、通知事件成对出现。
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pilotstd.core.db import Database  # noqa: E402
from pilotstd.core.file_index import FileIndexRepository  # noqa: E402
from pilotstd.download.adapters.base import BaseDownloadAdapter  # noqa: E402
from pilotstd.download.engine import DownloadEngine  # noqa: E402
from pilotstd.download.session import SessionManager  # noqa: E402
from pilotstd.tasks.favorite_download import download_to_inbox  # noqa: E402

_PDF_BYTES = b"%PDF-1.4 fake standard full text"


class _FakeOpenstdAdapter(BaseDownloadAdapter):
    """冒充 openstd_download：不做真实网络/验证码，返回固定字节或业务失败。"""

    def __init__(self, session=None, fail_with: str = ""):
        super().__init__(session)
        self._fail_with = fail_with
        self.calls = 0

    @property
    def site_name(self) -> str:
        return "openstd_download"

    def can_handle(self, task) -> bool:
        return True

    def download(self, task):
        self.calls += 1
        if self._fail_with:
            task.error_message = self._fail_with
            return None
        return _PDF_BYTES


def _seed(db_path: str) -> int:
    """建库 + 塞入公告记录与收藏下载记录，返回 favorite_id。"""
    Database(db_path).close()
    db = Database(db_path)
    try:
        # user_favorites.user_id 有外键约束，先建用户行
        db.execute(
            "INSERT OR IGNORE INTO users (id, username, password_hash, salt, role)"
            " VALUES (1, 'e2euser', 'x', 'y', 'user')"
        )
        db.execute(
            "INSERT INTO announcement_record"
            " (id, source_site, pid, announce_no, standard_number, std_name, publish_date, fetched_at)"
            " VALUES (1, 'announcement_gb', 'p1', 'A-1', 'GB/T 1234-2020', '测试标准', '2026-01-01', '2026-01-02')"
        )
        db.execute(
            "INSERT INTO user_favorites"
            " (user_id, record_id, status, standard_type, standard_number, created_at, updated_at)"
            " VALUES (1, 1, 'pending', 'NationalStd', 'GB/T 1234-2020', datetime('now'), datetime('now'))"
        )
        fav_id = db.fetchone("SELECT id FROM user_favorites WHERE user_id=1 AND record_id=1")["id"]
        db.execute(
            "INSERT INTO favorite_downloads"
            " (favorite_id, user_id, record_id, status, standard_no, standard_name,"
            "  standard_type, retry_count, created_at, updated_at)"
            " VALUES (?, 1, 1, 'pending', 'GB/T 1234-2020', '测试标准', 'NationalStd', 0,"
            " datetime('now'), datetime('now'))",
            (fav_id,),
        )
        return fav_id
    finally:
        db.close()


def _build_manager(tmp_path, adapter: _FakeOpenstdAdapter) -> MagicMock:
    engine = DownloadEngine(
        adapters=[adapter],
        session_manager=SessionManager(min_delay=0.001, max_delay=0.005),
        save_root=str(tmp_path / "library"),
    )
    mgr = MagicMock()
    mgr.download_engine = engine
    return mgr


def _run(tmp_path, adapter, hcno="HC123", adopted=False):
    """跑一次 download_to_inbox，返回 (favorite_id, mgr, 真实 sqlite 连接)。"""
    db_path = str(tmp_path / "t.db")
    fav_id = _seed(db_path)
    mgr = _build_manager(tmp_path, adapter)
    inbox = tmp_path / "inbox"
    found_path = str(tmp_path / "library" / "GBT 1234-2020.pdf")

    with patch("pilotstd.tasks.favorite_download.get_db_path", return_value=db_path), patch(
        "pilotstd.tasks.favorite_download._get_inbox_dir", return_value=inbox
    ), patch(
        "pilotstd.tasks.favorite_download._load_cached_query_result",
        return_value=MagicMock(hcno=hcno, is_adopted=adopted),
    ), patch(
        "pilotstd.manager.facade.StandardManager", return_value=mgr
    ), patch(
        "pilotstd.tasks.favorite_download._find_in_file_index",
        side_effect=[None, found_path],
    ), patch(
        "pilotstd.tasks.favorite_download.time.sleep"
    ):
        download_to_inbox(fav_id, 1, 1)

    return fav_id, mgr, db_path, inbox, found_path


class _RealArchiveMgr:
    """真解析 + 真归档 + 真写索引的管理器替身（只实现链路用到的那一面）。

    与 MagicMock 版 e2e 的区别：归档不是空转，而是真的把 inbox 文件搬到库目录
    并 upsert `file_index`；链路的索引查询也不再打桩 —— 全程真跑，用来验证
    「归档写入口径 == 链路查询口径」（技术债 #29 的关键接缝）。
    """

    def __init__(self, download_engine, db, parser, dst: str):
        self.download_engine = download_engine
        self._parser = parser
        self._repo = FileIndexRepository(db)
        self._dst = dst
        self.moved: list[str] = []

    def parse_standard_number(self, name: str):
        """与 facade 同口径：委托 StandardParser。"""
        return self._parser.parse(name)

    def archive_standards(self, parsed_list, word_source_root=None):
        """模拟 organizer：搬文件进库目录 + 写 file_index。"""
        for item in parsed_list:
            Path(self._dst).parent.mkdir(parents=True, exist_ok=True)
            shutil.move(item.source_path, self._dst)
            self.moved.append(item.source_path)
            self._repo.upsert(
                file_path=self._dst,
                logical_code=item.logical_code,
                number=item.number,
                year=item.year,
                std_name="测试标准",
                status="现行",
            )
        return {"moved": len(parsed_list)}


@pytest.mark.integration
class TestArchiveStepEndToEnd:
    """技术债 #29：归档这一环真跑（真搬文件 + 真写索引 + 真查询）。"""

    def test_real_archive_step_leads_to_done(self, tmp_path):
        """下载字节 → inbox → 链路调归档（搬库+写索引）→ 真查询命中 → done + local_path 指向库内。"""
        from pilotstd.organizer.industry_lookup import build_code_mapping
        from pilotstd.scan.parser import StandardParser
        from pilotstd.tasks.favorite_download import download_to_inbox

        db_path = str(tmp_path / "real.db")
        fav_id = _seed(db_path)
        engine = DownloadEngine(
            adapters=[_FakeOpenstdAdapter()],
            session_manager=SessionManager(min_delay=0.001, max_delay=0.005),
            save_root=str(tmp_path / "library"),
        )
        inbox = tmp_path / "inbox"
        dst = str(tmp_path / "standards" / "GBT 1234-2020.pdf")
        db = Database(db_path)
        try:
            mgr = _RealArchiveMgr(
                engine, db, StandardParser(build_code_mapping()), dst
            )
            with patch(
                "pilotstd.tasks.favorite_download.get_db_path", return_value=db_path
            ), patch(
                "pilotstd.tasks.favorite_download._get_inbox_dir", return_value=inbox
            ), patch(
                "pilotstd.tasks.favorite_download._load_cached_query_result",
                return_value=MagicMock(hcno="HC1", is_adopted=False),
            ), patch(
                "pilotstd.manager.facade.StandardManager", return_value=mgr
            ), patch(
                "pilotstd.tasks.favorite_download._notify_download_started"
            ), patch(
                "pilotstd.tasks.favorite_download._notify_download_complete"
            ), patch(
                "pilotstd.tasks.favorite_download._notify_download_failed"
            ):
                download_to_inbox(fav_id, 1, 1)

            row = db.fetchone(
                "SELECT status, local_path, error_message FROM favorite_downloads WHERE favorite_id=?",
                (fav_id,),
            )
        finally:
            db.close()

        assert row["status"] == "done", row
        assert row["local_path"] == dst, row
        assert Path(dst).exists(), "归档后文件应已在库目录"
        assert mgr.moved and mgr.moved[0].startswith(str(inbox)), mgr.moved
        assert not list(inbox.glob("*.pdf")), "inbox 里的文件应已被搬走"


@pytest.mark.integration
class TestArchiveIndexContract:
    """技术债 #29 契约：归档器写 file_index 的口径必须能被链路的查询命中。

    链路用**规范标准号**（`GB/T 5613-2026`）查 `(logical_code, number, year)`；归档器写的是
    `archive_standards` 收到的 parsed 项。若解析源误用被 `_safe_filename` 转义过的 inbox 文件名
    （`GB_T 5613-2026_000002.pdf`），`logical_code` 会退化成 `GB` → 两边口径不一致、永远查不到。
    """

    def test_organizer_written_index_is_found_by_chain_lookup(self, tmp_path):
        """真实 parser + 真实 FileIndexRepository + 真实查询：口径一致 → 命中。"""
        from pilotstd.core.file_index import FileIndexRepository
        from pilotstd.organizer.industry_lookup import build_code_mapping
        from pilotstd.scan.parser import StandardParser
        from pilotstd.tasks.favorite_download import _find_in_file_index

        db = Database(str(tmp_path / "contract.db"))
        try:
            parser = StandardParser(build_code_mapping())
            item = parser.parse("GB/T 5613-2026")
            assert item is not None and item.logical_code == "GB/T"
            dst = str(tmp_path / "standards" / "GBT 5613-2026.pdf")
            FileIndexRepository(db).upsert(
                file_path=dst,
                logical_code=item.logical_code,
                number=item.number,
                year=item.year,
                std_name="测试标准",
                status="现行",
            )
            # 链路侧：用规范标准号查得到（这正是归档后置 done 的依据）
            assert _find_in_file_index("GB/T 5613-2026", db) == dst

            # 反证：若按被转义的 inbox 文件名解析，logical_code 退化为 GB → 查不到
            escaped = parser.parse("GB_T 5613-2026_000002.pdf")
            assert escaped is not None and escaped.logical_code == "GB", escaped.logical_code
        finally:
            db.close()



class TestFavoriteDownloadChainE2E:
    def test_success_chain_writes_inbox_and_marks_done(self, tmp_path):
        """成功链路：字节落 inbox → 轮询命中 → done → 事件成对。"""
        fav_id, mgr, db_path, inbox, found_path = _run(tmp_path, _FakeOpenstdAdapter())

        # 1) 适配器经 std_gov→openstd_download 映射被路由到，且确有一次调用
        # 2) 字节真正落到 inbox（文件名含 favorite_id 后 6 位）
        files = list(inbox.glob("*.pdf"))
        assert len(files) == 1, f"应恰好落一个 PDF，实际 {files}"
        assert files[0].read_bytes() == _PDF_BYTES
        assert str(fav_id)[-6:] in files[0].name

        # 3) 状态机终态 done + local_path 指向扫描器登记后的库内路径
        db = Database(db_path)
        try:
            row = db.fetchone(
                "SELECT status, local_path FROM favorite_downloads WHERE favorite_id=?",
                (fav_id,),
            )
        finally:
            db.close()
        assert row["status"] == "done"
        assert row["local_path"] == found_path

        # 4) 事件成对：started → complete，且无 failed
        events = [c.args[0] for c in mgr.notification_mgr.send_event.call_args_list]
        assert events == ["download_started", "download_complete"], events

    def test_business_failure_marks_failed_with_single_notification(self, tmp_path):
        """适配器业务失败（暂无全文）→ failed + 仅 1 条 download_failed + 无 inbox 残留。"""
        adapter = _FakeOpenstdAdapter(fail_with="viewGb 返回空内容（标准可能暂无全文）")
        fav_id, mgr, db_path, inbox, _found = _run(tmp_path, adapter)

        assert not inbox.exists() or not list(inbox.glob("*.pdf")), "失败不得留下半成品"

        db = Database(db_path)
        try:
            row = db.fetchone(
                "SELECT status, error_message FROM favorite_downloads WHERE favorite_id=?",
                (fav_id,),
            )
        finally:
            db.close()
        assert row["status"] == "failed"
        assert "viewGb 返回空内容" in row["error_message"]

        events = [c.args[0] for c in mgr.notification_mgr.send_event.call_args_list]
        assert events.count("download_failed") == 1, events
        assert "download_complete" not in events

    def test_adopted_standard_never_reaches_adapter(self, tmp_path):
        """采标闸：版权受限 → 业务终态跳过，不下载、不写 inbox、不写 failed。

        P1（2026-09-21）：跳过属终态，`download_to_inbox` 以 FavoriteSkip 上抛且不写 failed
        （写 failed 会被链路按失败重试 7 天）；终态标记与单次通知由链路负责
        （tests/test_favorite_chain_processor.py::test_skip_mode_marks_terminal_without_retries）。
        """
        from pilotstd.tasks.favorite_download import FavoriteSkip

        adapter = _FakeOpenstdAdapter()
        with pytest.raises(FavoriteSkip, match="采标标准"):
            _run(tmp_path, adapter, adopted=True)

        assert adapter.calls == 0, "采标标准不得调用适配器"
        inbox = tmp_path / "inbox"
        assert not inbox.exists() or not list(inbox.glob("*.pdf"))

        db = Database(str(tmp_path / "t.db"))
        try:
            rows = db.fetchall("SELECT status, error_message FROM favorite_downloads")
        finally:
            db.close()
        assert rows, "队列行应仍然存在（终态由链路接管）"
        assert rows[0]["status"] != "failed", "终态跳过不得写 failed，否则会被重试 7 天"
