"""可信 IP 密钥策略回归（2026-10-24）：环境变量 > config > 抛错，不保留可用默认值。"""

import pytest

from pilotstd.manager.wechat_ip_service import WechatIPService


class _Cfg:
    """最小配置替身：只实现 get/set/save。"""

    def __init__(self, data: dict | None = None) -> None:
        self._d = dict(data or {})
        self.saved = False

    def get(self, key: str, default=None):
        return self._d.get(key, default)

    def set(self, key: str, value) -> None:
        self._d[key] = value

    def save(self) -> None:
        self.saved = True


class _Mgr:
    def __init__(self, data: dict | None = None) -> None:
        self.cfg = _Cfg(data)


def test_env_secret_wins(monkeypatch):
    monkeypatch.setenv("WECHAT_IP_ENCRYPT_SECRET", "from-env")
    svc = WechatIPService(_Mgr({"wechat_ip.encrypt_secret": "from-cfg"}))
    assert svc._get_secret() == "from-env"


def test_cfg_secret_fallback(monkeypatch):
    monkeypatch.delenv("WECHAT_IP_ENCRYPT_SECRET", raising=False)
    svc = WechatIPService(_Mgr({"wechat_ip.encrypt_secret": "from-cfg"}))
    assert svc._get_secret() == "from-cfg"


def test_missing_secret_raises(monkeypatch):
    monkeypatch.delenv("WECHAT_IP_ENCRYPT_SECRET", raising=False)
    svc = WechatIPService(_Mgr())
    with pytest.raises(RuntimeError) as exc:
        svc._get_secret()
    assert "WECHAT_IP_ENCRYPT_SECRET" in str(exc.value)


def test_update_config_refuses_without_secret(monkeypatch):
    """无密钥时带 cookie 保存必须失败，且不落任何加密值。"""
    monkeypatch.delenv("WECHAT_IP_ENCRYPT_SECRET", raising=False)
    mgr = _Mgr()
    result = WechatIPService(mgr).update_config({"cookie_raw": "sessionid=abc"})
    assert result["ok"] is False
    assert "WECHAT_IP_ENCRYPT_SECRET" in result["error"]
    assert mgr.cfg.get("wechat_ip.encrypted_cookie", "") == ""
    assert mgr.cfg.saved is False


def test_update_config_encrypts_with_env_secret(monkeypatch):
    monkeypatch.setenv("WECHAT_IP_ENCRYPT_SECRET", "unit-test-secret")
    mgr = _Mgr()
    result = WechatIPService(mgr).update_config({"cookie_raw": "sessionid=abc"})
    assert result["ok"] is True
    assert mgr.cfg.get("wechat_ip.encrypted_cookie", "")
    assert mgr.cfg.get("wechat_ip.cookie_source") == "manual"


def test_masked_secret_not_overwritten(monkeypatch):
    """GET 返回 *** 掩码；前端原样 PUT 时不得覆盖真实 key/password。"""
    monkeypatch.setenv("WECHAT_IP_ENCRYPT_SECRET", "unit-test-secret")
    mgr = _Mgr({
        "wechat_ip.cookiecloud_key": "real-key",
        "wechat_ip.cookiecloud_password": "real-pass",
    })
    result = WechatIPService(mgr).update_config({
        "cookiecloud_key": "***",
        "cookiecloud_password": "***",
        "cookie_source": "cookiecloud",
    })
    assert result["ok"] is True
    assert mgr.cfg.get("wechat_ip.cookiecloud_key") == "real-key"
    assert mgr.cfg.get("wechat_ip.cookiecloud_password") == "real-pass"
    assert mgr.cfg.get("wechat_ip.cookie_source") == "cookiecloud"


def test_cookiecloud_status_not_misreported_as_missing_secret():
    mgr = _Mgr({"wechat_ip.cookie_source": "cookiecloud", "wechat_ip.cookiecloud_key": "k"})
    assert WechatIPService(mgr).get_config()["cookie_status"] == "已配置 (CookieCloud)"

    mgr2 = _Mgr({"wechat_ip.cookie_source": "cookiecloud"})
    assert WechatIPService(mgr2).get_config()["cookie_status"] == "未配置 CookieCloud Key"
