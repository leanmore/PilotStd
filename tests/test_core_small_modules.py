"""核心小模块补测（NEW-43，2026-11-24）。

清单点名的高价值无测试模块，逐个补齐：
  1. `notification/_builders_common.py` —— 事件构建器共享助手（标准号展示/链接/类型标签/预计下载日）
  2. `validity_replacement.py` —— 替代关系方向判定（防止"代替旧号"被当成新标准）
  3. `query/adapters/_shared_ssl.py` —— 进程级共享 SSL context（避免重复加载 CA）

这三个模块都是「一处逻辑错、影响面广」的核心：
  - 构建器助手错了 → 所有通知文案失真
  - 方向判定错了 → 用户被告知"有新版本"但实际是旧号
  - SSL context 错了 → 12 个适配器全部连不上或白付 6.7s
"""

import ssl
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ════════════════════════════════════════════════════════════════
# 1. _builders_common：标准号展示 / 链接 / 类型标签 / 预计下载日
# ════════════════════════════════════════════════════════════════


class TestBuildersCommon:
    """事件构建器共享助手。"""

    def test_std_label_both_present(self):
        from pilotstd.core.notification._builders_common import _std_label

        assert _std_label("GB/T 1-2020", "标准名") == "GB/T 1-2020 标准名"

    def test_std_label_number_only(self):
        """名称缺失时只返回标准号（不产生尾部空格）。"""
        from pilotstd.core.notification._builders_common import _std_label

        assert _std_label("GB/T 1-2020", "") == "GB/T 1-2020"
        assert _std_label("GB/T 1-2020", "   ") == "GB/T 1-2020"

    def test_std_label_name_only(self):
        """标准号缺失时只返回名称。"""
        from pilotstd.core.notification._builders_common import _std_label

        assert _std_label("", "标准名") == "标准名"

    def test_std_label_both_empty(self):
        from pilotstd.core.notification._builders_common import _std_label

        assert _std_label("", "") == ""

    def test_make_link_with_number(self):
        from pilotstd.core.notification._builders_common import _make_link

        assert _make_link("GB/T 1-2020") == "/standards/GB/T 1-2020"

    def test_make_link_without_number(self):
        """标准号为空 → None（消息不含跳转）。"""
        from pilotstd.core.notification._builders_common import _make_link

        assert _make_link(None) is None
        assert _make_link("") is None

    def test_std_type_text_known(self):
        from pilotstd.core.notification._builders_common import _std_type_text

        # 三种已知类型都应返回非空（具体文案随语言变，只断言非空）
        for st in ("NationalStd", "IndustryStd", "LocalStd"):
            assert _std_type_text(st), f"{st} 应有标签"

    def test_std_type_text_unknown_returns_empty(self):
        """未知类型返回空串（模板中省略该行）。"""
        from pilotstd.core.notification._builders_common import _std_type_text

        assert _std_type_text("UnknownType") == ""
        assert _std_type_text("") == ""

    def test_expected_download_date_empty_input(self):
        from pilotstd.core.notification._builders_common import _expected_download_date

        assert _expected_download_date("") == ""

    def test_expected_download_date_invalid_input(self):
        """无法解析的日期 → 空串（模板回退通用提示），不抛异常。"""
        from pilotstd.core.notification._builders_common import _expected_download_date

        assert _expected_download_date("not-a-date") == ""

    def test_expected_download_date_adds_cooldown(self, monkeypatch):
        """预计下载日 = 发布日期 + 冷却期（默认 28 天）。"""
        from pilotstd.core.notification._builders_common import _expected_download_date

        monkeypatch.setenv("ARCHIVE_COOLDOWN_DAYS", "28")
        # 2026-01-01 + 28 天 = 2026-01-29
        assert _expected_download_date("2026-01-01") == "2026-01-29"

    def test_expected_download_date_respects_env(self, monkeypatch):
        """冷却期与收藏下载链同源（ARCHIVE_COOLDOWN_DAYS），避免双源漂移。"""
        from pilotstd.core.notification._builders_common import _expected_download_date

        monkeypatch.setenv("ARCHIVE_COOLDOWN_DAYS", "7")
        assert _expected_download_date("2026-01-01") == "2026-01-08"


# ════════════════════════════════════════════════════════════════
# 2. validity_replacement：替代关系方向判定
# ════════════════════════════════════════════════════════════════


class TestValidityReplacement:
    """替代关系方向判定（防止"代替旧号"被当成新标准）。"""

    def test_forward_replacement_is_not_backward(self):
        """新号年份更晚 → 正常替代，不是倒退。"""
        from pilotstd.core.validity_replacement import is_backward_replacement

        assert is_backward_replacement("GB 50011-2010", "GB 50011-2016") is False

    def test_backward_replacement_detected(self):
        """新号年份更早 → 方向倒退，必须识别。"""
        from pilotstd.core.validity_replacement import is_backward_replacement

        assert is_backward_replacement("GB 50011-2016", "GB 50011-2010") is True

    def test_same_year_not_backward(self):
        from pilotstd.core.validity_replacement import is_backward_replacement

        assert is_backward_replacement("GB 50011-2010", "GB 50011-2010") is False

    def test_unparseable_returns_false(self):
        """年份解析不出来时保守返回 False（不误判为倒退）。"""
        from pilotstd.core.validity_replacement import is_backward_replacement

        assert is_backward_replacement("", "") is False
        assert is_backward_replacement("garbage", "garbage2") is False

    def test_replacement_info_no_row(self):
        """查不到替代记录 → 空 dict。"""
        from pilotstd.core.validity_replacement import replacement_info

        class _Db:
            def fetchone(self, *_a, **_kw):
                return None

        assert replacement_info(_Db(), "GB 1-2020") == {}

    def test_replacement_info_backward_returns_empty(self):
        """方向倒退时返回空（不把旧号当新标准展示）。"""
        from pilotstd.core.validity_replacement import replacement_info

        class _Row(dict):
            def keys(self):
                return super().keys()

        class _Db:
            def __init__(self):
                self._calls = 0

            def fetchone(self, *_a, **_kw):
                self._calls += 1
                if self._calls == 1:
                    return _Row(superseded_by="GB 50011-2010")
                return _Row(std_name="旧名", implement_date="2010-01-01")

        assert replacement_info(_Db(), "GB 50011-2016") == {}

    def test_replacement_info_forward_returns_details(self):
        """方向正常时返回新标准号、名称与实施日期。"""
        from pilotstd.core.validity_replacement import replacement_info

        class _Row(dict):
            def keys(self):
                return super().keys()

        class _Db:
            def __init__(self):
                self._calls = 0

            def fetchone(self, *_a, **_kw):
                self._calls += 1
                if self._calls == 1:
                    return _Row(superseded_by="GB 50011-2016")
                return _Row(std_name="新名", implement_date="2016-08-01")

        info = replacement_info(_Db(), "GB 50011-2010")
        assert info["new_standard"] == "GB 50011-2016"
        assert info["new_standard_name"] == "新名"
        assert info["new_standard_implementation_date"] == "2016-08-01"


# ════════════════════════════════════════════════════════════════
# 3. _shared_ssl：进程级共享 SSL context
# ════════════════════════════════════════════════════════════════


class TestSharedSsl:
    """进程级共享 SSL context（避免 12 个适配器逐个加载 CA 包）。"""

    def test_returns_ssl_context(self):
        from pilotstd.query.adapters._shared_ssl import default_ssl_context

        ctx = default_ssl_context()
        assert isinstance(ctx, ssl.SSLContext)

    def test_singleton_same_object(self):
        """重复调用返回**同一个**对象（这是性能优化的核心契约）。"""
        from pilotstd.query.adapters import _shared_ssl

        first = _shared_ssl.default_ssl_context()
        second = _shared_ssl.default_ssl_context()
        assert first is second

    def test_caches_after_first_call(self, monkeypatch):
        """首次之后不再调用 `ssl.create_default_context`（省掉 1.3s CA 加载）。"""
        from pilotstd.query.adapters import _shared_ssl

        # 重置模块级单例
        monkeypatch.setattr(_shared_ssl, "_CONTEXT", None)
        calls = {"n": 0}
        real = ssl.create_default_context

        def _spy(*a, **kw):
            calls["n"] += 1
            return real(*a, **kw)

        monkeypatch.setattr(ssl, "create_default_context", _spy)
        _shared_ssl.default_ssl_context()
        _shared_ssl.default_ssl_context()
        _shared_ssl.default_ssl_context()
        assert calls["n"] == 1, f"应只构造一次，实际 {calls['n']} 次"

    def test_verify_mode_is_enabled(self):
        """必须是**默认校验**的 context（不能误关校验）。"""
        from pilotstd.query.adapters._shared_ssl import default_ssl_context

        assert default_ssl_context().verify_mode == ssl.CERT_REQUIRED


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
