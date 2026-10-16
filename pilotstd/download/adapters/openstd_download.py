# 模块：项目/下载/适配器/国家标准全文公开系统下载脚本
"""国家标准全文公开系统（openstd.samr.gov.cn）下载适配器。

⚠️ 2026-09-26 对着现网逐跳实测确认的下载链路（6 步，全部走 `/bzgk/std/*`）：

  1. `GET {BASE}/newGbInfo?hcno=<H>`                    详情页（建立 JSESSIONID + 校验 hcno 是否被识别）
  2. `GET {BASE}/showGb?type=download&hcno=<H>&request_locale=zh`
     （`Referer: 详情页`）→「全文下载」页；其 JS 里写着后续动作：
     `window.location.href = "viewGb?hcno=" + hcno`
  3. `GET {BASE}/gc?_<毫秒>`（`Referer: 全文下载页`）      验证码图片（image/jpeg）
  4. `ddddocr` 识别 4 位验证码
  5. `POST {BASE}/verifyCode  verifyCode=<4位>`（同上 Referer）  期望响应体为 `success`
  6. `GET {BASE}/viewGb?hcno=<H>`（同上 Referer）        `Content-Disposition: attachment;filename=xxx.pdf`

  实测要点：步骤 2 的「全文下载页」不是可选项——不打开它、直接 3→5→6 在新会话上会拿到
  200 + 0 字节（GB/T 5613-2026 对照：跳过下载页 0B / 走完整序列 251,074B PDF）。
  因此本适配器按站点自身 JS 的顺序执行，并在 viewGb 空内容时整轮重试一次。

⚠️ 版权闸在**本适配器**判定（2026-10-16 新增，`parse_search_row`）：openstd 搜索页对采标标准
打 `<span class="label label-warning">采</span>`，本适配器认这个标记并以 `ADOPTED_SKIP_MESSAGE`
收口，**不进入验证码阶段**。为什么不能只依赖 `task.query_result.is_adopted`：采标判定逐查询站点
各写一套，权威判据只在 `std_gov`，而实测作答的 `cssn` 完全不判采标 ⇒ 那些站点答出的采标标准
`is_adopted=False`，若下载侧不自己认标记，版权闸就会随"哪个站点先答出来"而失效。

⚠️ 两个历史事故点（都已在现网复现，禁止再改回去）：

  A. **端点路径**：2026-09 起 openstd 把下载端点从 `/bzgk/gb/*` 迁到 `/bzgk/std/*`。
     旧路径对 GET 是 301（requests 自动跟随，表面上"还能用"），但 **POST 遇 301 会被
     requests 降级为 GET，表单体被丢弃** → `verifyCode` 恒返回 `error`；
     生产日志 2026-09-24~26 连续 15 次 `verifyCode 结果: error`、0 次 success 即此因。
     真正被丢弃的是验证码文本，与 OCR 准确率无关。

  B. **hcno 来源**：下载标识 hcno **只能**从 openstd 自己的搜索页取
     （`{BASE}/std_list_type?p.p1=0&p.p2=<标准号>&p.p90=circulation_date&p.p91=desc`
     中 `onclick="showInfo('<hcno>')"` 的值，且必须**按行内标准号匹配**）。
     `std.samr.gov.cn` 查询结果里的 `pid` 是**另一种标识**，openstd 侧不识别：
     实测 `newGbInfo?hcno=<pid>` 与"篡改末位"、"空 hcno"返回**逐字节相同**的页面。
     历史上 `70b631b4` / `d6a56b11` 已两次修过此处并留下"禁止再次误改 hcno 来源"的注释，
     `f4f812e7` 重写时又改回 pid → 第三次回归。
"""

import logging
import re
import time
from typing import Callable, Optional, cast

import requests

from ..models import ADOPTED_SKIP_MESSAGE, DownloadTask
from .base import BaseDownloadAdapter

logger = logging.getLogger(__name__)

# 搜索页结果行：<a href="javascript:void(0)" onclick="showInfo('9075EE…');">GB/T 5310-2008</a>
_HCNO_ROW_RE = re.compile(r"showInfo\(\s*['\"]([0-9A-Fa-f]{16,40})['\"]\s*\)\s*;[^>]*>([^<]{2,80})<")

# 搜索页结果行整行（`<tr>`）：采标判定必须看**整行**——"采"标记在标准号单元格之后，
# 不在锚点文本里（实测 2026-10-16：`<span class="label label-warning" title="该标准采用国际标准">采</span>`）
_ROW_RE = re.compile(r"<tr[^>]*>.*?</tr>", re.IGNORECASE | re.DOTALL)
# 采标标记：行内出现 label-warning 且该 span 文本为"采"，或标题属性写明"采用国际标准"
# i18n-allow: 匹配 openstd 站点页面上的中文标记，翻译即失效
_ADOPTED_RE = re.compile(r"label-warning[^>]*>\s*采|该标准采用国际标准")

# viewGb 整轮重试次数：会话授权偶发未落地时返回 200 + 0 字节，重开下载页再来一轮即可
_VIEW_ROUNDS = 2


def _norm_std_no(text: str) -> str:
    """标准号归一：去空白、统一连字符与斜杠、大写（页面写法可能是 `GB/T 150.1-2024` 或 `GB/T150.1-2024`）。"""
    s = text.strip().upper()
    for ch in (" ", "\u3000", "\t", "\n", "\r"):
        s = s.replace(ch, "")
    for src, dst in (("—", "-"), ("－", "-"), ("／", "/")):
        s = s.replace(src, dst)
    return s


def parse_hcno_from_search_page(html: str, standard_number: str) -> str:
    """从 openstd 搜索页 HTML 中按标准号匹配 hcno；未匹配返回空串。

    ⚠️ 必须比对行内标准号，不能取页面第一个 `showInfo(...)`：搜索页会同时返回多条
    结果（2026-09-26 实测：搜 `GB/T 5310-2008` 时首条是 `GB 2024-2016`），
    取首条会把**别的标准**的全文当成该收藏的下载内容。
    """
    return parse_search_row(html, standard_number)[0]


def parse_search_row(html: str, standard_number: str) -> tuple[str, bool]:
    """按标准号匹配搜索页结果行，返回 `(hcno, is_adopted)`；未匹配返回 `("", False)`。

    **`is_adopted` 是下载侧唯一的权威版权闸依据**（2026-10-16 新增）：
    openstd 在采标标准所在行打 `<span class="label label-warning" …>采</span>`，
    详情页另有"该标准采用了ISO、IEC等……由于涉及版权保护问题，本系统暂不提供在线阅读服务"。

    为什么不能只看查询结果：采标判定是**逐查询站点各写一套**，权威判据只在 `std_gov`
    （`std_gov.py` 读官方表格的"采"字段），而 `cssn` 等站点根本不判采标 ⇒
    `QueryResult.is_adopted` 在那些站点作答时为 `False`。实测（部署实例 v0.138.3，
    2026-10-16T22:07+08:00）：`GB/T 7584.1-2026`、`GB/T 8335-2026`、`GB 20097-2025`、
    `GB/T 18663.6-2026` 四个在案采标标准全部 `is_adopted=False`、`is_downloadable=True`。
    故版权闸必须由**下载站点自身**认这个标记，否则"该不该下载"仍取决于哪个站点先答出来。
    """
    target = _norm_std_no(standard_number)
    if not target:
        return "", False
    for block, hcno, label in _iter_search_rows(html):
        if _norm_std_no(label) == target:
            return hcno, bool(_ADOPTED_RE.search(block))
    return "", False


def _iter_search_rows(html: str) -> "list[tuple[str, str, str]]":
    """产出 `(判定块, hcno, 行内标准号)`。

    有 `<tr>` 时按行切分（"采"标记与标准号同行，需整行判定）；没有 `<tr>` 的片段
    （既有单测夹具即为此形态）退化为**逐锚点**扫描，保持与旧实现完全一致的匹配顺序。
    """
    rows = [m.group(0) for m in _ROW_RE.finditer(html)]
    out: list[tuple[str, str, str]] = []
    if rows:
        for block in rows:
            out.extend((block, m.group(1), m.group(2)) for m in _HCNO_ROW_RE.finditer(block))
    else:
        out.extend((html, m.group(1), m.group(2)) for m in _HCNO_ROW_RE.finditer(html))
    return out


class OpenstdDownloadAdapter(BaseDownloadAdapter):
    """国家标准全文公开系统（openstd.samr.gov.cn）下载适配器。

    下载标识 hcno 由本适配器自行解析（openstd 搜索页），**不使用** `query_result.hcno`
    ——查询流程（std_gov）产出的 `pid` 与下载流程需要的 `hcno` 是两个不同的标识。
    """

    # ⚠️ 路径不可回退到 /bzgk/gb：POST 遇 301 被降级为 GET，verifyCode 体丢失（见模块 docstring A）
    BASE_URL = "https://openstd.samr.gov.cn/bzgk/std"

    @property
    def search_url(self) -> str:
        """hcno 搜索页（与 BASE_URL 同源）。

        刻意由 BASE_URL 派生：站点整体迁移路径时只需改一个常量，
        避免"端点改了、搜索页还指旧路径"这类漂移（本适配器已因路径漂移出过一次事故）。
        """
        return f"{self.BASE_URL}/std_list_type"

    def __init__(
        self,
        session: requests.Session | None = None,
        captcha_callback: Optional[Callable[[bytes], Optional[str]]] = None,
    ):
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

    # ════════════════════════════════════════════════════════════════ 分隔
    # hcno 解析（下载标识，与查询产出的 pid 无关）
    # ════════════════════════════════════════════════════════════════ 分隔

    def _lookup_hcno(self, standard_number: str) -> tuple[str, bool]:
        """到 openstd 搜索页按标准号解析 `(hcno, is_adopted)`；失败返回 `("", False)`。"""
        try:
            resp = self._session.get(
                self.search_url,
                params={
                    "p.p1": "0",
                    "p.p2": standard_number,
                    "p.p90": "circulation_date",
                    "p.p91": "desc",
                },
                timeout=30,
            )
        except requests.RequestException as e:
            logger.warning("openstd 搜索 hcno 失败 (%s): %s", standard_number, e)
            return "", False

        if resp.status_code != 200:
            logger.warning("openstd 搜索 hcno HTTP %s (%s)", resp.status_code, standard_number)
            return "", False

        hcno, adopted = parse_search_row(resp.text, standard_number)
        if not hcno and not adopted:
            logger.warning(
                "openstd 搜索页未匹配到标准号 %s（可能尚未收录/标准号写法不一致；"
                "注意 std_gov 的 pid 不是 hcno，禁止回退使用）",
                standard_number,
            )
        return hcno, adopted

    def _resolve_target(self, task: DownloadTask) -> tuple[str, bool]:
        """解析 `(hcno, is_adopted)`：显式传入（`task.extra["hcno"]`，供手工/GUI）→ 搜索页。

        刻意**不**回退 `task.query_result.hcno`：那是 std_gov 的 pid，openstd 不识别，
        回退后只会让失败推迟到验证码之后并伪装成"验证码问题"（2026-09 事故根因之一）。
        显式传入的 hcno 无法从搜索页判采标（不额外发一次请求），故 `is_adopted=False`。
        """
        explicit = task.extra.get("hcno", "") if task.extra else ""
        if explicit:
            return str(explicit), False
        return self._lookup_hcno(task.standard_number)

    # ════════════════════════════════════════════════════════════════ 分隔
    # 下载主流程
    # ════════════════════════════════════════════════════════════════ 分隔

    def download(self, task: DownloadTask) -> Optional[bytes]:
        """解析标识后执行下载；采标直接跳过，解析不到直接失败——都不进入验证码阶段。"""
        hcno, adopted = self._resolve_target(task)
        if adopted:
            # 版权闸：与查询阶段的采标跳过同一文案，调用方按 ADOPTED_SKIP_MESSAGE 识别业务终态
            task.error_message = ADOPTED_SKIP_MESSAGE
            # i18n-allow: 开发者日志（与既有告警同口径，不进 i18n）
            logger.info("采标标准，跳过下载（openstd 搜索页「采」标记）: %s", task.standard_number)
            return None
        if not hcno:
            task.error_message = (
                f"无法获取下载标识(hcno): {task.standard_number}"
                "（openstd 搜索页未匹配到该标准号；std_gov 的 pid 不能当 hcno 用）"
            )
            logger.warning("下载失败(无hcno): %s", task.standard_number)
            return None

        logger.debug("下载开始: %s hcno=%s", task.standard_number, hcno)
        return self._do_download(hcno, task)

    def _visit_detail(self, hcno: str, task: DownloadTask) -> str:
        """预访问详情页：建立会话，并在详情页查不到该标准号时提前告警（hcno 失效信号）。

        返回详情页 URL，供后续下载页/验证码请求当 `Referer`（浏览器点击链路同款）。
        """
        detail_url = f"{self.BASE_URL}/newGbInfo?hcno={hcno}"
        try:
            resp = self._session.get(detail_url, timeout=30)
        except requests.RequestException as e:
            logger.debug("详情页预访问失败（继续走验证码）: %s", e)
            return detail_url
        if resp.status_code == 200 and _norm_std_no(task.standard_number) not in _norm_std_no(resp.text):
            # pid / 空 / 篡改 hcno 都会走到这里：服务端返回同一张"标准不存在"的壳页面
            logger.warning(
                "hcno 疑似无效: %s hcno=%s（详情页未出现该标准号，检查 hcno 来源是否为 openstd 搜索页）",
                task.standard_number,
                hcno,
            )
        return detail_url

    def _open_download_page(self, hcno: str, detail_url: str) -> str:
        """打开「全文下载」页（浏览器点"下载标准"的真实动作），返回可用作 Referer 的 URL。

        实测（2026-09-26）：不打开该页直接 `gc→verifyCode→viewGb` 也能偶尔成功，
        但**新会话首下**会返回 200 + 0 字节；按站点自身 JS 的顺序（下载页 → 验证码 → viewGb）
        在同一会话里带上该页 Referer 则稳定拿到 PDF（GB/T 5613-2026 对照：最小序列 0B / 本序列 251KB）。
        """
        dl_url = f"{self.BASE_URL}/showGb?type=download&hcno={hcno}&request_locale=zh"
        try:
            resp = self._session.get(dl_url, timeout=30, headers={"Referer": detail_url})
            logger.debug("全文下载页: %s -> %s len=%d", dl_url, resp.status_code, len(resp.text))
            return resp.url or dl_url
        except requests.RequestException as e:
            logger.debug("全文下载页打开失败（仍尝试验证码）: %s", e)
            return dl_url

    def _do_download(self, hcno: str, task: DownloadTask) -> Optional[bytes]:
        """5 步链路（详见模块 docstring）：详情页 → 下载页 → gc → 识别 → verifyCode → viewGb。

        viewGb 偶发 200 + 0 字节（会话授权未落地），故整轮重试 `_VIEW_ROUNDS` 次。
        """
        detail_url = self._visit_detail(hcno, task)

        for round_idx in range(_VIEW_ROUNDS):
            referer = self._open_download_page(hcno, detail_url)
            self._handle_captcha(hcno, task, referer)
            if task.error_message:
                return None

            content = self._fetch_view(hcno, referer, task)
            if content is not None:
                # 记录实际用到的轮次：用于现场统计"两轮是否够用"（第 2 轮多为会话授权未落地）
                logger.info(
                    "viewGb 第%d轮取到全文: %s hcno=%s bytes=%d",
                    round_idx + 1,
                    task.standard_number,
                    hcno,
                    len(content),
                )
                return content
            if round_idx < _VIEW_ROUNDS - 1:
                logger.warning(
                    "viewGb 未取到全文，重开下载页重试（%s hcno=%s）",
                    task.standard_number,
                    hcno,
                )
                task.error_message = ""  # 清空以便下一轮重新判定
        return None

    def _fetch_view(self, hcno: str, referer: str, task: DownloadTask) -> Optional[bytes]:
        """取全文：GET viewGb → 校验文件头 → 提取文件名。失败设 `task.error_message` 并返回 None。"""
        view_url = f"{self.BASE_URL}/viewGb?hcno={hcno}"
        try:
            resp = self._session.get(view_url, timeout=120, stream=True, headers={"Referer": referer})
        except requests.RequestException as e:
            task.error_message = f"PDF 下载请求失败: {e}"
            logger.warning("下载失败(viewGb): %s hcno=%s | %s", task.standard_number, hcno, e)
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
            # 会话未通过验证码、或该标准暂无全文，都会是 200 + 0 字节
            task.error_message = "viewGb 返回空内容（会话未通过验证码，或该标准暂无全文）"
            logger.warning("下载失败(空内容): %s hcno=%s", task.standard_number, hcno)
            return None

        # 从响应头提取服务器建议的文件名
        cd = resp.headers.get("Content-Disposition", "")
        if cd and "filename=" in cd:
            m = re.search(r'filename[^;=\n]*=(["\']?)([^"\';\n]+)\1', cd)
            if m:
                if task.extra is None:
                    task.extra = {}
                task.extra["filename_from_header"] = m.group(2)
                logger.debug("Content-Disposition 文件名: %s", m.group(2))

        # 校验便携文档文件头
        if content[:5] == b"%PDF-":
            return cast("bytes | None", content)
        if len(content) > 1000 and b"html" not in content[:50].lower():
            return cast("bytes | None", content)

        task.error_message = "viewGb 返回非 PDF 内容"
        logger.warning(
            "下载失败(非PDF): %s hcno=%s | 前50字节=%r",
            task.standard_number,
            hcno,
            content[:50],
        )
        return None

    # ════════════════════════════════════════════════════════════════ 分隔
    # 验证码处理
    # ════════════════════════════════════════════════════════════════ 分隔

    def _handle_captcha(self, hcno: str, task: DownloadTask, referer: str = "") -> Optional[bytes]:
        """验证码识别与提交：GET gc 图片 → ddddocr 识别 → POST verifyCode。

        每轮最多两次（第二次换一张图）；`referer` 传「全文下载页」URL（与浏览器同款）。
        验证成功后返回 None（由调用方继续 viewGb），失败则设置 `task.error_message`。
        """
        hdrs = {"Referer": referer} if referer else {}
        for attempt in range(2):
            # ═══ 步骤2：获取验证码图片 ═══
            captcha_url = f"{self.BASE_URL}/gc?_{int(time.time() * 1000)}"
            try:
                img_resp = self._session.get(captcha_url, timeout=15, headers=hdrs)
            except requests.RequestException as e:
                task.error_message = "验证码图片获取失败"
                logger.warning("下载失败(验证码): %s | 图片获取失败: %s", task.standard_number, e)
                return None

            if img_resp.status_code != 200 or b"image" not in img_resp.headers.get("Content-Type", "").encode():
                # 端点迁移/被重定向到 HTML 时，这里会第一时间暴露（而不是等到 verifyCode 报 error）
                logger.error(
                    "验证码图片异常: %s HTTP %s ctype=%s len=%d（端点是否已迁移？）",
                    task.standard_number,
                    img_resp.status_code,
                    img_resp.headers.get("Content-Type"),
                    len(img_resp.content),
                )

            # ═══步骤3：识别═══
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
                    headers=hdrs,
                )
                result = resp.text.strip()
                logger.info("verifyCode 结果: %s (第%d次)", result, attempt + 1)
                if result == "success":
                    return None  # 验证通过，由调用方继续 viewGb
                if "<html" in result[:200].lower() or len(result) > 40:
                    # 正常契约只有 success/error 两个词；别的响应体说明端点被重定向或迁移了
                    logger.error(
                        "verifyCode 返回非预期内容（端点可能已迁移）: HTTP %s body=%r",
                        resp.status_code,
                        result[:120],
                    )
            except requests.RequestException as e:
                logger.warning("verifyCode 请求失败: %s", e)
                if attempt == 0:
                    continue

        task.error_message = "验证码提交失败（已重试）"
        logger.warning("下载失败(验证码): %s hcno=%s | 验证码提交失败", task.standard_number, hcno)
        return None
