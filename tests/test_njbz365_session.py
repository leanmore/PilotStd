"""Njz365SessionManager 单元测试 — 覆盖会话管理、签名计算、重试逻辑。"""

import hashlib
import unittest
from unittest.mock import patch

import requests
import responses

from pilotstd.query.adapters._njbz365_session_manager import (
    _PRIVATE_KEY,
    Njz365SessionManager,
)


class TestComputeSign(unittest.TestCase):
    """_compute_sign 静态方法测试。"""

    def test_basic_sign(self):
        params = {"api": "gbtitle_gl", "gjz": "test", "token": "jwt123"}
        result = Njz365SessionManager._compute_sign(params)
        self.assertIsInstance(result, str)
        self.assertEqual(len(result), 32)  # MD5 hex = 32 chars

    def test_empty_values_filtered(self):
        """空字符串和 None 值被过滤。"""
        params = {"api": "gbtitle_gl", "gjz": "", "token": None, "page": "1"}
        result = Njz365SessionManager._compute_sign(params)
        self.assertIsInstance(result, str)

    def test_json_data_key_excluded(self):
        """json_data key 被排除。"""
        params = {"api": "test", "json_data": "{}", "page": "1"}
        result = Njz365SessionManager._compute_sign(params)
        self.assertIsInstance(result, str)

    def test_keys_sorted(self):
        """key 按字母排序后拼接。"""
        params = {"z": "last", "a": "first", "m": "middle"}
        result = Njz365SessionManager._compute_sign(params)
        result2 = Njz365SessionManager._compute_sign({"a": "first", "m": "middle", "z": "last"})
        self.assertEqual(result, result2)

    def test_contains_private_key(self):
        """签名中包含私钥拼接。"""
        params = {"api": "gbtitle_gl", "gjz": "test"}
        # 手动计算预期签名
        raw = "api=gbtitle_gl&gjz=test&key=" + _PRIVATE_KEY
        expected = hashlib.md5(raw.encode()).hexdigest().upper()
        self.assertEqual(Njz365SessionManager._compute_sign(params), expected)


class TestBuildBaseParams(unittest.TestCase):
    """_build_base_params 测试。"""

    def setUp(self):
        self.session = Njz365SessionManager(requests.Session())

    def test_returns_dict_with_required_fields(self):
        self.session._jwt = "test_jwt"
        params = self.session._build_base_params("GB/T 1.1")
        self.assertIsInstance(params, dict)
        self.assertEqual(params["api"], "gbtitle_gl")
        self.assertEqual(params["gjz"], "GB/T 1.1")
        self.assertEqual(params["token"], "test_jwt")
        # time_str 应为数字字符串
        self.assertTrue(params["time_str"].isdigit())


class TestEnsureSession(unittest.TestCase):
    """_ensure_session 测试 — 使用 responses 模拟 HTTP。"""

    def setUp(self):
        self.session = Njz365SessionManager(requests.Session())

    @responses.activate
    def test_first_call_initializes(self):
        """首次调用：POST login_status_refresh 获取 token。"""
        responses.add(
            responses.POST,
            "https://www.njbz365.cn/apis/user_center/user/login_status_refresh",
            json={"code": "0", "msg": "刷新成功", "token": "jwt_test_123"},
            status=200,
        )

        self.session._ensure_session()

        self.assertTrue(self.session._initialized)
        self.assertEqual(self.session._jwt, "jwt_test_123")

    def test_already_initialized_skips(self):
        """已初始化时直接返回。"""
        self.session._initialized = True
        # 不应发起任何请求
        with patch.object(self.session, "_retry_request") as mock_retry:
            self.session._ensure_session()
            mock_retry.assert_not_called()

    @responses.activate
    def test_token_refresh_failure_handled(self):
        """login_status_refresh 返回非 0 code → 不崩溃，_jwt 为空。"""
        responses.add(
            responses.POST,
            "https://www.njbz365.cn/apis/user_center/user/login_status_refresh",
            json={"code": "1001", "msg": "登录状态异常"},
            status=200,
        )

        self.session._ensure_session()
        self.assertTrue(self.session._initialized)
        self.assertEqual(self.session._jwt, "")


class TestRefreshCsrf(unittest.TestCase):
    """_refresh_csrf 测试。"""

    def setUp(self):
        self.session = Njz365SessionManager(requests.Session())

    @responses.activate
    def test_successful_csrf_refresh(self):
        responses.add(
            responses.OPTIONS,
            "https://www.njbz365.cn/apis/std_base/web/jg_sel_standardcode",
            status=200,
            headers={"Set-Cookie": "csrf_token=new_csrf; session=new_sess"},
        )

        self.session._refresh_csrf()

        self.assertEqual(self.session._csrf_token, "new_csrf")
        self.assertEqual(self.session._session_val, "new_sess")

    @responses.activate
    @patch("time.sleep")
    def test_retry_on_failure(self, mock_sleep):
        """前两次失败，第三次成功。"""
        responses.add(
            responses.OPTIONS,
            "https://www.njbz365.cn/apis/std_base/web/jg_sel_standardcode",
            body=requests.ConnectionError("timeout"),
        )
        responses.add(
            responses.OPTIONS,
            "https://www.njbz365.cn/apis/std_base/web/jg_sel_standardcode",
            body=requests.ConnectionError("timeout"),
        )
        responses.add(
            responses.OPTIONS,
            "https://www.njbz365.cn/apis/std_base/web/jg_sel_standardcode",
            status=200,
            headers={"Set-Cookie": "csrf_token=final_csrf; session=final_sess"},
        )

        self.session._refresh_csrf()

        self.assertEqual(mock_sleep.call_count, 2)
        self.assertEqual(self.session._csrf_token, "final_csrf")

    @responses.activate
    @patch("time.sleep")
    def test_all_retries_fail(self, mock_sleep):
        """全部 3 次重试均失败 → 不抛异常。"""
        for _ in range(3):
            responses.add(
                responses.OPTIONS,
                "https://www.njbz365.cn/apis/std_base/web/jg_sel_standardcode",
                body=requests.ConnectionError("timeout"),
            )

        # 不应抛出异常
        self.session._refresh_csrf()
        self.assertEqual(self.session._csrf_token, "")


class TestRetryRequest(unittest.TestCase):
    """_retry_request 测试。"""

    def setUp(self):
        self.session = Njz365SessionManager(requests.Session())

    @responses.activate
    def test_successful_request(self):
        responses.add(responses.GET, "https://www.njbz365.cn/test", status=200, body="ok")

        resp = self.session._retry_request("get", "https://www.njbz365.cn/test")
        self.assertIsNotNone(resp)
        self.assertEqual(resp.status_code, 200)

    @responses.activate
    @patch("time.sleep")
    def test_retry_on_timeout(self, mock_sleep):
        """前两次超时，第三次成功。"""
        responses.add(
            responses.GET,
            "https://www.njbz365.cn/test",
            body=requests.Timeout("timeout"),
        )
        responses.add(
            responses.GET,
            "https://www.njbz365.cn/test",
            body=requests.Timeout("timeout"),
        )
        responses.add(responses.GET, "https://www.njbz365.cn/test", status=200, body="ok")

        resp = self.session._retry_request("get", "https://www.njbz365.cn/test")
        self.assertIsNotNone(resp)
        self.assertEqual(mock_sleep.call_count, 2)

    @responses.activate
    @patch("time.sleep")
    def test_all_retries_exhausted(self, mock_sleep):
        """全部重试失败 → 返回 None。"""
        for _ in range(3):
            responses.add(
                responses.GET,
                "https://www.njbz365.cn/test",
                body=requests.Timeout("timeout"),
            )

        resp = self.session._retry_request("get", "https://www.njbz365.cn/test")
        self.assertIsNone(resp)

    @responses.activate
    def test_request_exception_returns_none(self):
        """非网络异常（如 HTTPError）→ 返回 None。"""
        responses.add(responses.GET, "https://www.njbz365.cn/test", status=500)

        resp = self.session._retry_request("get", "https://www.njbz365.cn/test")
        self.assertIsNone(resp)


class TestDoRequest(unittest.TestCase):
    """_do_request 测试。"""

    def setUp(self):
        self.session = Njz365SessionManager(requests.Session())
        self.session._jwt = "test_jwt"
        self.session._csrf_token = "test_csrf"

    @responses.activate
    @patch.object(Njz365SessionManager, "_ensure_session")
    def test_successful_search(self, _mock_ensure):
        responses.add(
            responses.POST,
            "https://www.njbz365.cn/apis/std_base/web/jg_sel_standardcode",
            json={"code": "0", "data": [{"id": 1, "title": "标准1"}]},
            status=200,
        )

        result = self.session._do_request("GB/T 1.1")
        self.assertIsNotNone(result)
        self.assertEqual(result["code"], "0")

    @responses.activate
    @patch.object(Njz365SessionManager, "_ensure_session")
    @patch("time.sleep")
    def test_token_expired_refresh(self, mock_sleep, _mock_ensure):
        """token 过期 → 刷新 session 重试。"""
        # 第1次：token 过期
        responses.add(
            responses.POST,
            "https://www.njbz365.cn/apis/std_base/web/jg_sel_standardcode",
            json={"code": "1001", "msg": "token expired"},
            status=200,
        )
        # 第2次：成功
        responses.add(
            responses.POST,
            "https://www.njbz365.cn/apis/std_base/web/jg_sel_standardcode",
            json={"code": "0", "data": []},
            status=200,
        )

        result = self.session._do_request("GB/T 1.1")
        self.assertIsNotNone(result)
        self.assertEqual(result["code"], "0")
        self.assertFalse(self.session._initialized)

    @responses.activate
    @patch.object(Njz365SessionManager, "_ensure_session")
    @patch("time.sleep")
    def test_csrf_expired_refresh(self, mock_sleep, _mock_ensure):
        """1002 返回 → 按 token 刷新重试。"""
        responses.add(
            responses.POST,
            "https://www.njbz365.cn/apis/std_base/web/jg_sel_standardcode",
            json={"code": "1002", "msg": "csrf expired"},
            status=200,
        )
        responses.add(
            responses.POST,
            "https://www.njbz365.cn/apis/std_base/web/jg_sel_standardcode",
            json={"code": "0", "data": []},
            status=200,
        )

        result = self.session._do_request("test")
        self.assertIsNotNone(result)

    @responses.activate
    @patch.object(Njz365SessionManager, "_ensure_session")
    @patch("time.sleep")
    def test_timeout_retry_then_success(self, mock_sleep, _mock_ensure):
        """超时重试后成功。"""
        responses.add(
            responses.POST,
            "https://www.njbz365.cn/apis/std_base/web/jg_sel_standardcode",
            body=requests.Timeout("timeout"),
        )
        responses.add(
            responses.POST,
            "https://www.njbz365.cn/apis/std_base/web/jg_sel_standardcode",
            json={"code": "0", "data": []},
            status=200,
        )

        result = self.session._do_request("test")
        self.assertIsNotNone(result)

    @responses.activate
    @patch.object(Njz365SessionManager, "_ensure_session")
    @patch("time.sleep")
    def test_all_attempts_fail(self, mock_sleep, _mock_ensure):
        """全部 3 次尝试失败 → 返回 None。"""
        for _ in range(3):
            responses.add(
                responses.POST,
                "https://www.njbz365.cn/apis/std_base/web/jg_sel_standardcode",
                body=requests.Timeout("timeout"),
            )

        result = self.session._do_request("test")
        self.assertIsNone(result)

    @responses.activate
    @patch.object(Njz365SessionManager, "_ensure_session")
    def test_non_network_exception_returns_none(self, _mock_ensure):
        """非 Timeout/ConnectionError 的 RequestException → 返回 None。"""
        responses.add(
            responses.POST,
            "https://www.njbz365.cn/apis/std_base/web/jg_sel_standardcode",
            body=requests.HTTPError("HTTP error"),
        )

        result = self.session._do_request("test")
        self.assertIsNone(result)

    @responses.activate
    @patch.object(Njz365SessionManager, "_ensure_session")
    def test_unknown_error_code_returns_none(self, _mock_ensure):
        """未知错误 code（非 0/1001/1002/1003）→ 返回 None。"""
        responses.add(
            responses.POST,
            "https://www.njbz365.cn/apis/std_base/web/jg_sel_standardcode",
            json={"code": "9999", "msg": "未知错误"},
            status=200,
        )

        result = self.session._do_request("test")
        self.assertIsNone(result)

    @responses.activate
    @patch.object(Njz365SessionManager, "_ensure_session")
    def test_invalid_json_response_returns_none(self, _mock_ensure):
        """响应非 JSON → ValueError → 返回 None。"""
        responses.add(
            responses.POST,
            "https://www.njbz365.cn/apis/std_base/web/jg_sel_standardcode",
            body="Not JSON",
            status=200,
        )

        result = self.session._do_request("test")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
