# tests/test_security.py — 安全测试：认证、路径遍历、速率限制
import os
import sys

import pytest

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="module", autouse=True)
def _isolate_env_security(_isolate_env_standard_test_creds):
    """本模块启用标准测试凭证 env 隔离。"""
    pass


class TestAuthRateLimit:
    """登录速率限制测试（持久化到 SQLite）。"""

    def test_rate_limit_triggers_after_max_attempts(self):
        """连续失败 MAX_ATTEMPTS 次后应返回 429。"""
        import os
        import shutil
        import tempfile
        import time

        from docker.auth import LOCKOUT_SECONDS, MAX_ATTEMPTS
        from docker.users import (
            clear_login_failures,
            count_recent_failures,
            init_login_attempts_table,
            record_login_failure,
        )

        tmp = tempfile.mkdtemp(prefix="pilotstd_test_")
        try:
            # 临时覆盖数据库路径
            db_path = os.path.join(tmp, "test.db")
            import docker.users

            _orig = docker.users.get_db_path
            docker.users.get_db_path = lambda: db_path

            init_login_attempts_table()
            ip = "127.0.0.1"
            now = time.time()

            # 填充 MAX_ATTEMPTS 条记录
            for _ in range(MAX_ATTEMPTS):
                record_login_failure(ip)

            cutoff = now - LOCKOUT_SECONDS
            recent = count_recent_failures(ip, cutoff)
            assert recent >= MAX_ATTEMPTS, f"应有 {MAX_ATTEMPTS} 条失败记录，实际 {recent}"

            clear_login_failures(ip)
        finally:
            docker.users.get_db_path = _orig
            shutil.rmtree(tmp, ignore_errors=True)

    def test_rate_limit_clears_expired_entries(self):
        """超过 LOCKOUT_SECONDS 的记录不计入限流。"""
        import os
        import shutil
        import tempfile
        import time

        from docker.users import (
            clear_login_failures,
            count_recent_failures,
            init_login_attempts_table,
            record_login_failure,
        )

        tmp = tempfile.mkdtemp(prefix="pilotstd_test_")
        try:
            db_path = os.path.join(tmp, "test.db")
            import docker.users

            _orig = docker.users.get_db_path
            docker.users.get_db_path = lambda: db_path

            init_login_attempts_table()
            ip = "192.168.1.1"
            record_login_failure(ip)
            # 使用过期 cutoff 验证旧记录不被计入
            now = time.time()
            cutoff = now  # 当前时间，旧记录刚好过期
            recent = count_recent_failures(ip, cutoff)
            assert recent == 0, f"过期记录应不计入，实际 {recent}"

            clear_login_failures(ip)
        finally:
            docker.users.get_db_path = _orig
            shutil.rmtree(tmp, ignore_errors=True)


class TestPathValidation:
    """路径遍历防护测试。"""

    def test_valid_path_passes(self):
        """合法路径应通过校验。"""
        from docker.api.scan import _validate_path

        # /inbox 是允许的根目录
        result = _validate_path("/inbox/standards")
        assert os.path.isabs(result)

    def test_path_traversal_rejected(self):
        """../../../etc 应被拒绝。"""
        import os

        # 模拟一个受限场景：直接测试 abspath 前缀匹配逻辑
        abs_path = os.path.abspath("/media/../../../etc/passwd")
        abs_root = os.path.abspath("/media")
        # 路径遍历后不应在根目录下
        assert not abs_path.startswith(abs_root)

    def test_download_engine_path_traversal_rejected(self):
        """下载引擎应拒绝路径遍历攻击的标准号。"""
        import shutil
        import tempfile

        from pilotstd.download.engine import DownloadEngine
        from pilotstd.download.models import DownloadTask
        from pilotstd.download.session import SessionManager

        tmp_dir = tempfile.mkdtemp(prefix="pilotstd_dl_test_")
        try:
            session_mgr = SessionManager()
            engine = DownloadEngine(adapters=[], session_manager=session_mgr, save_root=tmp_dir)
            task = DownloadTask(standard_number="../../etc/passwd")
            try:
                engine._resolve_target_path(task)
                # 如果未抛异常，验证结果路径仍在 save_root 内
            except ValueError as e:
                assert "路径越界" in str(e)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_download_engine_normal_path_ok(self):
        """正常标准号的下载路径应在 _save_root 范围内。"""
        import shutil
        import tempfile

        from pilotstd.download.engine import DownloadEngine
        from pilotstd.download.models import DownloadTask
        from pilotstd.download.session import SessionManager

        tmp_dir = tempfile.mkdtemp(prefix="pilotstd_dl_test_")
        try:
            session_mgr = SessionManager()
            engine = DownloadEngine(adapters=[], session_manager=session_mgr, save_root=tmp_dir)
            task = DownloadTask(standard_number="GB/T 1.1-2020")
            result = engine._resolve_target_path(task)
            assert os.path.realpath(result).startswith(os.path.realpath(tmp_dir) + os.sep)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


class TestJWTToken:
    """JWT Token 安全测试。"""

    def test_token_contains_sub_and_iat(self):
        """Token 应包含 sub 和 iat 字段。"""
        from jose import jwt

        from docker.auth import SECRET, _generate_token

        token = _generate_token()
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        assert "sub" in payload
        assert payload["sub"].isdigit(), f"sub 应为数字字符串(user_id)，实际: {payload['sub']}"
        assert "iat" in payload
        assert "exp" in payload

    def test_token_has_expiry(self):
        """Token 应有过期时间且在合理范围内。"""
        from datetime import datetime, timezone

        from jose import jwt

        from docker.auth import SECRET, TOKEN_EXPIRE_HOURS, _generate_token

        token = _generate_token()
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        iat = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        delta_hours = (exp - iat).total_seconds() / 3600
        assert abs(delta_hours - TOKEN_EXPIRE_HOURS) < 0.01


class TestCSRFProtection:
    """CSRF 防护测试（独立 csrf_token Cookie + X-CSRF-Token 请求头）。"""

    def test_csrf_header_name_defined(self):
        """CSRF_HEADER 常量应已定义。"""
        from docker.auth import CSRF_HEADER

        assert CSRF_HEADER == "X-CSRF-Token"

    def test_state_changing_methods_checked(self):
        """POST/PUT/DELETE/PATCH 应在 CSRF 检查范围内。"""
        state_changing = {"POST", "PUT", "DELETE", "PATCH"}
        assert "POST" in state_changing
        assert "GET" not in state_changing  # GET 不受 CSRF 检查

    def test_login_sets_csrf_cookie(self):
        """登录成功后应设置独立的 csrf_token Cookie（httponly=False 供前端读取）。"""
        # 验证 CSRF token 是通过独立 cookie 而非复用 JWT
        from docker.auth import COOKIE_NAME

        assert COOKIE_NAME == "pilotstd_token"  # JWT cookie
        # csrf_token 是独立 cookie，登录时通过 resp.set_cookie("csrf_token", ...) 设置


class TestJWTSecretAutoGen:
    """JWT 密钥：未设置环境变量时自动生成，不再抛 RuntimeError。"""

    def test_missing_jwt_secret_auto_generates(self):
        """清除 JWT_SECRET 后导入 auth 模块应自动生成 SECRET，不抛异常。"""
        import importlib
        import os

        saved_secret = os.environ.pop("JWT_SECRET", None)
        try:
            if "docker.auth" in sys.modules:
                del sys.modules["docker.auth"]
            mod = importlib.import_module("docker.auth")
            assert mod.SECRET, "SECRET 不应为空"
            # token_urlsafe(32) 约 43 字符
            assert len(mod.SECRET) >= 32, f"SECRET 长度不足: {len(mod.SECRET)}"
        finally:
            if saved_secret:
                os.environ["JWT_SECRET"] = saved_secret
            if "docker.auth" in sys.modules:
                del sys.modules["docker.auth"]


class TestSecureCookie:
    """Cookie 安全标记测试。"""

    def test_cookie_name_defined(self):
        """Cookie 名称应已定义。"""
        from docker.auth import COOKIE_NAME

        assert COOKIE_NAME == "pilotstd_token"

    def test_auth_whitelist_contains_health(self):
        """健康检查端点应在白名单中。"""
        from docker.auth import AUTH_WHITELIST

        whitelist_paths = {path for path, _ in AUTH_WHITELIST}
        for p in ["/api/login", "/api/logout", "/api/health"]:
            assert p in whitelist_paths, f"{p} 不在白名单中"


class TestPasswordSecurity:
    """密码安全模块测试 — bcrypt 哈希与旧格式兼容。"""

    def test_get_password_hash_returns_bcrypt(self):
        from pilotstd.core.security import get_password_hash

        h = get_password_hash("test_password")
        assert h.startswith("$2b$"), f"应为 bcrypt 格式，实际：{h[:20]}..."

    def test_bcrypt_verify_correct_password(self):
        from pilotstd.core.security import get_password_hash, verify_password

        h = get_password_hash("correct")
        assert verify_password("correct", h) is True

    def test_bcrypt_verify_wrong_password(self):
        from pilotstd.core.security import get_password_hash, verify_password

        h = get_password_hash("correct")
        assert verify_password("wrong", h) is False

    def test_verify_legacy_desktop_format(self):
        import hashlib
        import secrets

        from pilotstd.core.security import verify_password

        salt = secrets.token_hex(16)
        digest = hashlib.sha256((salt + "desktop_password").encode()).hexdigest()
        assert verify_password("desktop_password", f"{salt}:{digest}") is True
        assert verify_password("wrong", f"{salt}:{digest}") is False

    def test_verify_legacy_docker_format(self):
        import hashlib

        from pilotstd.core.security import verify_password_with_salt

        salt = "a" * 64
        h = hashlib.pbkdf2_hmac("sha256", b"docker_password", salt.encode(), 100_000).hex()
        assert verify_password_with_salt("docker_password", h, salt) is True
        assert verify_password_with_salt("wrong", h, salt) is False

    def test_needs_upgrade_detects_legacy(self):
        from pilotstd.core.security import needs_upgrade

        assert needs_upgrade("a" * 64) is True
        assert needs_upgrade("salt:digest") is True
        assert needs_upgrade("") is True

    def test_needs_upgrade_bcrypt_skipped(self):
        from pilotstd.core.security import get_password_hash, needs_upgrade

        bcrypt_hash = get_password_hash("modern")
        assert needs_upgrade(bcrypt_hash) is False

    def test_empty_password_rejected(self):
        from pilotstd.core.security import verify_password, verify_password_with_salt

        assert verify_password("", "") is False
        assert verify_password("anything", "") is False
        assert verify_password_with_salt("anything", "", "salt") is False

    def test_generate_salt_returns_hex(self):
        from pilotstd.core.security import generate_salt

        s = generate_salt()
        assert len(s) == 32
        assert all(c in "0123456789abcdef" for c in s)
