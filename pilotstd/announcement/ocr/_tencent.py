# 模块：项目///_脚本
# 腾讯云文字识别提供商实现
"""腾讯云通用文字识别 — 支持 PDF 直接上传。

TC3-HMAC-SHA256 签名，直接 HTTP 调用，无需 SDK。
文档: https://cloud.tencent.com/document/api/866/33518
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import hmac
import json
import logging
import time
from typing import Any

import requests

from ._base import BaseOcrProvider, OcrResult

logger = logging.getLogger(__name__)


class TencentOcrProvider(BaseOcrProvider):
    """腾讯云通用文字识别 — 支持 PDF 直接上传。

    TC3-HMAC-SHA256 签名，直接 HTTP 调用，无需 SDK。
    文档: https://cloud.tencent.com/document/api/866/33518
    """

    _SERVICE = "ocr"
    _HOST = "ocr.tencentcloudapi.com"
    _VERSION = "2018-11-19"
    _ACTION = "GeneralBasicOCR"

    def __init__(self, secret_id: str, secret_key: str):
        self._secret_id = secret_id
        self._secret_key = secret_key

    @property
    def name(self) -> str:
        return "tencent"

    def _sign_tc3(self, payload: str, timestamp: int) -> dict[str, Any]:
        """TC3-HMAC-SHA256 签名，返回请求头。"""
        date = datetime.datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d")
        algorithm = "TC3-HMAC-SHA256"
        ct = "application/json; charset=utf-8"

        # 步骤1: 规范请求
        http_request_method = "POST"
        canonical_uri = "/"
        canonical_querystring = ""
        canonical_headers = f"content-type:{ct}\nhost:{self._HOST}\nx-tc-action:{self._ACTION.lower()}\n"
        signed_headers = "content-type;host;x-tc-action"
        hashed_request_payload = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        canonical_request = (
            f"{http_request_method}\n{canonical_uri}\n"
            f"{canonical_querystring}\n{canonical_headers}\n"
            f"{signed_headers}\n{hashed_request_payload}"
        )

        # 步骤2: 待签字符串
        credential_scope = f"{date}/{self._SERVICE}/tc3_request"
        hashed_canonical_request = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
        string_to_sign = f"{algorithm}\n{timestamp}\n{credential_scope}\n{hashed_canonical_request}"

        # 步骤3: 签名
        def _sign(key: bytes, msg: str) -> bytes:
            return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

        secret_date = _sign(("TC3" + self._secret_key).encode("utf-8"), date)
        secret_service = _sign(secret_date, self._SERVICE)
        secret_signing = _sign(secret_service, "tc3_request")
        signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

        # 步骤4:头
        authorization = (
            f"{algorithm} Credential={self._secret_id}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )
        return {
            "Authorization": authorization,
            "Content-Type": ct,
            "Host": self._HOST,
            "X-TC-Action": self._ACTION,
            "X-TC-Version": self._VERSION,
            "X-TC-Timestamp": str(timestamp),
            "X-TC-Region": "ap-guangzhou",
        }

    def recognize_pdf(self, pdf_bytes: bytes, page_num: int = 1) -> OcrResult:
        """识别 PDF 单页文本：TC3-HMAC-SHA256 签名 → JSON POST → 解析响应。"""
        b64 = base64.b64encode(pdf_bytes).decode()
        timestamp = int(time.time())
        payload = json.dumps(
            {
                "ImageBase64": b64,
                "IsPdf": True,
                "PdfPageNumber": page_num,
                "LanguageType": "zh",
            }
        )
        headers = self._sign_tc3(payload, timestamp)
        try:
            resp = requests.post(
                f"https://{self._HOST}",
                data=payload.encode("utf-8"),
                headers=headers,
                timeout=60,
            )
            data = resp.json()
            if "Response" in data and "Error" in data["Response"]:
                err = data["Response"]["Error"]
                code = err.get("Code", "")
                return OcrResult(
                    error=f"{code}: {err.get('Message', '')}",
                    error_code=code,
                    error_type=_tencent_error_type(code),
                )
            resp_data = data.get("Response", {})
            detections = resp_data.get("TextDetections", [])
            text = "\n".join(d.get("DetectedText", "") for d in detections)
            pdf_size = resp_data.get("PdfPageSize", 0)
            return OcrResult(text=text, pdf_pages=pdf_size)
        except Exception:
            logger.warning("腾讯云 OCR 请求失败", exc_info=True)
            return OcrResult(error="请求异常", error_type="other")


def _tencent_error_type(code: str) -> str:
    """将腾讯云错误码映射为通用错误类型：RequestLimitExceeded=QPS超限, NoFreeAmount=月限额。"""
    if code == "RequestLimitExceeded":
        return "qps"
    if code == "FailedOperation.NoFreeAmount":
        return "month"
    return "other"
