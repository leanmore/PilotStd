# 模块：pilotstd/announcement/ocr/_aliyun.py
# 阿里云 OCR 提供商实现
"""阿里云 OCR 统一识别 — 支持 PDF 直接上传。

HMAC-SHA1 签名 + Base64，直接 HTTP 调用，无需 SDK。
文档: https://help.aliyun.com/zh/ocr/developer-reference/api-ocr-api-2021-07-07-recognizealltext
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
import urllib.parse
import uuid
from typing import Any

import requests

from ._base import BaseOcrProvider, OcrResult

logger = logging.getLogger(__name__)


class AliyunOcrProvider(BaseOcrProvider):
    """阿里云 OCR 统一识别 — 支持 PDF 直接上传。

    HMAC-SHA1 签名 + Base64，直接 HTTP 调用，无需 SDK。
    文档: https://help.aliyun.com/zh/ocr/developer-reference/api-ocr-api-2021-07-07-recognizealltext
    """

    _ENDPOINT = "ocr-api.cn-hangzhou.aliyuncs.com"
    _VERSION = "2021-07-07"

    def __init__(self, access_key_id: str, access_key_secret: str):
        self._ak_id = access_key_id
        self._ak_secret = access_key_secret

    @property
    def name(self) -> str:
        return "aliyun"

    def _sign_aliyun(self, params: dict[str, Any]) -> str:
        """阿里云 HMAC-SHA1 签名，返回 Signature 字符串。"""
        # 参数排序 + URL 编码
        sorted_keys = sorted(params.keys())
        canonical = "&".join(
            f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(str(params[k]), safe='')}" for k in sorted_keys
        )
        string_to_sign = "POST&%2F&" + urllib.parse.quote(canonical, safe="")
        key = self._ak_secret + "&"
        signature = hmac.new(key.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha1).digest()
        return base64.b64encode(signature).decode()

    def recognize_pdf(self, pdf_bytes: bytes, page_num: int = 1) -> OcrResult:
        """识别 PDF 单页文本：HMAC-SHA1 签名 → multipart 上传 → 解析响应。"""
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        nonce = str(uuid.uuid4())
        base64.b64encode(pdf_bytes).decode()

        params = {
            "AccessKeyId": self._ak_id,
            "Action": "RecognizeAllText",
            "Format": "JSON",
            "OutputStamp": "false",
            "PageNo": str(page_num),
            "SignatureMethod": "HMAC-SHA1",
            "SignatureNonce": nonce,
            "SignatureVersion": "1.0",
            "Timestamp": timestamp,
            "Type": "General",
            "Version": self._VERSION,
        }
        params["Signature"] = self._sign_aliyun(params)

        try:
            body_data = (
                b"--boundary\r\n"
                b'Content-Disposition: form-data; name="body"; filename="page.pdf"\r\n'
                b"Content-Type: application/pdf\r\n\r\n" + pdf_bytes + b"\r\n--boundary--"
            )
            query = urllib.parse.urlencode(params)
            resp = requests.post(
                f"https://{self._ENDPOINT}/?{query}",
                data=body_data,
                headers={
                    "Content-Type": "multipart/form-data; boundary=boundary",
                },
                timeout=60,
            )
            data = resp.json()
            code = data.get("Code", "0")
            if code != "0":
                return OcrResult(
                    error=f"code={code} msg={data.get('Message', '')}",
                    error_code=code,
                    error_type="qps" if code == "Throttling.User" else "other",
                )
            content = data.get("Data", {}).get("Content", "")
            return OcrResult(text=content)
        except Exception:
            logger.warning("阿里云 OCR 请求失败", exc_info=True)
            return OcrResult(error="请求异常", error_type="other")
