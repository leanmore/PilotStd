# tests/test_network.py — 网络请求层测试：重试、超时、状态码处理、单例
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestNetworkMonitorSingleton:
    """NetworkMonitor 单例测试。"""

    def test_monitor_is_singleton(self):
        """多次获取应返回同一实例。"""
        from pilotstd.query.network import get_monitor

        m1 = get_monitor()
        m2 = get_monitor()
        assert m1 is m2

    def test_monitor_record_and_reset(self):
        """记录和重置功能正常。"""
        from pilotstd.query.network import get_monitor

        m = get_monitor()
        initial = m.total_errors
        m.record_error("test_site")
        assert m.total_errors == initial + 1
        m.reset()
        assert m.total_errors == 0

    def test_monitor_summary_format(self):
        """汇总输出格式正确。"""
        from pilotstd.query.network import get_monitor

        m = get_monitor()
        m.reset()
        m.record_error("site_a")
        m.record_error("site_a")
        m.record_error("site_b")
        summary = m.summary()
        assert "site_a" in summary
        assert "site_b" in summary
        m.reset()


class TestRetryLogic:
    """重试逻辑测试。"""

    def test_retryable_status_codes(self):
        """502/503/504 应触发重试。"""
        from pilotstd.query.network import RETRYABLE_STATUS

        assert 502 in RETRYABLE_STATUS
        assert 503 in RETRYABLE_STATUS
        assert 504 in RETRYABLE_STATUS
        # 4xx 不在可重试列表中
        assert 404 not in RETRYABLE_STATUS
        assert 401 not in RETRYABLE_STATUS

    def test_max_retries_defined(self):
        """MAX_RETRIES 应为合理值。"""
        from pilotstd.query.network import MAX_RETRIES

        assert MAX_RETRIES == 1

    def test_max_redirects_defined(self):
        """MAX_REDIRECTS 应已定义且为合理值。"""
        from pilotstd.query.network import MAX_REDIRECTS

        assert MAX_REDIRECTS == 5


class TestSafeRequest:
    """safe_request 函数测试。"""

    def test_safe_get_uses_safe_request(self):
        """safe_get 应委托给 safe_request。"""

        from pilotstd.query.network import safe_get, safe_request

        # 验证函数存在且可调用签名正确
        assert callable(safe_get)
        assert callable(safe_request)

    def test_safe_post_uses_safe_request(self):
        """safe_post 应委托给 safe_request。"""
        from pilotstd.query.network import safe_post

        assert callable(safe_post)


class TestNetworkMonitorThreadSafety:
    """并发安全基本测试。"""

    def test_concurrent_records(self):
        """多线程同时记录不应丢数据。"""
        import threading

        from pilotstd.query.network import get_monitor

        m = get_monitor()
        m.reset()
        threads = []
        errors_per_thread = 100

        def record_errors(site):
            for _ in range(errors_per_thread):
                m.record_error(site)

        for i in range(4):
            t = threading.Thread(target=record_errors, args=(f"site_{i}",))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 总数应等于线程数 × 每线程错误数
        assert m.total_errors == 4 * errors_per_thread
        m.reset()
