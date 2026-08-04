# 模块：项目///_脚本
# 百度云文字识别提供商实现
"""百度云通用文字识别（标准版）— basicGeneral 接口收 PDF。"""

from __future__ import annotations

import base64
import logging
import time
from typing import Optional

from ._base import BaseOcrProvider, OcrResult

logger = logging.getLogger(__name__)


class BaiduOcrProvider(BaseOcrProvider):
    """百度云通用文字识别（标准版）— basicGeneral 接口收 PDF。"""

    def __init__(self, api_key: str, secret_key: str):
        self._api_key = api_key
        self._secret_key = secret_key
        # 令牌缓存：避免每次文字识别调用都重新获取_
        self._access_token: Optional[str] = None
        self._token_expire: float = 0

    @property
    def name(self) -> str:
        return "baidu"

    def _get_access_token(self) -> Optional[str]:
        """获取百度云 access_token，带缓存。"""
        from ...query.network import safe_raw_get

        # 缓存命中：未过期直接返回，提前1小时刷新留缓冲
        if self._access_token and time.time() < self._token_expire:
            return self._access_token
        resp = safe_raw_get(
            "https://aip.baidubce.com/oauth/2.0/token",
            "baidu_ocr",
            timeout=15,
            params={
                "grant_type": "client_credentials",
                "client_id": self._api_key,
                "client_secret": self._secret_key,
            },
        )
        if resp is None or resp.status_code != 200:
            logger.warning("百度云 access_token 获取失败")
            return None
        try:
            data = resp.json()
            self._access_token = data.get("access_token", "")
            expires = data.get("expires_in", 2592000)
            # 提前1小时过期，确保不会在请求中途失效
            self._token_expire = time.time() + expires - 3600
            return self._access_token
        except Exception:
            logger.warning("百度云 access_token 解析失败", exc_info=True)
            return None

    def recognize_pdf(self, pdf_bytes: bytes, page_num: int = 1) -> OcrResult:
        """识别 PDF 单页文本：获取 token → base64 编码 → basicGeneral 接口调用。"""
        from ...query.network import safe_raw_post

        token = self._get_access_token()
        if not token:
            return OcrResult(error="access_token 获取失败", error_type="other")
        try:
            # 接口：便携文档单页64编码+_中英混合识别
            resp = safe_raw_post(
                "https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic",
                "baidu_ocr",
                timeout=60,
                data={
                    "pdf_file": base64.b64encode(pdf_bytes).decode(),
                    "pdf_file_num": str(page_num),
                    "language_type": "CHN_ENG",
                },
                params={"access_token": token},
            )
            if resp is None:
                return OcrResult(error="请求超时", error_type="timeout")
            result = resp.json()
            if "error_code" in result:
                code = result["error_code"]
                # 将百度云错误码映射为通用错误类型，上层统一处理冷却策略
                return OcrResult(
                    error=f"code={code} msg={result.get('error_msg', '')}",
                    error_code=str(code),
                    error_type=_baidu_error_type(code),
                )
            words = result.get("words_result", [])
            text = "\n".join(w.get("words", "") for w in words)
            pdf_size = result.get("pdf_file_size", 0)
            return OcrResult(text=text, pdf_pages=int(pdf_size) if pdf_size else 0)
        except Exception:
            logger.warning("百度云 OCR 请求失败", exc_info=True)
            return OcrResult(error="请求异常", error_type="other")


def _baidu_error_type(code: int) -> str:
    """将百度云错误码映射为通用错误类型：18=QPS超限, 17=日限额, 19=月限额。"""
    if code == 18:
        return "qps"
    if code == 17:
        return "day"
    if code == 19:
        return "month"
    return "other"
