# tests/gui/test_settings_announce.py
# 公告互斥逻辑测试：脏数据仲裁、自动互切、取消不影响对方

import os
import tempfile

import pytest

from pilotstd.core.config import ConfigManager


@pytest.fixture
def cfg():
    """临时文件 ConfigManager，每次测试独立。"""
    tmp = tempfile.mkdtemp(prefix="pilotstd_test_cfg_")
    path = os.path.join(tmp, "config.json")
    mgr = ConfigManager(filepath=path)
    yield mgr
    import shutil

    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def settings_page(qapp, cfg):
    """创建真实 SettingsPage，已走完 __init__ + _load_from_config。"""
    from pilotstd.ui.pages.settings._core import SettingsPage

    page = SettingsPage(cfg)
    yield page
    page.close()
    page.deleteLater()


class TestDirtyDataArbitration:
    """脏数据仲裁：配置双 True 时加载后自动修正。"""

    def test_double_true_arbitrates_to_local_only(self, qapp, cfg):
        """双 True 脏数据 → Web 缓存被强制关闭，URL 输入框同步禁用。"""
        cfg.set("announcement.enabled", True)
        cfg.set("query.use_announcement_match", True)
        cfg.save()

        from pilotstd.ui.pages.settings._core import SettingsPage

        page = SettingsPage(cfg)
        try:
            assert page.announcement_cb.isChecked() is True
            assert page.announce_cache_cb.isChecked() is False
            assert page.announce_url_edit.isEnabled() is False
            assert page.announcement_cb.isEnabled() is True
            assert page.announce_cache_cb.isEnabled() is True
            # 确认脏数据已被修正写盘
            assert cfg.get("query.use_announcement_match") is False
        finally:
            page.close()
            page.deleteLater()

    def test_single_true_no_change(self, settings_page, cfg):
        """只有本地公告 True 时，加载后不被仲裁误伤。"""
        cfg.set("announcement.enabled", True)
        cfg.set("query.use_announcement_match", False)
        cfg.save()
        settings_page._load_from_config()

        assert settings_page.announcement_cb.isChecked() is True
        assert settings_page.announce_cache_cb.isChecked() is False


class TestAutoToggle:
    """自动互切：勾选一方自动取消对方。"""

    def test_check_cache_auto_unchecks_local(self, settings_page):
        """勾选 Web 缓存 → 本地公告自动取消。"""
        # 前置：本地公告已勾选（触发槽函数，Web 缓存被自动取消）
        settings_page.announcement_cb.setChecked(True)
        assert settings_page.announcement_cb.isChecked() is True
        assert settings_page.announce_cache_cb.isChecked() is False

        # 用户点击 Web 缓存复选框
        settings_page.announce_cache_cb.click()

        assert settings_page.announcement_cb.isChecked() is False
        assert settings_page.announce_cache_cb.isChecked() is True
        assert settings_page.announce_url_edit.isEnabled() is True

    def test_check_local_auto_unchecks_cache(self, settings_page):
        """勾选本地公告 → Web 缓存自动取消。"""
        # 前置：Web 缓存已勾选（触发槽函数，本地公告被自动取消）
        settings_page.announce_cache_cb.setChecked(True)
        assert settings_page.announce_cache_cb.isChecked() is True
        assert settings_page.announcement_cb.isChecked() is False

        # 用户点击本地公告复选框
        settings_page.announcement_cb.click()

        assert settings_page.announce_cache_cb.isChecked() is False
        assert settings_page.announcement_cb.isChecked() is True


class TestUncheckDoesNotAffectOther:
    """取消勾选不应影响对方。"""

    def test_uncheck_cache_leaves_local_unchanged(self, settings_page):
        """取消 Web 缓存 → 本地公告状态不变。"""
        # 前置：Web 缓存已勾选
        settings_page.announce_cache_cb.click()
        assert settings_page.announce_cache_cb.isChecked() is True
        assert settings_page.announcement_cb.isChecked() is False

        # 用户取消勾选 Web 缓存
        settings_page.announce_cache_cb.click()

        assert settings_page.announcement_cb.isChecked() is False

    def test_uncheck_local_leaves_cache_unchanged(self, settings_page):
        """取消本地公告 → Web 缓存状态不变。"""
        # 前置：本地公告已勾选
        settings_page.announcement_cb.click()
        assert settings_page.announcement_cb.isChecked() is True
        assert settings_page.announce_cache_cb.isChecked() is False

        # 用户取消勾选本地公告
        settings_page.announcement_cb.click()

        assert settings_page.announce_cache_cb.isChecked() is False


class TestConfigPersistence:
    """配置写盘验证。"""

    def test_cache_toggle_writes_config(self, settings_page, cfg):
        """勾选 Web 缓存后配置正确写盘。"""
        settings_page._on_announce_cache_toggled(True)

        assert cfg.get("query.use_announcement_match") is True

    def test_local_toggle_writes_config(self, settings_page, cfg):
        """勾选本地公告后配置正确写盘。"""
        settings_page._on_announcement_toggled(True)

        assert cfg.get("announcement.enabled") is True
