# tests/test_updater.py
# 测试 platform/updater — 版本比较、SHA256 提取、更新脚本生成
# 网络相关函数（check_latest_version, download_update）使用 mock

import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from pilotstd.platform.updater import (
    check_latest_version,
    download_update,
    extract_sha256_from_body,
    generate_update_script,
    is_newer_version,
    verify_checksum,
)


class TestIsNewerVersion(unittest.TestCase):
    """语义化版本比较测试。"""

    def test_latest_greater_than_current(self) -> None:
        """latest > current 返回 True。"""
        assert is_newer_version("v0.55.0", "0.54.1") is True

    def test_latest_equal_current(self) -> None:
        """版本相同时返回 False。"""
        assert is_newer_version("v0.55.0", "0.55.0") is False

    def test_latest_less_than_current(self) -> None:
        """latest < current 返回 False。"""
        assert is_newer_version("v0.53.0", "0.54.1") is False

    def test_no_v_prefix_handled(self) -> None:
        """不含 v 前缀也能正常比较。"""
        assert is_newer_version("1.0.0", "0.9.9") is True

    def test_partial_version_treated_as_zero(self) -> None:
        """只含一个段号时缺失段按 0 处理。"""
        assert is_newer_version("2", "1.9.9") is True


class TestExtractSha256FromBody(unittest.TestCase):
    """Release body 中提取 SHA256 测试。"""

    def test_extract_valid_sha256_line(self) -> None:
        body = "更新内容\nSHA256: abc123def456\n备注"
        result = extract_sha256_from_body(body)
        assert result == "abc123def456"

    def test_extract_when_no_sha256_line(self) -> None:
        body = "更新内容\n无校验和"
        result = extract_sha256_from_body(body)
        assert result == ""

    def test_extract_case_insensitive(self) -> None:
        body = "sha256: ABCDEF"
        result = extract_sha256_from_body(body)
        assert result == "ABCDEF"


class TestVerifyChecksum(unittest.TestCase):
    """SHA256 校验测试。"""

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="pilotstd_test_")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp)

    def test_valid_checksum_passes(self) -> None:
        import hashlib

        path = os.path.join(self.tmp, "test.bin")
        content = b"hello world"
        with open(path, "wb") as f:
            f.write(content)
        expected = hashlib.sha256(content).hexdigest()
        assert verify_checksum(path, expected) is True

    def test_invalid_checksum_fails(self) -> None:
        path = os.path.join(self.tmp, "test2.bin")
        with open(path, "wb") as f:
            f.write(b"hello world")
        assert verify_checksum(path, "deadbeef" * 8) is False

    def test_nonexistent_file_fails(self) -> None:
        assert verify_checksum("/nonexistent/file.bin", "deadbeef" * 8) is False


class TestGenerateUpdateScript(unittest.TestCase):
    """更新批处理脚本生成测试。"""

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="pilotstd_test_")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp)

    def test_generates_bat_file(self) -> None:
        zip_path = os.path.join(self.tmp, "update.zip")
        # 创建一个假的 zip 文件
        with open(zip_path, "wb") as f:
            f.write(b"PK\x03\x04")
        bat_path = generate_update_script(zip_path, self.tmp)
        assert os.path.exists(bat_path)
        assert bat_path.endswith("update.bat")

    def test_script_contains_essential_commands(self) -> None:
        zip_path = os.path.join(self.tmp, "update.zip")
        with open(zip_path, "wb") as f:
            f.write(b"PK\x03\x04")
        bat_path = generate_update_script(zip_path, self.tmp)
        with open(bat_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "PilotStd.exe" in content
        assert "Expand-Archive" in content
        assert "PilotStd" in content

    def test_empty_exe_dir_generates_script(self) -> None:
        """空目录也能生成更新脚本。"""
        zip_path = os.path.join(self.tmp, "u.zip")
        with open(zip_path, "wb") as f:
            f.write(b"PK\x03\x04")
        bat_path = generate_update_script(zip_path, self.tmp)
        assert os.path.isfile(bat_path)


class TestCheckLatestVersion(unittest.TestCase):
    """更新检查测试（mock 网络）。"""

    @patch("pilotstd.platform.updater.urllib.request.urlopen")
    def test_returns_release_info_on_success(self, mock_urlopen: MagicMock) -> None:
        import json

        mock_resp = MagicMock()
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.read.return_value = json.dumps(
            {
                "tag_name": "v0.55.0",
                "body": "更新说明",
                "assets": [
                    {
                        "name": "PilotStd-v0.55.0.zip",
                        "browser_download_url": "https://example.com/dl.zip",
                    }
                ],
            }
        ).encode()
        mock_urlopen.return_value = mock_resp

        result = check_latest_version()
        assert result is not None
        assert result["tag_name"] == "v0.55.0"
        assert result["filename"] == "PilotStd-v0.55.0.zip"

    @patch("pilotstd.platform.updater.urllib.request.urlopen")
    def test_returns_none_on_no_tag_name(self, mock_urlopen: MagicMock) -> None:
        import json

        mock_resp = MagicMock()
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.read.return_value = json.dumps(
            {
                "body": "无 tag",
                "assets": [],
            }
        ).encode()
        mock_urlopen.return_value = mock_resp

        result = check_latest_version()
        assert result is None

    @patch("pilotstd.platform.updater.urllib.request.urlopen")
    def test_returns_none_on_network_error(self, mock_urlopen: MagicMock) -> None:
        import urllib.error

        mock_urlopen.side_effect = urllib.error.URLError("connection refused")
        result = check_latest_version()
        assert result is None


class TestDownloadUpdate(unittest.TestCase):
    """下载更新测试（mock 网络）。"""

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="pilotstd_test_")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp)

    @patch("pilotstd.platform.updater.zipfile.is_zipfile")
    @patch("pilotstd.platform.updater.urllib.request.urlopen")
    def test_download_success_returns_true(self, mock_urlopen: MagicMock, mock_is_zip: MagicMock) -> None:
        mock_is_zip.return_value = True
        mock_resp = MagicMock()
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.headers = {"Content-Length": "4"}
        mock_resp.read.side_effect = [b"test", b""]
        mock_urlopen.return_value = mock_resp

        save_path = os.path.join(self.tmp, "dl.zip")
        result = download_update("http://fake.url", save_path)
        assert result is True
        assert os.path.exists(save_path)

    @patch("pilotstd.platform.updater.urllib.request.urlopen")
    def test_download_network_error_returns_false(self, mock_urlopen: MagicMock) -> None:
        import urllib.error

        mock_urlopen.side_effect = urllib.error.URLError("timeout")
        result = download_update("http://fake.url", os.path.join(self.tmp, "x.zip"))
        assert result is False
