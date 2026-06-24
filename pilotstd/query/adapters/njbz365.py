# pilotstd/query/adapters/njbz365.py
# 南京标准公共服务平台查询适配器（njbz365.cn 新站，2026-05-25上线）

import base64
import hashlib
import logging
import re
import time
from typing import Any, Dict, Optional
from urllib.parse import unquote

import requests

from ..models import QueryResult
from ..network import safe_get
from ..search_strategy import match_result
from .base import BaseAdapter

logger = logging.getLogger(__name__)

# API 基地址（BFF 代理，同域）
BASE_API = "https://www.njbz365.cn/apis"
HOME_URL = "https://www.njbz365.cn/"

# Sign 算法签名私钥（反爬签名，非身份凭证）
_PRIVATE_KEY_B64 = "OlFnZH0rZFIyZmExRkZiV1tzQU8+LWQ6Si9QSEdxU1M="
_PRIVATE_KEY = base64.b64decode(_PRIVATE_KEY_B64).decode()


class Njbz365Adapter(BaseAdapter):
    """南京标准公共服务平台查询适配器。

    搜索流程：
    1. 访问首页获取访客 token cookie
    2. OPTIONS 请求获取 csrf_token
    3. 构造请求体 + 计算 sign
    4. POST jg_sel_standardcode 获取结果列表
    """

    supports_replaces_detail = True

    def __init__(self, session: requests.Session | None = None):
        self._session = session or requests.Session()
        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/133.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "zh-CN,zh;q=0.9",
            }
        )
        self._csrf_token = ""
        self._session_val = ""
        self._jwt = ""
        self._initialized = False

    @property
    def site_name(self) -> str:
        return "njbz365"

    @property
    def site_label(self) -> str:
        return "南京标准公共服务平台"

    def _ensure_session(self) -> None:
        """确保有有效的访客 session 和 JWT。"""
        if self._initialized:
            return

        # 第1步：访问首页获取 token cookie（最多重试 3 次，指数退避）
        if "token" not in self._session.cookies:
            self._retry_request("get", HOME_URL, timeout=30, err_msg="访问njbz365首页获取token")
            # 即使失败也继续——可能 cookie 中已有 token

        # 从 cookie 提取 JWT
        token_raw = unquote(self._session.cookies.get("token", "") or "")
        if token_raw:
            import json

            try:
                token_data = json.loads(token_raw)
                self._jwt = token_data.get("token", "")
            except (json.JSONDecodeError, KeyError):
                pass

        # 第2步：OPTIONS 请求获取 csrf_token 和 session
        if not self._csrf_token:
            self._refresh_csrf()

        self._initialized = True

    def _refresh_csrf(self) -> None:
        """通过 OPTIONS 请求获取 csrf_token，失败时重试 3 次。"""
        for attempt in range(3):
            try:
                resp = self._session.options(
                    f"{BASE_API}/std_base/web/jg_sel_standardcode",
                    timeout=15,
                )
                cookies = resp.headers.get("Set-Cookie", "")
                m = re.search(r"csrf_token=([^;]+)", cookies)
                if m:
                    self._csrf_token = m.group(1)
                m2 = re.search(r"session=([^;]+)", cookies)
                if m2:
                    self._session_val = m2.group(1)
                # 设置 cookie 以便后续请求自动携带
                if self._csrf_token:
                    self._session.cookies.set("csrf_token", self._csrf_token, domain=".njbz365.cn")
                if self._session_val:
                    self._session.cookies.set("session", self._session_val, domain=".njbz365.cn")
                return  # 成功则退出
            except requests.RequestException as e:
                if attempt < 2:
                    wait = 2**attempt
                    logger.warning(
                        "获取 csrf_token 失败（%d/3），%ds后重试: %s",
                        attempt + 1,
                        wait,
                        e,
                    )
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
        """发送 HTTP 请求（使用实例 session），网络超时/连接失败时指数退避重试。
        返回 Response 或 None（全部重试失败时）。
        """
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
                    logger.warning(
                        "%s失败（%d/%d），%ds后重试: %s",
                        err_msg,
                        attempt + 1,
                        max_retries,
                        wait,
                        e,
                    )
                    time.sleep(wait)
            except requests.RequestException as e:
                logger.error("%s请求异常: %s", err_msg, e)
                return None
        logger.error("%s最终失败（已重试%d次）: %s", err_msg, max_retries, last_exc)
        return None

    @staticmethod
    def _compute_sign(params: Dict[str, str]) -> str:
        """计算请求签名。

        1. 过滤空值
        2. key 字母排序
        3. 拼接 key=value&...&key=<privateKey>
        4. MD5 大写
        """
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
            # 空值字段（sign 计算时会被过滤，但需在请求体中）
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

        url = f"{BASE_API}/std_base/web/jg_sel_standardcode"
        headers = {
            "x-csrftoken": self._csrf_token,
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
                    logger.warning(
                        "njbz365 请求超时/连接失败（%d/3），%ds后重试: %s",
                        attempt + 1,
                        wait,
                        e,
                    )
                    time.sleep(wait)
                    continue
                logger.error("njbz365 请求最终失败: %s", e)
                return None
            except requests.RequestException as e:
                logger.error("njbz365 请求失败: %s", e)
                return None
            except ValueError:
                # njbz365 返回非 JSON（高峰期 unavailable 页面、验证码等）
                # 不返回 None——None 被上层当作"无匹配"而非"站点不可用"
                # 这里打日志后直接抛异常，让 query_batch 的 except 包装为带 error_message 的结果
                return None

            if data.get("code") == "0":
                return data  # type: ignore[no-any-return]  # API 响应无精确类型

            # token 过期 → 刷新 session 重试
            if data.get("code") == "1001" and attempt < 2:
                logger.info("njbz365 token 过期，刷新重试")
                self._initialized = False
                self._csrf_token = ""  # 同时重置 CSRF，可能也过期了
                self._ensure_session()
                headers["x-csrftoken"] = self._csrf_token
                continue

            # CSRF 过期重试
            if data.get("code") in ("1002", "1003") and attempt < 2:
                logger.info("njbz365 CSRF 过期，刷新重试")
                self._csrf_token = ""
                self._refresh_csrf()
                headers["x-csrftoken"] = self._csrf_token
                continue

            logger.warning(
                "njbz365 返回错误 code=%s: %s",
                data.get("code", "?"),
                data.get("msg", ""),
            )
            return None

        return None

    # 详情页 URL 模板
    DETAIL_URL = "https://www.njbz365.cn/details/{}"

    def _search(
        self,
        search_term: str,
        target_code: str = "",
        target_number: int = 0,
        target_year: int = 0,
    ) -> Optional[QueryResult]:
        """单结果兼容接口。target 为空时从 search_term 自动解析。"""
        if not target_code:
            parsed = _parse_result_number(search_term)
            target_code = parsed.get("code", "")
            target_number = parsed.get("number", 0)
            target_year = parsed.get("year", 0)
        candidates = self._search_candidates(search_term, target_code, target_number, target_year)
        return candidates[0] if candidates else None

    def _search_candidates(
        self,
        search_term: str,
        target_code: str = "",
        target_number: int = 0,
        target_year: int = 0,
    ) -> list[QueryResult]:
        """返回 API 全部候选结果（最多 limit 条），供 base 层统一打分。"""
        data = self._do_request(search_term)
        if data is None:
            return []

        items = data.get("data", {}).get("datalist", [])
        if not items:
            return []

        status_map = {"现行": "现行", "未生效": "即将实施", "废止": "废止"}
        results = []
        for item in items:
            bzbh = item.get("bzbh", "")
            bzmc = item.get("bzmc", "")
            bzzt = item.get("bzzt", "")
            bzid = item.get("bzid", "")
            cybz = item.get("cybz", "")
            is_adopted = bool(cybz)
            status = status_map.get(bzzt, bzzt)

            matched, match_status = match_result(target_code, target_number, target_year, bzmc, bzbh)

            results.append(
                QueryResult(
                    standard_number=bzbh,
                    standard_name=bzmc,
                    status=status,
                    match_status=match_status,
                    source_site=self.site_name,
                    hcno=bzid,
                    is_adopted=is_adopted,
                    is_downloadable=not is_adopted,
                    publish_date=item.get("fbrq", ""),
                    implementation_date=item.get("ssrq", ""),
                )
            )
        return results

    def _fetch_replaces(self, bzid: str, bzbh: str) -> str:
        """从详情页获取替代标准号。"""
        if not bzid:
            return ""
        try:
            url = self.DETAIL_URL.format(bzid)
            resp = safe_get(
                self._session,
                url,
                self.site_name,
                params={"bzbh": bzbh, "bzid": bzid},
                timeout=10,
            )
            if resp is None or resp.status_code != 200:
                return ""
            m = re.search(
                r"被如下标准代替：\s*([A-Z]+(?:/[A-Z]+)?\s*\d+(?:\.\d+)?\s*[—\-:]\s*\d{4})",
                resp.text,
            )
            if m:
                return m.group(1).strip()
        except Exception:
            logger.debug("njbz365 替代标准解析失败", exc_info=True)
        return ""

    def _post_process_result(self, result: QueryResult) -> None:
        """结果后处理：从详情页提取替代标准号。"""
        if result.hcno:
            result.replaces = self._fetch_replaces(result.hcno, result.standard_number)

    def fetch_replaces_detail(self, result: Any) -> str:
        """classifier 调用的统一接口：从查询结果提取替代关系。"""
        if hasattr(self, "_fetch_replaces") and result.hcno:
            return self._fetch_replaces(result.hcno, result.standard_number) or ""
        return ""


def _parse_result_number(standard_number: str) -> dict[str, Any]:
    """从标准编号字符串解析代号、顺序号、年份、部分号。委托公用解析器。"""
    from ...core.std_utils import parse_std_number

    r = parse_std_number(standard_number)
    return r if r else {"code": "", "number": 0, "part": None, "year": 0}
