# tests/test_docker_api.py
"""docker/api/*.py API 端点测试"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import unittest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from docker.auth import require_admin
from docker.manager import get_manager_dep


class TestAPIEndpoints(unittest.TestCase):
    client: TestClient

    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        from docker.api.announce import router as announce_router
        from docker.api.archive import router as archive_router
        from docker.api.download import router as download_router
        from docker.api.logs import router as logs_router
        from docker.api.normalize import router as normalize_router
        from docker.api.organize import router as organize_router
        from docker.api.pending import router as pending_router
        from docker.api.query import router as query_router
        from docker.api.scan import router as scan_router
        from docker.api.settings import router as settings_router
        from docker.api.stats import router as stats_router
        from docker.api.system import router as system_router
        from docker.api.upload import router as upload_router
        from docker.api.users import router as users_router

        app.include_router(stats_router)
        app.include_router(scan_router)
        app.include_router(organize_router)
        app.include_router(pending_router)
        app.include_router(announce_router)
        app.include_router(settings_router)
        app.include_router(system_router)
        app.include_router(normalize_router)
        app.include_router(archive_router)
        app.include_router(upload_router)
        app.include_router(logs_router)
        app.include_router(query_router)
        app.include_router(download_router)
        app.include_router(users_router)
        cls.client = TestClient(app)

    def setUp(self):
        """每个测试前注入 require_admin 覆盖，避免 401。"""
        self.client.app.dependency_overrides[require_admin] = lambda: "admin"

    def tearDown(self):
        """清除 dependency_overrides，防止测试间污染。"""
        self.client.app.dependency_overrides.clear()

    # ── Stats ──

    def test_stats_returns_zero_counts_when_empty(self):
        mock_mgr = MagicMock()
        mock_mgr.file_index.get_status_stats.return_value = {
            "current": 0,
            "expired": 0,
            "pending": 0,
            "upcoming": 0,
        }
        self.client.app.dependency_overrides[get_manager_dep] = lambda: mock_mgr
        r = self.client.get("/api/stats")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["current"], 0)
        self.assertEqual(data["expired"], 0)
        self.assertEqual(data["pending"], 0)

    # ── Scan ──

    @patch("docker.api.scan._validate_path")
    def test_scan_returns_file_list(self, mock_validate):
        """POST /api/scan 返回扫描到的文件列表及统计。"""
        mock_validate.return_value = "/inbox"
        mock_mgr = MagicMock()
        from pilotstd.models import ParsedStdInfo

        mock_parsed = ParsedStdInfo(
            raw_filename="GB_T_1-2020.pdf",
            logical_code="GB/T",
            number=1,
            year=2020,
            std_name="测试",
        )
        mock_parsed.source_path = "/inbox/GB_T_1-2020.pdf"
        mock_mgr.scan_directory.return_value = [mock_parsed]
        mock_mgr._last_skipped_dirs = []
        self.client.app.dependency_overrides[get_manager_dep] = lambda: mock_mgr
        r = self.client.post("/api/scan", params={"path": "/inbox"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["pdf_count"], 1)
        self.assertEqual(data["files"][0]["name"], "GB_T_1-2020.pdf")

    @patch("docker.api.scan._validate_path")
    def test_scan_invalid_path_returns_400(self, mock_validate):
        """扫描路径不在允许范围时返回 400。"""
        mock_validate.side_effect = ValueError("路径不在允许的目录范围内")
        r = self.client.post("/api/scan", params={"path": "/etc"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("error", r.json())

    # ── Organize ──

    @patch("docker.api.organize._validate_path")
    @patch("docker.api.organize.os.path.exists", return_value=True)
    @patch("docker.api.organize.os.scandir")
    def test_files_lists_directory(self, mock_scandir, mock_exists, mock_validate):
        mock_validate.return_value = "/standards"
        mock_entry = MagicMock()
        mock_entry.name = "test.pdf"
        mock_entry.is_dir.return_value = False
        mock_entry.stat.return_value.st_size = 1024
        mock_scandir.return_value = [mock_entry]

        r = self.client.get("/api/files?path=/standards")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(len(data["files"]), 1)
        self.assertEqual(data["files"][0]["name"], "test.pdf")

    @patch("docker.api.organize._validate_path")
    @patch("docker.api.organize.os.path.exists", return_value=False)
    def test_files_nonexistent_path_returns_404(self, mock_exists, mock_validate):
        """路径不存在时返回 404。路径校验通过，但文件系统找不到。"""
        mock_validate.return_value = "/nonexistent"
        r = self.client.get("/api/files?path=/nonexistent")
        self.assertEqual(r.status_code, 404)

    @patch("docker.api.organize._validate_path")
    @patch("docker.api.organize.os.walk")
    @patch("docker.api.organize.os.listdir")
    @patch("docker.api.organize.os.rmdir")
    def test_clean_empty_removes_dirs(self, mock_rmdir, mock_listdir, mock_walk, mock_validate):
        mock_validate.return_value = "/standards"
        mock_walk.return_value = [("/standards/empty", ["sub"], [])]
        mock_listdir.return_value = []
        r = self.client.post("/api/clean-empty", params={"path": "/standards"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["cleaned"], 1)

    # ── Settings ──

    @patch("docker.api.settings.update_job")
    def test_get_settings_returns_all_sections(self, mock_update):
        mock_mgr = MagicMock()
        mock_mgr.cfg.get.return_value = []
        self.client.app.dependency_overrides[get_manager_dep] = lambda: mock_mgr
        r = self.client.get("/api/settings")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        for section in ["storage", "scan", "query", "tasks", "appearance"]:
            self.assertIn(section, data, f"Missing section: {section}")

    @patch("docker.api.settings.update_job")
    def test_put_settings_calls_update_job(self, mock_update):
        mock_mgr = MagicMock()
        mock_mgr.cfg.get.return_value = False
        self.client.app.dependency_overrides[get_manager_dep] = lambda: mock_mgr
        # put_settings 需要 admin 权限，通过 dependency override 绕过
        from docker.auth import require_admin

        self.client.app.dependency_overrides[require_admin] = lambda: "admin"
        data = {
            "tasks": {
                "auto_scan_enabled": True,
                "auto_scan_cron": "0 4 * * *",
            }
        }
        r = self.client.put("/api/settings", json=data)
        self.assertEqual(r.status_code, 200)
        # put_settings 对所有 3 个 job 都调用 update_job；此处验证关键调用存在
        mock_update.assert_any_call("auto_scan", "0 4 * * *", True)

    # ── Pending ──

    def test_requery_pending_returns_results(self):
        mock_result = MagicMock()
        mock_result.standard_number = "GB/T 1-2020"
        mock_result.standard_name = "测试"
        mock_result.status = "现行"
        mock_result.source_site = "test"
        mock_stats = MagicMock()
        mock_mgr = MagicMock()
        mock_mgr.query_by_numbers.return_value = ([mock_result], mock_stats)
        self.client.app.dependency_overrides[get_manager_dep] = lambda: mock_mgr

        # numbers: list[str] 是 body 参数，FastAPI 期望 JSON 数组而非对象
        r = self.client.post("/api/pending/requery", json=["GB/T 1-2020"])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["results"]), 1)
        self.assertEqual(r.json()["results"][0]["standard_number"], "GB/T 1-2020")

    def test_get_pending_returns_items(self):
        """GET /api/pending 返回待确认标准列表。"""
        mock_mgr = MagicMock()
        mock_mgr.get_pending_items.return_value = [
            {
                "standard_number": "GB/T 1-2020",
                "status": "待确认",
                "source_site": "njbz365",
            }
        ]
        self.client.app.dependency_overrides[get_manager_dep] = lambda: mock_mgr
        r = self.client.get("/api/pending")
        self.assertEqual(r.status_code, 200)
        items = r.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["standard_number"], "GB/T 1-2020")

    # ── Announce ──

    def test_check_announce_returns_count(self):
        mock_mgr = MagicMock()
        mock_mgr.check_announcements_filtered.return_value = {
            "gb": {"matched": 2, "updated": 1, "total_announcements": 3},
            "hb": {"matched": 0, "updated": 0, "total_announcements": 0},
            "db": {"matched": 0, "updated": 0, "total_announcements": 0},
        }
        mock_mgr.db.fetchall.return_value = []
        self.client.app.dependency_overrides[get_manager_dep] = lambda: mock_mgr
        r = self.client.post("/api/announce/check")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])
        # 公告抓取已改为后台异步执行，返回 msg 而非 count
        self.assertIn("msg", r.json())

    def test_announce_results_initially_empty(self):
        r = self.client.get("/api/announce/results")
        self.assertEqual(r.status_code, 200)

    # ── Normalize ──

    def test_normalize_returns_results(self):
        """POST /api/normalize 返回规范化后的文件名列表。"""
        mock_mgr = MagicMock()
        mock_mgr.normalize_files_stream.return_value = [
            {"source": "/inbox/test.pdf", "normalized": "GB_T_1-2020.pdf"},
        ]
        self.client.app.dependency_overrides[get_manager_dep] = lambda: mock_mgr
        r = self.client.post(
            "/api/normalize",
            json={"items": [{"source_path": "/inbox/test.pdf", "logical_code": "GB/T 1-2020"}], "run_id": "test-run"},
        )
        self.assertEqual(r.status_code, 200)
        results = r.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source_path"], "/inbox/test.pdf")
        self.assertEqual(results[0]["new_filename"], "GB_T_1-2020.pdf")

    def test_normalize_accepts_list_body(self):
        """POST /api/normalize 必须包含 items 和 run_id（Body embed 模式）。"""
        mock_mgr = MagicMock()
        mock_mgr.normalize_files_stream.return_value = []
        self.client.app.dependency_overrides[get_manager_dep] = lambda: mock_mgr
        # Body(embed=True) 要求 {"items": [...], "run_id": "..."}
        r = self.client.post("/api/normalize", json={"items": [], "run_id": "test-run"})
        self.assertEqual(r.status_code, 200)
        # 缺 run_id 返回 422
        r2 = self.client.post("/api/normalize", json={"items": []})
        self.assertEqual(r2.status_code, 422)

    # ── Archive ──

    def test_archive_calls_organize(self):
        """POST /api/archive 将文件移动到分类目录。"""
        mock_mgr = MagicMock()
        mock_mgr.archive_standards.return_value = {"moved": 1, "errors": []}
        self.client.app.dependency_overrides[get_manager_dep] = lambda: mock_mgr
        r = self.client.post(
            "/api/archive",
            json={
                "items": [
                    {
                        "source_path": "/inbox/GB_T_1-2020.pdf",
                        "logical_code": "GB/T 1-2020",
                        "number": 1,
                        "year": 2020,
                        "std_name": "测试标准",
                        "num_prefix": "GB/T",
                        "num_suffix": "",
                        "language": "zh",
                        "ext": "pdf",
                    }
                ],
                "word_source_root": "/word",
                "run_id": "test-run",
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["moved"], 1)
        # 验证 archive_standards 被调用且 word_source_root 正确传递
        mock_mgr.archive_standards.assert_called_once()
        args, kwargs = mock_mgr.archive_standards.call_args
        self.assertEqual(kwargs["word_source_root"], "/word")
        parsed_list = args[0]
        self.assertEqual(len(parsed_list), 1)
        self.assertEqual(parsed_list[0].logical_code, "GB/T 1-2020")

    # ── Query ──

    def test_query_standards_returns_results(self):
        """POST /api/query 返回查询结果及统计。"""
        from pilotstd.query.models import QueryResult

        mock_result = QueryResult(
            standard_number="GB/T 1-2020",
            standard_name="测试标准",
            status="现行",
            source_site="njbz365",
            match_status="exact",
        )
        mock_stats = MagicMock()
        mock_stats.total = 1
        mock_stats.found = 1
        mock_stats.downloadable = 1
        mock_stats.not_found = 0
        mock_mgr = MagicMock()
        mock_mgr.query_by_numbers.return_value = ([mock_result], mock_stats)
        self.client.app.dependency_overrides[get_manager_dep] = lambda: mock_mgr
        r = self.client.post("/api/query", json={"numbers": ["GB/T 1-2020"], "run_id": "test-run"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["stats"]["total"], 1)
        self.assertEqual(data["stats"]["found"], 1)
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["standard_number"], "GB/T 1-2020")

    @patch("builtins.open")
    def test_query_save_persists_results(self, mock_open):
        """POST /api/query/save 保存查询结果到文件。"""
        r = self.client.post(
            "/api/query/save",
            json=[{"standard_number": "GB/T 1-2020", "standard_name": "测试"}],
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])
        self.assertEqual(r.json()["count"], 1)

    @patch("docker.api.query.os.path.exists")
    def test_query_results_initially_empty(self, mock_exists):
        """查询结果文件不存在时返回空列表。"""
        mock_exists.return_value = False
        r = self.client.get("/api/query/results")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["results"], [])

    # ── Download ──

    def test_download_standards_returns_results(self):
        """POST /api/download 返回下载任务状态。"""
        mock_task = MagicMock()
        mock_task.standard_number = "GB/T 1-2020"
        mock_task.status = MagicMock(value="success")
        mock_task.saved_path = "/standards/GB/GB_T_1-2020.pdf"
        mock_task.error_message = ""
        mock_task.query_result = None
        mock_stats = MagicMock()
        mock_stats.total = 1
        mock_stats.success = 1
        mock_stats.failed = 0
        mock_stats.skipped_adopted = 0
        mock_mgr = MagicMock()
        mock_mgr.download_by_numbers.return_value = ([mock_task], mock_stats)
        self.client.app.dependency_overrides[get_manager_dep] = lambda: mock_mgr
        r = self.client.post("/api/download", json={"numbers": ["GB/T 1-2020"], "run_id": "test-run"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["stats"]["total"], 1)
        self.assertEqual(data["stats"]["success"], 1)
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["status"], "success")
        self.assertEqual(data["results"][0]["saved_path"], "/standards/GB/GB_T_1-2020.pdf")

    # ── Upload ──

    @patch("builtins.open")
    @patch("uuid.uuid4")
    def test_upload_valid_image_returns_url(self, mock_uuid, mock_open):
        """上传合法 JPEG 图片返回访问 URL。"""
        mock_uuid.return_value.hex = "abc123def456"
        # 最小合法 JPEG（SOI + JFIF 头）
        jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        r = self.client.post("/api/upload", files={"file": ("test.jpg", jpeg_bytes, "image/jpeg")})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("url", data)
        self.assertIn("abc123def456.jpg", data["url"])

    def test_upload_invalid_extension_returns_400(self):
        """上传不支持扩展名返回 400。"""
        r = self.client.post(
            "/api/upload",
            files={"file": ("test.exe", b"data", "application/octet-stream")},
        )
        self.assertEqual(r.status_code, 400)

    def test_upload_wrong_magic_returns_400(self):
        """扩展名 .jpg 但内容是 PNG 魔数：返回 400。"""
        # PNG 文件头魔数
        png_header = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        r = self.client.post("/api/upload", files={"file": ("fake.jpg", png_header, "image/jpeg")})
        self.assertEqual(r.status_code, 400)

    def test_backgrounds_not_found_returns_404(self):
        """请求不存在的背景图返回 404。——上传测试没真实写盘，文件自然不存在。"""
        r = self.client.get("/api/backgrounds/nonexistent_file_xyz.png")
        self.assertEqual(r.status_code, 404)

    # ── Logs ──

    @patch("builtins.open")
    @patch("docker.api.logs.os.path.exists")
    def test_logs_returns_lines(self, mock_exists, mock_open):
        """GET /api/logs 返回最近 N 行日志。"""
        mock_exists.return_value = True
        mock_open.return_value.__enter__.return_value.readlines.return_value = [
            "line 1\n",
            "line 2\n",
            "line 3\n",
        ]
        r = self.client.get("/api/logs?tail=10")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(len(data["lines"]), 3)
        self.assertEqual(data["total"], 3)

    @patch("docker.api.logs.os.path.exists")
    def test_logs_file_not_exist_returns_note(self, mock_exists):
        """日志文件尚未生成时返回提示信息。"""
        mock_exists.return_value = False
        r = self.client.get("/api/logs")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["lines"], [])
        self.assertIn("尚未生成", data.get("note", ""))

    # ── Users ──

    @patch("docker.api.users.list_users")
    def test_list_users_returns_list(self, mock_list):
        """GET /api/users 返回用户列表。"""
        mock_list.return_value = [{"id": 1, "username": "admin", "role": "admin"}]
        r = self.client.get("/api/users")
        self.assertEqual(r.status_code, 200)
        users = r.json()["users"]
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0]["username"], "admin")

    @patch("docker.api.users.add_user")
    def test_add_user_returns_ok(self, mock_add):
        """POST /api/users 添加用户成功返回 ok。"""
        mock_add.return_value = True
        r = self.client.post(
            "/api/users",
            json={"username": "newuser", "password": "pass1234", "role": "user"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])

    @patch("docker.api.users.add_user")
    def test_add_user_empty_username_returns_400(self, mock_add):
        """空用户名返回 400。"""
        r = self.client.post("/api/users", json={"username": "", "password": "pass1234"})
        self.assertEqual(r.status_code, 400)

    @patch("docker.api.users.add_user")
    def test_add_user_duplicate_returns_409(self, mock_add):
        """用户名已存在返回 409。"""
        mock_add.return_value = False
        r = self.client.post(
            "/api/users",
            json={"username": "admin", "password": "pass1234", "role": "admin"},
        )
        self.assertEqual(r.status_code, 409)

    @patch("docker.api.users.delete_user")
    def test_delete_user_returns_ok(self, mock_delete):
        """DELETE /api/users/{id} 删除成功返回 ok。"""
        mock_delete.return_value = True
        mock_mgr = MagicMock()
        mock_mgr.user_service.get_user_by_id.return_value = {"id": 2, "username": "testuser", "role": "user"}
        self.client.app.dependency_overrides[get_manager_dep] = lambda: mock_mgr
        r = self.client.delete("/api/users/2")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])

    @patch("docker.api.users.delete_user")
    def test_delete_user_not_found_returns_400(self, mock_delete):
        """删除不存在的用户返回 400。"""
        mock_delete.return_value = False
        mock_mgr = MagicMock()
        mock_mgr.user_service.get_user_by_id.return_value = {"id": 99, "username": "testuser", "role": "user"}
        self.client.app.dependency_overrides[get_manager_dep] = lambda: mock_mgr
        r = self.client.delete("/api/users/99")
        self.assertEqual(r.status_code, 400)

    @patch("docker.api.users.get_current_username")
    @patch("docker.api.users.change_password")
    def test_change_password_returns_ok(self, mock_change, mock_user):
        """PUT /api/users/password 修改密码成功返回 ok。"""
        mock_user.return_value = "admin"
        mock_change.return_value = True
        r = self.client.put(
            "/api/users/password",
            json={"old_password": "old", "new_password": "newpass"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])

    @patch("docker.api.users.get_current_username")
    def test_change_password_short_returns_400(self, mock_user):
        """新密码不足 4 个字符返回 400。"""
        mock_user.return_value = "admin"
        r = self.client.put("/api/users/password", json={"old_password": "old", "new_password": "ab"})
        self.assertEqual(r.status_code, 400)

    # ── System: version ──

    def test_system_version_returns_ok(self):
        r = self.client.get("/api/system/version")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("version", data)
        self.assertIn("image", data)

    # ── System: update ──

    @patch("docker.api.system.os.path.exists", return_value=False)
    @patch("docker.api.system.os.environ.get", return_value="")
    @patch("docker.api.system._get_container_id", return_value="")
    def test_update_no_container_id_returns_500(self, mock_cid, mock_env, mock_exists):
        """无法获取容器 ID 时返回 500。"""
        r = self.client.post("/api/system/update")
        self.assertEqual(r.status_code, 500)

    @patch("docker.api.system._get_container_id", return_value="abc123")
    @patch("docker.api.system._run_docker")
    def test_update_same_digest_returns_not_updated(self, mock_run, mock_cid):
        """新旧 digest 相同时返回 updated=False。"""
        inspect_out = json.dumps([{"Image": "sha256:old"}])
        digest_out = "ghcr.io/leanmore/pilotstd@sha256:abc123"
        mock_run.side_effect = [
            MagicMock(stdout=inspect_out),  # inspect cid
            MagicMock(stdout=digest_out),  # image inspect old
            MagicMock(stdout="Downloaded newer"),  # pull
            MagicMock(stdout=digest_out),  # image inspect new
        ]
        r = self.client.post("/api/system/update")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()["updated"])

    @patch("docker.api.system.os.path.exists", return_value=False)
    @patch("docker.api.system.os.environ.get", return_value="")
    @patch("docker.api.system._get_container_id", return_value="abc123")
    @patch("docker.api.system._run_docker")
    def test_update_no_compose_returns_restarted_false(self, mock_run, mock_cid, mock_env, mock_exists):
        """无 compose 配置时，拉取成功但 restart 为 false。"""
        old_digest = "ghcr.io/leanmore/pilotstd@sha256:aaa"
        new_digest = "ghcr.io/leanmore/pilotstd@sha256:bbb"
        mock_run.side_effect = [
            MagicMock(stdout=json.dumps([{"Image": "sha256:old"}])),
            MagicMock(stdout=old_digest),
            MagicMock(stdout="Downloaded newer"),
            MagicMock(stdout=new_digest),
        ]
        r = self.client.post("/api/system/update")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["updated"])
        self.assertFalse(data["restarted"])
        self.assertIn("compose", data["message"].lower())

    @patch("docker.api.system.os.path.exists", return_value=True)
    @patch("docker.api.system.os.environ.get")
    @patch("docker.api.system._get_container_id", return_value="abc123")
    @patch("docker.api.system._run_docker")
    def test_update_with_compose_succeeds(self, mock_run, mock_cid, mock_env, mock_exists):
        """有 compose 配置时，compose up 成功后 restarted=True。"""
        mock_env.side_effect = lambda k, d="": {
            "COMPOSE_FILE": "/app/docker-compose.yml",
            "COMPOSE_PROJECT_NAME": "pilotstd",
        }.get(k, d)
        old_digest = "ghcr.io/leanmore/pilotstd@sha256:aaa"
        new_digest = "ghcr.io/leanmore/pilotstd@sha256:bbb"
        mock_run.side_effect = [
            MagicMock(stdout=json.dumps([{"Image": "sha256:old"}])),
            MagicMock(stdout=old_digest),
            MagicMock(stdout="Downloaded newer"),
            MagicMock(stdout=new_digest),
            MagicMock(stdout=""),  # compose up 成功
        ]
        r = self.client.post("/api/system/update")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["updated"])
        self.assertTrue(data["restarted"])
        self.assertEqual(data["method"], "compose")

    @patch("docker.api.system.os.path.exists", return_value=True)
    @patch("docker.api.system.os.environ.get")
    @patch("docker.api.system._get_container_id", return_value="abc123")
    @patch("docker.api.system._run_docker")
    def test_update_compose_fails_returns_restarted_false(self, mock_run, mock_cid, mock_env, mock_exists):
        """compose up 抛异常时 restarted=False。"""
        mock_env.side_effect = lambda k, d="": {
            "COMPOSE_FILE": "/app/docker-compose.yml",
            "COMPOSE_PROJECT_NAME": "pilotstd",
        }.get(k, d)
        old_digest = "ghcr.io/leanmore/pilotstd@sha256:aaa"
        new_digest = "ghcr.io/leanmore/pilotstd@sha256:bbb"
        mock_run.side_effect = [
            MagicMock(stdout=json.dumps([{"Image": "sha256:old"}])),
            MagicMock(stdout=old_digest),
            MagicMock(stdout="Downloaded newer"),
            MagicMock(stdout=new_digest),
            Exception("compose 网络错误"),  # compose up 失败
        ]
        r = self.client.post("/api/system/update")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["updated"])
        self.assertFalse(data["restarted"])

    @patch("docker.api.system._get_container_id", return_value="abc123")
    @patch("docker.api.system._run_docker")
    def test_update_docker_sock_not_found_returns_503(self, mock_run, mock_cid):
        """docker.sock 未挂载时返回 503。"""
        mock_run.side_effect = RuntimeError("docker.sock 未挂载")
        r = self.client.post("/api/system/update")
        self.assertEqual(r.status_code, 503)

    @patch("docker.api.system._get_container_id", return_value="abc123")
    @patch("docker.api.system._run_docker")
    def test_update_pull_timeout_returns_504(self, mock_run, mock_cid):
        """pull 超时返回 504（_run_docker 抛 TimeoutExpired 时 subprocess 模块抛出）。"""
        import subprocess

        # inspect 成功但 pull 超时
        mock_run.side_effect = [
            MagicMock(stdout=json.dumps([{"Image": "sha256:old"}])),
            MagicMock(stdout=""),
            subprocess.TimeoutExpired(cmd="docker pull", timeout=300),
        ]
        r = self.client.post("/api/system/update")
        self.assertEqual(r.status_code, 504)

    @patch("docker.api.system.os.path.exists", return_value=False)
    @patch("docker.api.system.os.environ.get", return_value="")
    @patch("docker.api.system._get_container_id", return_value="abc123")
    @patch("docker.api.system._run_docker")
    def test_update_old_digest_empty_still_triggers_update(self, mock_run, mock_cid, mock_env, mock_exists):
        """旧 digest 获取失败时（image inspect 抛异常），仍应触发更新流程。"""
        new_digest = "ghcr.io/leanmore/pilotstd@sha256:bbb"
        mock_run.side_effect = [
            MagicMock(stdout=json.dumps([{"Image": "sha256:old"}])),
            Exception("image inspect 失败"),  # old_digest 获取失败
            MagicMock(stdout="Pulled"),
            MagicMock(stdout=new_digest),
        ]
        r = self.client.post("/api/system/update")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["updated"])

    # ── Path Guard ──

    def test_get_allowed_roots_includes_inbox_and_standards(self):
        """回归门禁：get_allowed_roots 必须包含 inbox 和 standards（Docker 挂载点）。"""
        from pilotstd.core.path_guard import get_allowed_roots

        roots = get_allowed_roots("/standards")
        # 用 basename 做跨平台比较，避免 Windows 反斜杠 vs Linux 正斜杠差异
        basenames = [r.replace("\\", "/").rstrip("/").split("/")[-1] for r in roots]
        self.assertIn("inbox", basenames, f"/inbox 不在允许的目录范围内: {roots}")
        self.assertIn("standards", basenames, f"/standards 不在允许的目录范围内: {roots}")
