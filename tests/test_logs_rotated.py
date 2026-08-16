# tests/test_logs_rotated.py — 轮转日志访问端点测试
"""覆盖列表、分页读取、grep+context、非法文件名、未鉴权、空文件/不存在文件。"""

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from docker.api import logs as logs_mod


@pytest.fixture
def log_dir(tmp_path, monkeypatch):
    """monkeypatch 日志目录到临时目录。"""
    monkeypatch.setattr(logs_mod, "_get_log_dir", lambda: str(tmp_path))
    # 重置列表缓存，避免跨测试污染
    monkeypatch.setattr(logs_mod, "_list_cache", {"ts": 0.0, "files": []})
    return tmp_path


def _make_request(cookie: str | None = None) -> Request:
    """构造带可选 cookie 的 Request。"""
    headers = [(b"cookie", cookie.encode())] if cookie else []
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": headers,
        "query_string": b"",
        "server": ("test", 80),
        "client": ("test", 123),
        "scheme": "http",
        "root_path": "",
    }
    return Request(scope)


def _auth(monkeypatch, role: str = "admin"):
    """mock jwt.decode 返回指定角色。"""
    monkeypatch.setattr("docker.auth.jwt.decode", lambda *a, **k: {"role": role, "sub": "1"})


class TestListRotated:
    def test_list_rotated_files(self, log_dir):
        (log_dir / "app.log.1").write_text("a\nb\n", encoding="utf-8")
        (log_dir / "app.log.2").write_text("c\n", encoding="utf-8")
        (log_dir / "other.txt").write_text("x\n", encoding="utf-8")  # 不匹配，应排除
        files = logs_mod._list_rotated_impl()
        names = {f["name"] for f in files}
        assert names == {"app.log.1", "app.log.2"}
        for f in files:
            assert set(f) == {"name", "size_bytes", "mtime_iso", "lines_estimate"}
            assert f["size_bytes"] > 0

    def test_list_empty_dir(self, log_dir):
        assert logs_mod._list_rotated_impl() == []


class TestReadRotated:
    def test_read_with_pagination(self, log_dir):
        lines = [f"line{i}\n" for i in range(10)]
        (log_dir / "app.log.1").write_text("".join(lines), encoding="utf-8")
        r = logs_mod._read_rotated_impl("app.log.1", offset=2, limit=3, grep="", context=0)
        assert r["total_lines"] == 10
        assert r["returned_lines"] == 3
        assert r["offset"] == 2
        assert r["content"] == ["line2", "line3", "line4"]

    def test_read_grep_with_context(self, log_dir):
        (log_dir / "app.log.1").write_text(
            "a\nb\nERROR x\nc\nd\nERROR y\ne\nf\n", encoding="utf-8"
        )
        r = logs_mod._read_rotated_impl("app.log.1", offset=0, limit=100, grep="ERROR", context=1)
        # 匹配 ERROR x：前 b + ERROR x + 后 c；匹配 ERROR y：前 d + ERROR y + 后 e
        assert r["content"] == ["b", "ERROR x", "c", "d", "ERROR y", "e"]

    def test_read_empty_file(self, log_dir):
        (log_dir / "app.log.1").write_text("", encoding="utf-8")
        r = logs_mod._read_rotated_impl("app.log.1", 0, 100, "", 0)
        assert r["total_lines"] == 0
        assert r["content"] == []

    def test_read_nonexistent_file(self, log_dir):
        with pytest.raises(HTTPException) as e:
            logs_mod._read_rotated_impl("app.log.99", 0, 100, "", 0)
        assert e.value.status_code == 404


class TestSecurity:
    @pytest.mark.parametrize("bad", ["../../etc/passwd", "app.log.abc", "app.log..1", "/app.log", "app.log.1%2e"])
    def test_invalid_filename_400(self, bad, monkeypatch):
        _auth(monkeypatch)
        req = _make_request("pilotstd_token=fake")
        with pytest.raises(HTTPException) as e:
            logs_mod.read_rotated_log(req, bad)
        assert e.value.status_code == 400

    def test_unauthorized_403(self, monkeypatch):
        # 无 cookie → require_role 判 user → 403
        req = _make_request(None)
        with pytest.raises(HTTPException) as e:
            logs_mod.list_rotated_logs(req)
        assert e.value.status_code == 403
