"""SUPERUSER_PASSWORD 优先于旧版 ADMIN_PASSWORD（compose/文档口径）。"""

import pytest

from docker.users import _ensure_superuser
from pilotstd.core.db import Database
from pilotstd.core.security import verify_password_with_salt


@pytest.fixture()
def db(tmp_path):
    db = Database(str(tmp_path / "users.db"))
    yield db
    db.close()


def _row(db, username):
    return db.fetchone(
        "SELECT role, password_hash, salt FROM users WHERE username = ?", (username,)
    )


def test_superuser_password_takes_precedence(db, monkeypatch):
    monkeypatch.setenv("SUPERUSER_PASSWORD", "NewStylePass123")
    monkeypatch.setenv("ADMIN_PASSWORD", "LegacyPass456")
    _ensure_superuser(db, "guide_admin")
    row = _row(db, "guide_admin")
    assert row is not None
    assert row["role"] == "admin"
    assert verify_password_with_salt("NewStylePass123", row["password_hash"], row["salt"])
    assert not verify_password_with_salt("LegacyPass456", row["password_hash"], row["salt"])


def test_legacy_admin_password_fallback(db, monkeypatch):
    monkeypatch.delenv("SUPERUSER_PASSWORD", raising=False)
    monkeypatch.setenv("ADMIN_PASSWORD", "LegacyPass456")
    _ensure_superuser(db, "legacy_admin")
    row = _row(db, "legacy_admin")
    assert verify_password_with_salt("LegacyPass456", row["password_hash"], row["salt"])
