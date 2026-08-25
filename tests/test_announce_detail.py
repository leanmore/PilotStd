# tests/test_announce_detail.py — 公告详情页 API 测试
# P0 修复：真实 Database（迁移链生成 Schema）+ 消除 Mock

import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

import pytest

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)


@pytest.fixture(scope="module", autouse=True)
def _isolate_env_announce_detail():
    """模块级 env 隔离：强制注入 SUPERUSER=testadmin，teardown 恢复原值。

    TD-10 P1：替代守卫式 os.environ["SUPERUSER"] 注入（原模式永不恢复，
    会污染后导入的 test_docker_auth 等模块导致登录 401）。
    """
    old_values = {}
    env_vars = {"SUPERUSER": "testadmin"}
    for k, v in env_vars.items():
        old_values[k] = os.environ.get(k)
        os.environ[k] = v
    yield
    for k, old in old_values.items():
        if old is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = old


class TestAnnounceDetailAPI(unittest.TestCase):
    """验证 /api/announcements/{announce_no} 从 announcement_record 表查询。

    使用真实 Database 对象（由迁移链自动生成 Schema，与生产一致）。
    Handler 执行真实 SQL 语句——若引用不存在的列，测试将直接失败。
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.db")

        from pilotstd.core.db import Database

        # 真实 Database：迁移链自动生成 announcement_record 表结构
        # Schema = v15 → v22 → v29 → v36，与生产完全一致
        self.db = Database(self.db_path)

        # 插入测试数据（仅包含迁移链中确实存在的列）
        self.db.execute(
            "INSERT INTO announcement_record"
            " (source_site, pid, announce_no, standard_number, std_name,"
            "  publish_date, fetched_at, announcement_title)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "ahbz",
                "pid-001",
                "ANNOUNCE-2026-001",
                "GB/T 19001-2016",
                "质量管理体系",
                "2026-06-01",
                "2026-06-15",
                "2026年第1号公告",
            ),
        )

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_mgr(self):
        """构造 manager，使用真实 Database（Handler 将真正执行 SQL）。"""
        mgr = MagicMock()
        mgr.db = self.db
        return mgr

    def test_detail_returns_header_from_record(self):
        """详情页应从 announcement_record 返回公告头信息。"""
        from docker.api.announce_detail import get_announcement_detail

        mgr = self._make_mgr()
        result = get_announcement_detail("ANNOUNCE-2026-001", mgr=mgr)
        self.assertIsNotNone(result)
        self.assertIn("announcement", result)
        self.assertEqual(result["announcement"]["announce_no"], "ANNOUNCE-2026-001")

    def test_detail_unknown_raises_404(self):
        """不存在的公告号应返回 404。"""
        from fastapi import HTTPException

        from docker.api.announce_detail import get_announcement_detail

        mgr = self._make_mgr()

        with self.assertRaises(HTTPException) as ctx:
            get_announcement_detail("NONEXISTENT", mgr=mgr)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_detail_returns_records_array(self):
        """详情页应返回关联的标准记录列表。"""
        from docker.api.announce_detail import get_announcement_detail

        mgr = self._make_mgr()
        result = get_announcement_detail("ANNOUNCE-2026-001", mgr=mgr)
        self.assertIn("records", result)
        self.assertIsInstance(result["records"], list)
        self.assertIn("parse_status", result)

    def test_cleaner_enforces_semantic_output(self):
        """防绕过：清洗函数输出语义 class，不含废弃标签。

        若有人移除 import 或绕过 clean_announcement_content 直接写入原始 HTML，
        此测试将因 import 失败而中断。
        注意：clean_announcement_content 的输入契约是纯文本，需先 strip 已有标签。
        """
        from docker.api.announce_detail import clean_announcement_content

        # 模拟 extract_content 之后的纯文本输入
        plain_text = "国家市场监督管理总局 2026-07-29"
        result = clean_announcement_content(plain_text)
        self.assertNotIn("style=", result)
        self.assertNotIn("<font", result)
        self.assertIn('class="announce-signature"', result)
        self.assertIn("2026-07-29", result)

    def test_cleaner_idempotent_on_empty(self):
        """空字符串经清洗后仍为空，确保 INSERT 路径行为不变。"""
        from docker.api.announce_detail import clean_announcement_content

        self.assertEqual(clean_announcement_content(""), "")
        self.assertEqual(clean_announcement_content("  "), "")


if __name__ == "__main__":
    unittest.main()
