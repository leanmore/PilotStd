# tests/test_notification_api.py
# 通知系统 API 端点测试
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest

from docker.auth import COOKIE_NAME, AuthMiddleware
from docker.auth import router as auth_router


class TestNotificationAPI(unittest.TestCase):
    """测试通知 API 端点逻辑。"""

    def test_mark_read_request_model_default_id_none(self):
        """MarkReadRequest 的 id 默认应为 None。"""
        from docker.api.notification import MarkReadRequest

        req = MarkReadRequest()
        self.assertIsNone(req.id)

    def test_mark_read_request_model_with_id(self):
        """MarkReadRequest 接受指定的 id。"""
        from docker.api.notification import MarkReadRequest

        req = MarkReadRequest(id=42)
        self.assertEqual(req.id, 42)

    def test_mark_all_read_response_format(self):
        """标记全部已读应返回 ok: True。"""
        response = {"ok": True, "message": "已标记为已读"}
        self.assertTrue(response["ok"])
        self.assertIn("已标记为已读", response["message"])

    def test_mark_single_read_not_found_response(self):
        """标记不存在的 ID 应返回 404。"""
        response = {"error": "通知 ID 999 不存在"}
        self.assertIn("不存在", response["error"])

    def test_logs_response_includes_is_read_field(self):
        """logs 返回的 items 应包含 is_read 字段。"""
        items = [
            {
                "id": 1,
                "event_type": "test",
                "channel": "wechat",
                "title": "Test",
                "body": "Hello",
                "standard_number": None,
                "status": "success",
                "error_msg": None,
                "sent_at": "2026-06-29T12:00:00",
                "is_read": 0,
            }
        ]
        self.assertIn("is_read", items[0])
        self.assertEqual(items[0]["is_read"], 0)


class TestUpdateConfigSync(unittest.TestCase):
    """阶段一：PUT /api/notification/config 更新 enabled 时同时写 config.json 与 user_preferences。"""

    def _make_mgr(self):
        from unittest.mock import MagicMock

        mgr = MagicMock()
        mgr.cfg = MagicMock()
        mgr.user_service = MagicMock()
        mgr.notification_mgr = MagicMock()
        return mgr

    @staticmethod
    def _body(result):
        """第 2 批起 update_config 返回 JSONResponse（响应体含 warnings），此处取出 JSON。"""
        import json

        return json.loads(bytes(result.body).decode("utf-8"))

    def test_enabled_writes_both_config_and_db(self):
        from unittest.mock import MagicMock

        from docker.api.notification import update_config

        mgr = self._make_mgr()
        result = update_config(request=MagicMock(), body={"enabled": True}, mgr=mgr, user_id=1)
        mgr.cfg.set.assert_called_once_with("notification.enabled", True)
        mgr.user_service.save_preference.assert_called_once_with(1, "notification.enabled", True)
        mgr.cfg.save.assert_called_once()
        mgr._init_notification.assert_called_once()
        self.assertEqual(self._body(result)["ok"], True)

    def test_enabled_false_writes_db(self):
        from unittest.mock import MagicMock

        from docker.api.notification import update_config

        mgr = self._make_mgr()
        update_config(request=MagicMock(), body={"enabled": False}, mgr=mgr, user_id=2)
        mgr.user_service.save_preference.assert_called_once_with(2, "notification.enabled", False)

    def test_db_write_failure_does_not_block(self):
        from unittest.mock import MagicMock

        from docker.api.notification import update_config

        mgr = self._make_mgr()
        mgr.user_service.save_preference.side_effect = RuntimeError("db down")
        result = update_config(request=MagicMock(), body={"enabled": True}, mgr=mgr, user_id=1)
        mgr.cfg.set.assert_called_once_with("notification.enabled", True)
        mgr._init_notification.assert_called_once()
        self.assertEqual(self._body(result)["ok"], True)


# ════════════════════════════════════════════════════════════════
# TD-9 回归：_get_user_id 语义修复（按主键校验，禁止按 username 查询/兜底 1）
# ════════════════════════════════════════════════════════════════


class TestGetUserIdResolution:
    """TD-9：_get_user_id 必须按主键校验，不得按 username 查询或静默兜底 1。"""

    def test_unknown_user_raises_401(self):
        """用户不存在 → 显式 401（替代原兜底返回 1）。"""
        from unittest.mock import MagicMock

        import pytest
        from fastapi import HTTPException

        from docker.api.notification import _get_user_id

        mock_mgr = MagicMock()
        mock_mgr.user_service.get_user_by_id.return_value = None
        with pytest.raises(HTTPException) as exc:
            _get_user_id(user_id=99, mgr=mock_mgr)
        assert exc.value.status_code == 401

    def test_existing_user_returns_same_id(self):
        """用户存在 → 返回原 user_id（不再被折叠为 1）。"""
        from unittest.mock import MagicMock

        from docker.api.notification import _get_user_id

        mock_mgr = MagicMock()
        mock_mgr.user_service.get_user_by_id.return_value = {"id": 7, "username": "u7"}
        assert _get_user_id(user_id=7, mgr=mock_mgr) == 7


# ════════════════════════════════════════════════════════════════
# TD-9 集成：真实 AuthMiddleware + login cookie + 真实 SQLite
# ════════════════════════════════════════════════════════════════

_TEST_NOTIF_USER = "notif_user"


@pytest.fixture(scope="module", autouse=True)
def _set_notif_test_env():
    """设置测试环境变量，模块结束后恢复原值，避免污染其他测试文件。"""
    keys = ("JWT_SECRET", "ADMIN_PASSWORD", "SUPERUSER")
    old = {k: os.environ.get(k) for k in keys}
    os.environ["JWT_SECRET"] = "notif_td9_test_secret_key"
    os.environ["ADMIN_PASSWORD"] = "notif_td9_test_pass_42"
    os.environ["SUPERUSER"] = _TEST_NOTIF_USER
    yield
    for k, v in old.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


@pytest.fixture(scope="module")
def notif_client_and_db(tmp_path_factory, _set_notif_test_env):
    """创建 TestClient + 真实 SQLite + 测试用户；manager 用真实 UserService + mock 通知子系统。"""
    from unittest.mock import MagicMock

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from pilotstd.core.db import Database
    from pilotstd.core.security import generate_salt, get_password_hash
    from pilotstd.manager.user_service import UserService

    tmpdir = tmp_path_factory.mktemp("notif_td9")
    db = Database(str(tmpdir / "test.db"))
    db.execute(
        """CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    must_change_password INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);"""
    )
    db.execute("CREATE TABLE IF NOT EXISTS login_attempts (ip TEXT NOT NULL, attempt_time REAL NOT NULL)")

    pw_hash = get_password_hash(os.environ["ADMIN_PASSWORD"])
    salt = generate_salt()
    db.execute(
        "INSERT INTO users (username, password_hash, salt, role, must_change_password) VALUES (?, ?, ?, ?, ?)",
        (_TEST_NOTIF_USER, pw_hash, salt, "admin", 0),
    )

    # 注入测试数据库到 users/auth 模块，确保 login 端点使用测试 DB
    from docker import auth as auth_mod
    from docker import users as users_mod

    users_mod._db_instance = db
    auth_mod._init_done = True

    # 构造 manager：真实 UserService（查询测试 DB）+ mock 通知子系统
    mgr = MagicMock()
    mgr.db = db
    mgr.user_service = UserService(mgr)
    mgr.notification_mgr = MagicMock()
    mgr.notification_mgr._cred_helper = MagicMock()
    mgr.notification_mgr._cred_helper.get_all.return_value = {}
    mgr.notification_mgr.enabled = True
    mgr.cfg = MagicMock()
    mgr.cfg.get.return_value = []

    from docker.api.notification import router as notification_router
    from docker.manager import get_manager_dep

    app = FastAPI()
    app.add_middleware(AuthMiddleware)
    app.include_router(auth_router)
    app.include_router(notification_router)
    app.dependency_overrides[get_manager_dep] = lambda: mgr

    client = TestClient(app)
    yield client, db
    db.close()


@pytest.fixture(scope="module")
def notif_cookies(notif_client_and_db):
    """模块级：真实登录获取 cookie，所有集成测试共享。"""
    client, _ = notif_client_and_db
    r = client.post(
        "/api/login",
        data={"username": _TEST_NOTIF_USER, "password": os.environ["ADMIN_PASSWORD"]},
    )
    assert r.status_code == 200, f"登录失败: {r.status_code} {r.text[:200]}"
    cookies = dict(r.cookies)
    assert COOKIE_NAME in cookies, "登录响应未包含 pilotstd_token cookie"
    return cookies


@pytest.mark.xdist_group("notification")
def test_notif_config_returns_200_with_valid_user(notif_client_and_db, notif_cookies):
    """回归：合法登录用户访问通知配置返回 200（不再被解析为 user 1）。"""
    client, _ = notif_client_and_db
    r = client.get("/api/notification/config", cookies=notif_cookies)
    assert r.status_code == 200, f"应返回 200，实际 {r.status_code}: {r.text}"


@pytest.mark.xdist_group("notification")
def test_notif_config_401_without_cookie(notif_client_and_db):
    """无 Cookie 时鉴权链路仍返回 401（未绕过 AuthMiddleware）。"""
    client, _ = notif_client_and_db
    client.cookies.clear()
    r = client.get("/api/notification/config")
    assert r.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# 步 A C2：`GET /api/notification/channels` —— 渠道元数据契约与三层一致性
# 设计依据 docs/plans/notification-system-design/07-impl-design-A.md §三
# ══════════════════════════════════════════════════════════════════════════════

_CHANNEL_TOP_KEYS = {
    "name",
    "label_key",
    "icon",
    "enabled_default",
    "hint_key",
    "fields",
    "status_rule",
}
_FIELD_KEYS = {
    "name",
    "type",
    "label_key",
    "label",
    "required",
    "mask",
    "password",
    "placeholder",
    "placeholder_key",
    "badge_key",
    "divider_key",
}
# 后端实现细节：**不得**出现在面向前端的元数据里（`ctor` 由裁决 2 明确移除）
_IMPL_KEYS = {"ctor", "ctor_required", "cls_name", "module", "legacy_label_key"}


def _get_channels(client, cookies) -> dict:
    """取渠道元数据响应体（带状态码断言，避免把错误体当契约用）。"""
    r = client.get("/api/notification/channels", cookies=cookies)
    assert r.status_code == 200, f"应返回 200，实际 {r.status_code}: {r.text}"
    return r.json()


@pytest.mark.xdist_group("notification")
def test_channels_endpoint_shape(notif_client_and_db, notif_cookies):
    """V1：契约逐项断言——必备字段齐全、类型正确、**不含实现细节**、无凭证值。"""
    from pilotstd.core.notification.channel_spec import CHANNEL_SPECS

    client, _ = notif_client_and_db
    body = _get_channels(client, notif_cookies)
    assert set(body) == {"spec_hash", "channels"}
    assert isinstance(body["spec_hash"], str) and len(body["spec_hash"]) == 16
    assert len(body["channels"]) == len(CHANNEL_SPECS)
    for ch in body["channels"]:
        assert set(ch) == _CHANNEL_TOP_KEYS, f"{ch['name']} 顶层键不符"
        assert isinstance(ch["fields"], list) and ch["fields"]
        for field in ch["fields"]:
            assert set(field) == _FIELD_KEYS, f"{ch['name']}.{field.get('name')} 字段键不符"
        rule = ch["status_rule"]
        assert set(rule) == {"branches", "fallback_key"}
        for branch in rule["branches"]:
            assert set(branch) == {"all_of", "label_key"}
    # 实现细节与凭证一律不得出现在响应文本里
    raw = repr(body)
    for key in _IMPL_KEYS:
        assert key not in raw, f"响应体不应含实现细节 {key}"
    assert "***" not in raw and "tel_token" not in raw


@pytest.mark.xdist_group("notification")
def test_channels_endpoint_matches_spec(notif_client_and_db, notif_cookies):
    """V5（替回 T2）：**跨层**——API 响应的渠道集合与每渠道字段集合必须等于 spec 声明。

    为什么是跨层而非同源：`channel_spec` 是唯一声明源，若只比对它的两个视图会恒真；
    本用例经 **HTTP 端点**取回，中途任何硬编码/漏渠道/字段漂移都会 FAIL。
    """
    from pilotstd.core.notification.channel_spec import CHANNEL_SPECS

    client, _ = notif_client_and_db
    body = _get_channels(client, notif_cookies)
    assert {c["name"] for c in body["channels"]} == {s.name for s in CHANNEL_SPECS}
    spec_fields = {s.name: [f.name for f in s.fields] for s in CHANNEL_SPECS}
    for ch in body["channels"]:
        assert [f["name"] for f in ch["fields"]] == spec_fields[ch["name"]], ch["name"]
        spec = next(s for s in CHANNEL_SPECS if s.name == ch["name"])
        assert ch["enabled_default"] == spec.enabled_default
        assert ch["label_key"] == spec.label_key


@pytest.mark.xdist_group("notification")
def test_spec_hash_stable_and_sensitive(notif_client_and_db, notif_cookies, monkeypatch):
    """V2：`spec_hash` 判别力——同负载两次一致；负载变化（加字段）则**必须变化**。"""
    import copy

    # patch 目标随实现迁移：`/channels` 端点在步 C 后位于 notification_config（再导出不生效——
    # 端点读的是该模块自己的名字）
    import docker.api.notification_config as api_mod
    from pilotstd.core.notification.channel_spec import spec_payload

    client, _ = notif_client_and_db
    first = _get_channels(client, notif_cookies)["spec_hash"]
    again = _get_channels(client, notif_cookies)["spec_hash"]
    assert first == again, "同一负载两次调用必须得到相同哈希（不得含时间戳/随机量）"

    mutated = copy.deepcopy(spec_payload())
    mutated["channels"][0]["fields"].append({"name": "zz_probe_xyz", "type": "string"})
    monkeypatch.setattr(api_mod, "spec_payload", lambda: mutated)
    changed = _get_channels(client, notif_cookies)["spec_hash"]
    assert changed != first, "负载变化后哈希未变——说明哈希与负载无关（判别力为零）"


@pytest.mark.xdist_group("notification")
def test_three_layer_channel_consistency(notif_client_and_db, notif_cookies):
    """V6：三层一致性——spec == API 响应 == 前端实际声明的渠道集合。

    第三层锚在**前端源码**的结构位字面量（`key:`/`value:` 的渠道列表块），
    与 `channel_spec` 无派生关系，故任一层漂移都会 FAIL。
    """
    import os
    import sys
    from pathlib import Path

    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
    from _frontend_channel_scan import structural_keys

    from pilotstd.core.notification.channel_spec import CHANNEL_SPECS

    repo_root = Path(__file__).resolve().parent.parent
    spec_keys = {s.name for s in CHANNEL_SPECS}
    api_keys = {c["name"] for c in _get_channels(notif_client_and_db[0], notif_cookies)["channels"]}
    fe_keys = structural_keys(repo_root)
    assert spec_keys == api_keys, f"spec {sorted(spec_keys)} != API {sorted(api_keys)}"
    # C3（前端 schema 驱动改造）落地前，前端仍硬编码渠道列表，此时三层必须完全一致；
    # 落地后结构位字面量归零，只保留"不得出现未知渠道"这一半（由 B4 棘轮继续守）。
    if fe_keys:
        assert fe_keys == spec_keys, f"前端 {sorted(fe_keys)} 与 spec 不一致——三层漂移"
    assert not (fe_keys - spec_keys), "前端不得出现 spec 未声明的渠道"


def test_spec_endpoint_returns_subscribable_events():
    """D5：可订阅事件清单来自事件规格（前端零硬编码），集合与规格逐条一致。"""
    from docker.api.notification_config import get_notification_spec
    from pilotstd.core.notification.event_spec import EVENT_SPECS

    payload = get_notification_spec()
    expected = [s.key for s in EVENT_SPECS if s.subscribable]
    assert payload["events"] == expected
    assert len(payload["events"]) == 35
