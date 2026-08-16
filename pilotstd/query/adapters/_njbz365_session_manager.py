# 模块：项目/查询/适配器/_365__管理器脚本
# 365会话管理与请求签名—原_365，现为独立类
# 分隔
# 会话管理流程（3 步）：
# 1.首页→获取+令牌
# 2.输入输出→获取_+
# 3.搜索→带签名（/过期时自动刷新）
# 分隔
# 签名算法：过滤空值→排序→拼接→拼接私钥→5大写
# 重试策略：指数退避（2^秒），最多3次

import base64
import hashlib
import logging
import re
import time
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)

def _get_base_api() -> str:
    """从配置中心读取 njbz365 查询端点，未配置时回退硬编码默认值。"""
    from ..site_config import get_site_config

    config = get_site_config("njbz365")
    if config and config.search_url:
        return config.search_url
    return "https://www.njbz365.cn/apis"


HOME_URL = "https://www.njbz365.cn/"

# 算法签名私钥
_PRIVATE_KEY_B64 = "OlFnZH0rZFIyZmExRkZiV1tzQU8+LWQ6Si9QSEdxU1M="
_PRIVATE_KEY = base64.b64decode(_PRIVATE_KEY_B64).decode()


class Njz365SessionManager:
    """njbz365 会话管理、CSRF 刷新、请求签名与重试逻辑。

    原 _Njbz365SessionMixin，现为独立类（组合注入到 Njbz365Adapter）。
    """

    def __init__(self, session: requests.Session):
        self._session = session
        self._initialized = False
        self._jwt = ""
        self._csrf_token = ""
        self._session_val = ""

    def _ensure_session(self, force_refresh: bool = False) -> None:
        """确保有有效的访客 JWT。force_refresh 时强制重新获取。"""
        if self._initialized:
            return

        if force_refresh or not self._jwt:
            self._refresh_token()

        self._initialized = True

    def _refresh_token(self) -> None:
        """通过 login_status_refresh 接口获取访客 JWT token。

        旧机制（已失效）：GET 首页 → Set-Cookie 的 token 字段包含 JWT。
        新机制：POST login_status_refresh → 响应 JSON 的 "token" 字段包含 JWT。
        """
        url = f"{_get_base_api()}/user_center/user/login_status_refresh"
        params = {
            "org_id": "", "api": "gbtitle_gl", "time_str": str(int(time.time() * 1000)),
            "fws_source": "nj_std", "check_login_device": "", "c_s": "pc",
            "is_web": "1", "source": "gbtitle_gl", "token2": "", "_router_": "website/index", "token": "",
        }
        params["sign"] = self._compute_sign(params)
        try:
            resp = self._session.post(url, json=params, timeout=30)
            data = resp.json()
            if data.get("code") == "0":
                self._jwt = data.get("token", "")
            else:
                logger.warning("njbz365 token 获取失败: code=%s msg=%s", data.get("code"), data.get("msg"))
        except (requests.RequestException, ValueError) as e:
            logger.error("njbz365 token 获取异常: %s", e)

    def _refresh_csrf(self) -> None:
        """通过 OPTIONS 请求获取 csrf_token，失败时重试 3 次。"""
        for attempt in range(3):
            try:
                resp = self._session.options(
                    f"{_get_base_api()}/std_base/web/jg_sel_standardcode",
                    timeout=15,
                )
                cookies = resp.headers.get("Set-Cookie", "")
                m = re.search(r"csrf_token=([^;]+)", cookies)
                if m:
                    self._csrf_token = m.group(1)
                m2 = re.search(r"session=([^;]+)", cookies)
                if m2:
                    self._session_val = m2.group(1)
                if self._csrf_token:
                    self._session.cookies.set("csrf_token", self._csrf_token, domain=".njbz365.cn")
                if self._session_val:
                    self._session.cookies.set("session", self._session_val, domain=".njbz365.cn")
                return
            except requests.RequestException as e:
                if attempt < 2:
                    wait = 2**attempt
                    logger.warning("获取 csrf_token 失败（%d/3），%ds后重试: %s", attempt + 1, wait, e)
                    time.sleep(wait)
                else:
                    logger.warning("获取 csrf_token 最终失败: %s", e)

    def _retry_request(
        self,
        method: str,
        url: str,
        max_retries: int = 3,
        timeout: int = 30,
        err_msg: str = "",
        **kwargs: Any,
    ) -> Optional[requests.Response]:
        """发送 HTTP 请求（使用实例 session），网络超时/连接失败时指数退避重试。"""
        last_exc = None
        for attempt in range(max_retries):
            try:
                resp = self._session.request(method, url, timeout=timeout, **kwargs)
                resp.raise_for_status()
                return resp
            except (requests.Timeout, requests.ConnectionError) as e:
                last_exc = e
                if attempt < max_retries - 1:
                    wait = 2**attempt
                    logger.warning("%s失败（%d/%d），%ds后重试: %s", err_msg, attempt + 1, max_retries, wait, e)
                    time.sleep(wait)
            except requests.RequestException as e:
                logger.error("%s请求异常: %s", err_msg, e)
                return None
        logger.error("%s最终失败（已重试%d次）: %s", err_msg, max_retries, last_exc)
        return None

    @staticmethod
    def _compute_sign(params: Dict[str, str]) -> str:
        """计算请求签名：过滤空值 → key 排序 → 拼接 → MD5 大写。"""
        non_empty = {k: v for k, v in params.items() if v != "" and v is not None and k != "json_data"}
        sorted_keys = sorted(non_empty.keys())
        raw = "&".join(f"{k}={non_empty[k]}" for k in sorted_keys)
        raw += "&key=" + _PRIVATE_KEY
        return hashlib.md5(raw.encode()).hexdigest().upper()

    def _build_base_params(self, keyword: str) -> Dict[str, str]:
        """构造基础请求参数（含所有必需的空值字段）。"""
        return {
            "api": "gbtitle_gl",
            "time_str": str(int(time.time() * 1000)),
            "token": self._jwt,
            "gjz": keyword,
            "bzzt": "现行,未生效,废止",
            "fllb_new": "G,C,T,D,N",
            "check_web": "T",
            "is_web": "1",
            "c_s": "pc",
            "source": "gbtitle_gl",
            "fws_source": "nj_std",
            "isNew": "T",
            "reqType": "1",
            "sort_type": "0",
            "key_word_choose": "9",
            "medkey_word_choose": "3,4,6",
            "is_hot": "F",
            "gjz_whole": "F",
            "gjz_list": "[]",
            "_router_": "website/standard",
            "page": "1",
            "limit": "10",
            "org_id": "",
            "check_login_device": "",
            "ptly": "",
            "org_gid": "",
            "user_type": "",
            "fllb": "",
            "code_kind": "",
            "has_pdf": "",
            "is_atlas": "",
            "is_czb": "",
            "dw_gk": "",
            "cyfl": "",
            "pdf_content": "",
            "bzxh": "",
            "bzmc": "",
            "enmc": "",
            "sxq_zbfl": "",
            "sxq_ics": "",
            "sxq_dw_gk": "",
            "sxq_fllb": "",
            "sxq_bzzz": "",
            "is_ewm": "",
            "is_chapter": "",
            "hylb_new": "",
            "ndh": "",
            "bzzz": "",
            "zbfl": "",
            "ics": "",
            "qcr": "",
            "dw_qc": "",
            "origin": "",
            "and_gjz_list": "",
            "fbrq_jsrq": "",
            "fbrq_ksrq": "",
            "ssrq_ksrq": "",
            "ssrq_jsrq": "",
            "fzrq_ksrq": "",
            "fzrq_jsrq": "",
            "result_gjz": "",
        }

    def _do_request(self, search_term: str) -> Optional[dict[str, Any]]:
        """发起搜索请求，token/CSRF 过期时自动刷新并重试。"""
        self._ensure_session()

        url = f"{_get_base_api()}/std_base/web/jg_sel_standardcode"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "Referer": f"https://www.njbz365.cn/standard?gjz={search_term}",
            "Origin": "https://www.njbz365.cn",
        }

        for attempt in range(3):
            params = self._build_base_params(search_term)
            params["sign"] = self._compute_sign(params)

            try:
                resp = self._session.post(url, json=params, headers=headers, timeout=30)
                data = resp.json()
            except (requests.Timeout, requests.ConnectionError) as e:
                if attempt < 2:
                    wait = 2**attempt
                    logger.warning("njbz365 请求超时/连接失败（%d/3），%ds后重试: %s", attempt + 1, wait, e)
                    time.sleep(wait)
                    continue
                logger.error("njbz365 请求最终失败: %s", e)
                return None
            except requests.RequestException as e:
                logger.error("njbz365 请求失败: %s", e)
                return None
            except ValueError:
                return None

            if data.get("code") == "0":
                return data

            if data.get("code") == "1001" and attempt < 2:
                logger.info("njbz365 token 过期，刷新重试")
                self._initialized = False
                self._ensure_session(force_refresh=True)
                continue

            if data.get("code") in ("1002", "1003") and attempt < 2:
                logger.info("njbz365 返回 %s，按 token 刷新重试", data.get("code"))
                self._initialized = False
                self._ensure_session(force_refresh=True)
                continue

            logger.warning("njbz365 返回错误 code=%s: %s", data.get("code", "?"), data.get("msg", ""))
            return None

        return None


# 保留旧模块_合并请求_导出兼容
_PRIVATE_KEY = _PRIVATE_KEY
