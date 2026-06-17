# pilotstd/announcement/ocr.py
# OCR 提供商抽象层 — PDF 直接上传，支持百度云/腾讯云/阿里云
"""公告 PDF OCR 识别。默认百度云 basicGeneralPdf 接口，用户可配腾讯云/阿里云。

各平台均直接接收 PDF 文件（base64 编码后 ≤4~10MB），无需 PDF→图片转换。
百度云通用文字识别标准版每月免费 1000 次，月均用量 ~50 次，不花钱。
"""

from __future__ import annotations

import base64
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class OcrResult:
    """OCR 调用结果。ok=True 则 text 有效；ok=False 则 error/error_type 有效。"""
    text: str | None = None
    error: str | None = None
    error_code: str | None = None       # 原始错误码（"18"/"RequestLimitExceeded"等）
    error_type: str | None = None       # "qps"/"month"/"day"/"timeout"/"other"
    pdf_pages: int = 0                  # API 返回的总页数（交叉验证用）

    @property
    def ok(self) -> bool:
        return self.text is not None


class BaseOcrProvider(ABC):
    """OCR 提供商基类。用户可通过 ConfigManager 配置切换。"""

    @abstractmethod
    def recognize_pdf(self, pdf_bytes: bytes, page_num: int = 1) -> OcrResult:
        """识别 PDF 单页文本。返回 OcrResult。"""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """提供商标识名，用于日志和配置。"""
        ...


class BaiduOcrProvider(BaseOcrProvider):
    """百度云通用文字识别（标准版）— basicGeneral 接口收 PDF。"""

    def __init__(self, api_key: str, secret_key: str):
        self._api_key = api_key
        self._secret_key = secret_key
        self._access_token: Optional[str] = None
        self._token_expire: float = 0

    @property
    def name(self) -> str:
        return "baidu"

    def _get_access_token(self) -> Optional[str]:
        """获取百度云 access_token，带缓存。"""
        from ..query.network import safe_raw_get
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
            })
        if resp is None or resp.status_code != 200:
            logger.warning("百度云 access_token 获取失败")
            return None
        try:
            data = resp.json()
            self._access_token = data.get("access_token", "")
            expires = data.get("expires_in", 2592000)
            self._token_expire = time.time() + expires - 3600
            return self._access_token
        except Exception:
            logger.warning("百度云 access_token 解析失败", exc_info=True)
            return None

    def recognize_pdf(self, pdf_bytes: bytes, page_num: int = 1) -> OcrResult:
        from ..query.network import safe_raw_post
        token = self._get_access_token()
        if not token:
            return OcrResult(error="access_token 获取失败", error_type="other")
        try:
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
    if code == 18: return "qps"
    if code == 17: return "day"
    if code == 19: return "month"
    return "other"


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

    def _sign_tc3(self, payload: str, timestamp: int) -> dict:
        """TC3-HMAC-SHA256 签名，返回请求头。"""
        import hashlib, hmac, datetime

        date = datetime.datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d")
        algorithm = "TC3-HMAC-SHA256"
        ct = "application/json; charset=utf-8"

        # 步骤1: 规范请求
        http_request_method = "POST"
        canonical_uri = "/"
        canonical_querystring = ""
        canonical_headers = (
            f"content-type:{ct}\nhost:{self._HOST}\nx-tc-action:{self._ACTION.lower()}\n"
        )
        signed_headers = "content-type;host;x-tc-action"
        hashed_request_payload = hashlib.sha256(
            payload.encode("utf-8")).hexdigest()
        canonical_request = (
            f"{http_request_method}\n{canonical_uri}\n"
            f"{canonical_querystring}\n{canonical_headers}\n"
            f"{signed_headers}\n{hashed_request_payload}"
        )

        # 步骤2: 待签字符串
        credential_scope = f"{date}/{self._SERVICE}/tc3_request"
        hashed_canonical_request = hashlib.sha256(
            canonical_request.encode("utf-8")).hexdigest()
        string_to_sign = (
            f"{algorithm}\n{timestamp}\n{credential_scope}\n"
            f"{hashed_canonical_request}"
        )

        # 步骤3: 签名
        def _sign(key, msg):
            return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

        secret_date = _sign(("TC3" + self._secret_key).encode("utf-8"), date)
        secret_service = _sign(secret_date, self._SERVICE)
        secret_signing = _sign(secret_service, "tc3_request")
        signature = hmac.new(
            secret_signing, string_to_sign.encode("utf-8"),
            hashlib.sha256).hexdigest()

        # 步骤4: Authorization 头
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
        import requests, json

        b64 = base64.b64encode(pdf_bytes).decode()
        timestamp = int(time.time())
        payload = json.dumps({
            "ImageBase64": b64,
            "IsPdf": True,
            "PdfPageNumber": page_num,
            "LanguageType": "zh",
        })
        headers = self._sign_tc3(payload, timestamp)
        try:
            resp = requests.post(
                f"https://{self._HOST}", data=payload.encode("utf-8"),
                headers=headers, timeout=60,
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
    if code == "RequestLimitExceeded": return "qps"
    if code == "FailedOperation.NoFreeAmount": return "month"
    return "other"


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

    def _sign_aliyun(self, params: dict) -> str:
        """阿里云 HMAC-SHA1 签名，返回 Signature 字符串。"""
        import hmac, hashlib, urllib.parse

        # 参数排序 + URL 编码
        sorted_keys = sorted(params.keys())
        canonical = "&".join(
            f"{urllib.parse.quote(k, safe='')}="
            f"{urllib.parse.quote(str(params[k]), safe='')}"
            for k in sorted_keys
        )
        string_to_sign = "POST&%2F&" + urllib.parse.quote(canonical, safe='')
        key = self._ak_secret + "&"
        signature = hmac.new(
            key.encode("utf-8"), string_to_sign.encode("utf-8"),
            hashlib.sha1).digest()
        return base64.b64encode(signature).decode()

    def recognize_pdf(self, pdf_bytes: bytes, page_num: int = 1) -> OcrResult:
        import requests, json, uuid, hashlib, urllib.parse

        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        nonce = str(uuid.uuid4())
        b64 = base64.b64encode(pdf_bytes).decode()

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
                b"Content-Disposition: form-data; name=\"body\"; filename=\"page.pdf\"\r\n"
                b"Content-Type: application/pdf\r\n\r\n"
                + pdf_bytes +
                b"\r\n--boundary--"
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


# ── 月度调用计数器 ──────────────────────────────────────────────

import json as _json
import os as _os
import threading as _threading
from datetime import datetime as _datetime


class OcrCounters:
    """月度调用计数器，线程安全，每次+1后立即落盘。"""

    _LIMITS = {"baidu": 800, "tencent": 800, "aliyun": 150}

    def __init__(self, path: str):
        self._path = path
        self._lock = _threading.Lock()
        self._data = self._load()

    def _load(self) -> dict:
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = _json.load(f)
        except (FileNotFoundError, _json.JSONDecodeError):
            data = {"month": "", "baidu": 0, "tencent": 0, "aliyun": 0}
        current = _datetime.now().strftime("%Y-%m")
        if data.get("month") != current:
            data = {"month": current, "baidu": 0, "tencent": 0, "aliyun": 0}
        return data

    def _save(self):
        _os.makedirs(_os.path.dirname(self._path), exist_ok=True)
        tmp = self._path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            _json.dump(self._data, f, ensure_ascii=False)
        _os.replace(tmp, self._path)

    def can_accept(self, provider: str, pages: int) -> bool:
        with self._lock:
            return self._data[provider] + pages <= self._LIMITS[provider]

    def remaining(self, provider: str) -> int:
        with self._lock:
            return max(0, self._LIMITS[provider] - self._data[provider])

    def increment(self, provider: str):
        with self._lock:
            self._data[provider] += 1
            self._save()

    def get(self, provider: str) -> int:
        with self._lock:
            return self._data[provider]

    @property
    def month(self) -> str:
        with self._lock:
            return self._data["month"]


# ── 冷却管理 ──────────────────────────────────────────────────────

import time as _time


class ProviderCooling:
    """Provider 冷却状态管理，线程安全。"""

    def __init__(self):
        self._lock = _threading.Lock()
        self._until: dict[str, float] = {}

    def is_hot(self, name: str) -> bool:
        with self._lock:
            return _time.time() >= self._until.get(name, 0)

    def set(self, name: str, level: str):
        now = _datetime.now()
        if level == "qps":
            until = _time.time() + 300
        elif level == "day":
            until = (now.replace(hour=0, minute=0, second=0, microsecond=0)
                     + _datetime.timedelta(days=1)).timestamp()
        elif level == "month":
            if now.month == 12:
                nxt = now.replace(year=now.year + 1, month=1, day=1)
            else:
                nxt = now.replace(month=now.month + 1, day=1)
            until = nxt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        else:
            until = 0
        with self._lock:
            self._until[name] = until
        logger.warning("[OCR] %s 进入冷却: level=%s until=%.0f", name, level, until)

    def remaining(self, name: str) -> float:
        with self._lock:
            return max(0, self._until.get(name, 0) - _time.time())


# ── PDF 拆页工具 ──────────────────────────────────────────────────


def _split_pdf_pages(pdf_bytes: bytes) -> list[bytes]:
    """PyPDF2 拆 PDF 为单页 bytes 列表。失败降级为 [pdf_bytes]。"""
    try:
        from io import BytesIO
        from PyPDF2 import PdfReader, PdfWriter
        reader = PdfReader(BytesIO(pdf_bytes))
        total = len(reader.pages)
        if total <= 1:
            return [pdf_bytes]
        pages = []
        for i in range(total):
            writer = PdfWriter()
            writer.add_page(reader.pages[i])
            buf = BytesIO()
            writer.write(buf)
            pages.append(buf.getvalue())
        return pages
    except Exception:
        logger.warning("PyPDF2 拆页失败，降级为整文件处理")
        return [pdf_bytes]


def _pdf_page_count(pdf_bytes: bytes) -> int:
    """返回 PDF 总页数。失败返回 1。"""
    try:
        from io import BytesIO
        from PyPDF2 import PdfReader
        return len(PdfReader(BytesIO(pdf_bytes)).pages)
    except Exception:
        return 1


# ── 线程优先级 ──────────────────────────────────────────────────────


def _set_thread_priority_idle():
    """Windows: 当前线程设为 THREAD_PRIORITY_IDLE(-15)。非 Windows 静默跳过。"""
    try:
        import ctypes
        handle = ctypes.windll.kernel32.GetCurrentThread()
        ctypes.windll.kernel32.SetThreadPriority(handle, -15)
    except Exception:
        pass


# ── OcrSlot 单槽位 ────────────────────────────────────────────────


class OcrSlot:
    """单个 OCR 槽位——绑定一个 provider，按 QPS 逐页发送附件。"""

    _SIZE_LIMITS = {"baidu": 2.5 * 1024 * 1024, "tencent": 5 * 1024 * 1024,
                    "aliyun": 8 * 1024 * 1024}

    def __init__(self, name: str, provider: BaseOcrProvider, qps: int,
                 counters: OcrCounters, cooling: ProviderCooling):
        self.name = name
        self.provider = provider
        self._counters = counters
        self._cooling = cooling
        self._interval = 1.0 / qps if qps > 0 else 0.1

    def is_available(self, total_pages: int) -> bool:
        if self.provider is None:
            return False
        if not self._cooling.is_hot(self.name):
            return False
        if not self._counters.can_accept(self.name, total_pages):
            logger.warning("[OCR] %s 计数超限: %d/%d 需%d页",
                          self.name, self._counters.get(self.name),
                          self._counters.remaining(self.name), total_pages)
            return False
        return True

    def process(self, pages: list[bytes], label: str,
                emergency: "OcrSlot | None",
                stop_event: _threading.Event) -> list[str]:
        """处理附件页列表。返回提取的文本列表。失败时回退到 emergency。"""
        results = []
        total = len(pages)
        for i, page in enumerate(pages):
            if stop_event.is_set():
                logger.info("[OCR] %s 收到停止信号，已完成 %d/%d 页", self.name, i, total)
                break
            time.sleep(self._interval)
            result = self.provider.recognize_pdf(page, page_num=1)
            if result.ok:
                results.append(result.text)
                self._counters.increment(self.name)
                logger.info("[OCR] %s %s 页%d/%d OK", self.name, label, i + 1, total)
                if i == 0 and result.pdf_pages > 0 and result.pdf_pages != total:
                    logger.warning("[OCR] %s API返回页数=%d ≠ PyPDF2=%d，以PyPDF2为准",
                                 self.name, result.pdf_pages, total)
            else:
                err_type = result.error_type or "other"
                if err_type in ("qps", "month", "day"):
                    self._cooling.set(self.name, err_type)
                logger.warning("[OCR] %s %s 页%d/%d 错误(%s) → 剩余%d页",
                             self.name, label, i + 1, total,
                             result.error_code or err_type, total - i - 1)
                if emergency and (i + 1) < total:
                    remaining = pages[i + 1:]
                    return emergency._finish_remaining(remaining, label,
                                                       stop_event, results)
                break
        logger.info("[OCR] %s %s 完成 (%d/%d页)", self.name, label, len(results), total)
        return results

    def _finish_remaining(self, pages: list[bytes], label: str,
                          stop_event: _threading.Event,
                          existing: list[str]) -> list[str]:
        """应急接管剩余页。"""
        logger.warning("[OCR] %s 应急接管 %s 页%d-%d",
                     self.name, label,
                     len(existing) + 1, len(existing) + len(pages))
        for i, page in enumerate(pages):
            if stop_event.is_set():
                break
            time.sleep(self._interval)
            result = self.provider.recognize_pdf(page, page_num=1)
            if result.ok:
                existing.append(result.text)
                self._counters.increment(self.name)
            else:
                logger.error("[OCR] %s 应急也失败: %s", self.name, result.error)
                break
        return existing

    def check_page_size(self, size: int) -> bool:
        return size <= self._SIZE_LIMITS.get(self.name, 10 * 1024 * 1024)


# ── OcrScheduler 双槽调度器 ────────────────────────────────────────


class OcrScheduler(BaseOcrProvider):
    """双槽并行 OCR 调度器。"""

    def __init__(self, baidu_slot: OcrSlot | None, tencent_slot: OcrSlot | None,
                 aliyun_slot: OcrSlot | None, stop_event: _threading.Event,
                 counters: OcrCounters, cooling: ProviderCooling):
        self._slots = [s for s in (baidu_slot, tencent_slot) if s is not None]
        self._alibaba = aliyun_slot
        self._stop = stop_event
        self._counters = counters
        self._cooling = cooling
        self._active_lock = _threading.Condition()
        self._active = 0
        _set_thread_priority_idle()

    @property
    def name(self) -> str:
        return "scheduler"

    def recognize_pdf(self, pdf_bytes: bytes, page_num: int = 1) -> Optional[str]:
        """外部入口——入槽 + 阻塞等待完成。兼容 BaseOcrProvider 接口。"""
        pages = _split_pdf_pages(pdf_bytes)
        total = len(pages)
        label = f"附件-{id(pdf_bytes):x}"

        # 等待槽位
        with self._active_lock:
            while self._active >= len(self._slots) and not self._stop.is_set():
                self._active_lock.wait(timeout=1)
            if self._stop.is_set():
                return None
            self._active += 1

        slot = self._pick_slot(total)
        if slot is None:
            with self._active_lock:
                self._active -= 1
                self._active_lock.notify_all()
            logger.error("[OCR] %s 无可用槽位", label)
            return None

        logger.info("[OCR] %s槽 ← %s (%d页)", slot.name, label, total)
        try:
            results = slot.process(pages, label, emergency=self._alibaba,
                                  stop_event=self._stop)
            return "\n".join(results) if results else None
        finally:
            with self._active_lock:
                self._active -= 1
                self._active_lock.notify_all()

    def _pick_slot(self, total_pages: int) -> Optional[OcrSlot]:
        """选可用槽位——优先已用次数少的。"""
        available = [s for s in self._slots if s.is_available(total_pages)]
        if not available:
            return None
        available.sort(key=lambda s: self._counters.get(s.name))
        return available[0]


# ── create_ocr_provider ───────────────────────────────────────────

def create_ocr_provider(config: dict, data_dir: str = "") -> Optional[BaseOcrProvider]:
    """创建 OCR 调度器（多 provider 共存）或单个 provider（旧模式兼容）。

    新键（推荐）：
      baidu_api_key / baidu_secret_key
      tencent_secret_id / tencent_secret_key
      aliyun_access_key_id / aliyun_access_key_secret
    旧键（兼容，单 provider 模式）：
      api_key / secret_key / secret_id / access_key_id / access_key_secret
    """
    # 旧模式兼容：显式指定 provider 时走单 provider 路径
    explicit = config.get("provider", "")
    if explicit in ("baidu", "tencent", "aliyun"):
        if explicit == "baidu":
            return _create_baidu(config)
        elif explicit == "tencent":
            return _create_tencent(config)
        else:
            return _create_aliyun(config)

    # 新模式：创建全部有凭据的 provider，返回调度器
    import os as _os
    if not data_dir:
        from ..core.config import get_data_dir
        data_dir = get_data_dir()
    counter_path = _os.path.join(data_dir, "ocr_counters.json")
    counters = OcrCounters(counter_path)
    cooling = ProviderCooling()

    baidu = _create_baidu(config)
    tencent = _create_tencent(config)
    aliyun = _create_aliyun(config)

    stop = _threading.Event()
    baidu_slot = OcrSlot("baidu", baidu, 2, counters, cooling) if baidu else None
    tencent_slot = OcrSlot("tencent", tencent, 10, counters, cooling) if tencent else None
    aliyun_slot = OcrSlot("aliyun", aliyun, 10, counters, cooling) if aliyun else None

    if not baidu_slot and not tencent_slot:
        if aliyun_slot:
            logger.warning("仅阿里云可用，百度云和腾讯云均未配置")
            return aliyun_slot
        logger.warning("无可用 OCR provider")
        return None
    return OcrScheduler(baidu_slot, tencent_slot, aliyun_slot, stop, counters, cooling)


def _create_baidu(config: dict) -> Optional["BaiduOcrProvider"]:
    api_key = config.get("baidu_api_key", "") or config.get("api_key", "")
    secret_key = config.get("baidu_secret_key", "") or config.get("secret_key", "")
    if not api_key or not secret_key:
        logger.warning("百度云 OCR 未配置 api_key/secret_key，跳过")
        return None
    return BaiduOcrProvider(api_key=api_key, secret_key=secret_key)


def _create_tencent(config: dict) -> Optional["TencentOcrProvider"]:
    secret_id = config.get("tencent_secret_id", "") or config.get("secret_id", "")
    secret_key = config.get("tencent_secret_key", "") or config.get("secret_key", "")
    if not secret_id or not secret_key:
        logger.warning("腾讯云 OCR 未配置 secret_id/secret_key，跳过")
        return None
    return TencentOcrProvider(secret_id=secret_id, secret_key=secret_key)


def _create_aliyun(config: dict) -> Optional["AliyunOcrProvider"]:
    ak_id = config.get("aliyun_access_key_id", "") or config.get("access_key_id", "")
    ak_secret = config.get("aliyun_access_key_secret", "") or config.get("access_key_secret", "")
    if not ak_id or not ak_secret:
        logger.warning("阿里云 OCR 未配置 access_key_id/access_key_secret，跳过")
        return None
    return AliyunOcrProvider(access_key_id=ak_id, access_key_secret=ak_secret)
