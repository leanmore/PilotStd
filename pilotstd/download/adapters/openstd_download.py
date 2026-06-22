# pilotstd/download/adapters/openstd_download.py
# 国家标准全文公开系统下载适配器 — openstd.samr.gov.cn 新平台
#
# ⚠️ 2026-06-04 实测验证通过的完整下载链路（5步，不可跳过）：
#   1. GET showGb?type=download&hcno=<H>  →  302 + Set-Cookie: JSESSIONID
#      （建立会话，获取 cookie——跳过此步则后续全部 404）
#   2. GET gc?_<ts>  →  验证码图片（~4KB）
#   3. ddddocr 识别 4 位验证码
#   4. POST verifyCode  body: verifyCode=<4位码>  →  "success"
#      （验证通过后服务端授权当前会话的 viewGb 访问）
#   5. GET viewGb?hcno=<H>  →  Content-Disposition: attachment;filename=xxx.pdf
#      返回完整 PDF 字节流

import logging
import time
from typing import Optional

import requests

from ..models import DownloadTask
from .base import BaseDownloadAdapter

logger = logging.getLogger(__name__)


class OpenstdDownloadAdapter(BaseDownloadAdapter):
    """国家标准全文公开系统（openstd.samr.gov.cn）下载适配器。

    ⚠️ hcno 来源：std_gov 适配器查询结果的 pid 即新平台 hcno，
    无需额外搜索步骤。query_result.hcno 直接使用。
    """

    # 新平台基础 URL（2026-06-04 起 gb688.cn 已停用）
    BASE_URL = "https://openstd.samr.gov.cn/bzgk/gb"

    def __init__(self, session: requests.Session | None = None, captcha_callback=None):
        self._session = session or requests.Session()
        self._captcha_callback = captcha_callback
        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/133.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,*/*",
                "Accept-Language": "zh-CN,zh;q=0.9",
            }
        )

    @property
    def site_name(self) -> str:
        return "openstd_download"

    def can_handle(self, task: DownloadTask) -> bool:
        return task.source_site == "openstd_download"

    def download(self, task: DownloadTask) -> Optional[bytes]:
        """执行下载。

        hcno 优先从 task.extra 取（显式传入），否则从查询结果直接取。
        std_gov 适配器的 pid 即新平台 hcno，无需额外搜索。
        """
        hcno = task.extra.get("hcno", "") if task.extra else ""
        if not hcno and task.query_result:
            hcno = getattr(task.query_result, "hcno", "")

        if not hcno:
            task.error_message = "缺少 hcno（需先查询获取标准唯一ID）"
            logger.warning("下载失败(缺hcno): %s", task.standard_number)
            return None

        logger.debug("下载开始: %s hcno=%s", task.standard_number, hcno)
        return self._do_download(hcno, task)

    # ════════════════════════════════════════════════════════════════
    # 核心下载流程
    # ════════════════════════════════════════════════════════════════

    def _do_download(self, hcno: str, task: DownloadTask) -> Optional[bytes]:
        """⚠️ 5 步下载链路，每步不可跳过。

        1. showGb 建立会话 → 获取 JSESSIONID
        2. gc 验证码图片
        3. ddddocr 识别
        4. verifyCode 提交验证
        5. viewGb 下载 PDF
        """
        # ═══ 步骤1：建立会话 ⚠️ 不可跳过 ═══
        # showGb 在首次访问时 302 重定向并设置 JSESSIONID cookie，
        # 此 cookie 是后续 gc / verifyCode / viewGb 的会话凭证。
        show_url = f"{self.BASE_URL}/showGb?type=download&hcno={hcno}&request_locale=zh"
        try:
            self._session.get(show_url, timeout=30)
        except requests.RequestException as e:
            task.error_message = f"建立会话失败: {e}"
            logger.warning("下载失败(建会话): %s | %s", task.standard_number, e)
            return None

        # ═══ 步骤2-4：验证码处理 ═══
        captcha_result = self._handle_captcha(hcno, task)
        if captcha_result:
            return captcha_result
        # _handle_captcha 返回 None 表示验证通过但未直接下载（需继续步骤5）

        # ═══ 步骤5：下载 PDF ⚠️ 不可跳过 ═══
        # viewGb 必须在 verifyCode 返回 "success" 之后调用，
        # 否则服务端返回 Content-Range: bytes 0-0/0（空文件）。
        view_url = f"{self.BASE_URL}/viewGb?hcno={hcno}"
        try:
            resp = self._session.get(view_url, timeout=120, stream=True)
        except requests.RequestException as e:
            task.error_message = f"PDF 下载请求失败: {e}"
            logger.warning(
                "下载失败(viewGb): %s hcno=%s | %s", task.standard_number, hcno, e
            )
            return None

        if resp.status_code != 200:
            task.error_message = f"viewGb HTTP {resp.status_code}"
            logger.warning(
                "下载失败(viewGb HTTP%d): %s hcno=%s",
                resp.status_code,
                task.standard_number,
                hcno,
            )
            return None

        content = resp.content
        if not content:
            task.error_message = "viewGb 返回空内容（标准可能暂无全文）"
            logger.warning("下载失败(空内容): %s hcno=%s", task.standard_number, hcno)
            return None

        # 从 Content-Disposition 响应头提取服务器建议的文件名
        cd = resp.headers.get("Content-Disposition", "")
        if cd and "filename=" in cd:
            import re

            m = re.search(r'filename[^;=\n]*=(["\']?)([^"\';\n]+)\1', cd)
            if m:
                task.extra["filename_from_header"] = m.group(2)
                logger.debug("Content-Disposition 文件名: %s", m.group(2))

        # 校验 PDF 文件头
        if content[:5] == b"%PDF-":
            return content
        if len(content) > 1000 and b"html" not in content[:50].lower():
            return content

        task.error_message = "viewGb 返回非 PDF 内容"
        logger.warning(
            "下载失败(非PDF): %s hcno=%s | 前50字节=%r",
            task.standard_number,
            hcno,
            content[:50],
        )
        return None

    # ════════════════════════════════════════════════════════════════
    # 验证码处理
    # ════════════════════════════════════════════════════════════════

    def _handle_captcha(self, hcno: str, task: DownloadTask) -> Optional[bytes]:
        """⚠️ 验证码识别与提交。

        流程：GET gc 图片 → ddddocr 识别 → POST verifyCode。
        最多重试一次（刷新验证码图片）。
        验证成功后返回 None（由调用方继续 viewGb 下载），
        失败则设置 task.error_message 并返回 None。
        """
        for attempt in range(2):
            # ═══ 步骤2：获取验证码图片 ═══
            captcha_url = f"{self.BASE_URL}/gc?_{int(time.time() * 1000)}"
            try:
                img_resp = self._session.get(captcha_url, timeout=15)
            except requests.RequestException as e:
                task.error_message = "验证码图片获取失败"
                logger.warning(
                    "下载失败(验证码): %s | 图片获取失败: %s", task.standard_number, e
                )
                return None

            # ═══ 步骤3：ddddocr 识别 ═══
            captcha_text = ""
            try:
                import ddddocr

                ocr = ddddocr.DdddOcr()
                captcha_text = ocr.classification(img_resp.content)
                logger.info("ddddocr 识别: %s (第%d次)", captcha_text, attempt + 1)
            except ImportError:
                logger.warning("ddddocr 未安装")
            except Exception as e:
                logger.warning("ddddocr 失败: %s", e)

            # 手动回调兜底
            if (not captcha_text or len(captcha_text) != 4) and self._captcha_callback:
                captcha_text = self._captcha_callback(img_resp.content) or ""

            if not captcha_text or len(captcha_text) != 4:
                if attempt == 0:
                    continue  # 刷新验证码重试
                task.error_message = "验证码识别失败"
                logger.warning(
                    "下载失败(验证码): %s | 识别失败 验证码文本=%r",
                    task.standard_number,
                    captcha_text,
                )
                return None

            # ═══ 步骤4：提交验证码 ═══
            try:
                resp = self._session.post(
                    f"{self.BASE_URL}/verifyCode",
                    data={"verifyCode": captcha_text},
                    timeout=15,
                )
                result = resp.text.strip()
                logger.info("verifyCode 结果: %s (第%d次)", result, attempt + 1)
                if result == "success":
                    return None  # 验证通过，由调用方继续 viewGb
            except requests.RequestException as e:
                logger.warning("verifyCode 请求失败: %s", e)
                if attempt == 0:
                    continue

        task.error_message = "验证码提交失败（已重试）"
        logger.warning(
            "下载失败(验证码): %s hcno=%s | 验证码提交失败", task.standard_number, hcno
        )
        return None
