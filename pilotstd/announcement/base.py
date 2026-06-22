# pilotstd/announcement/base.py
# 公告抓取适配器抽象基类

import concurrent.futures
import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional

import requests

from ..query.network import CHROME_UA, safe_raw_get, safe_request

logger = logging.getLogger(__name__)

# 逐条详情抓取间隔（秒），多线程模式下仅在线程间抖动
FETCH_DELAY_RANGE = (0.5, 1.0)
# 详情获取最大并发数
_MAX_DETAIL_WORKERS = 3


class BaseAnnounceAdapter(ABC):
    """公告抓取适配器基类。每个站点/公告类型一个子类。"""

    # ── 子类必须定义 ──

    @property
    @abstractmethod
    def site_name(self) -> str:
        """适配器标识，如 'samr_gb'。"""
        ...

    @property
    @abstractmethod
    def standard_type(self) -> str:
        """公告类型: 'gb' / 'hb' / 'db'。"""
        ...

    @property
    @abstractmethod
    def _list_url(self) -> str:
        """公告列表 API 地址。"""
        ...

    @property
    @abstractmethod
    def _detail_url(self) -> str:
        """公告详情页基础 URL。"""
        ...

    @property
    def source_site(self) -> str:
        """写入 announcement_cache 的 source_site 值。"""
        return f"announcement_{self.standard_type}"

    # ── 列表拉取（通用实现，子类只需提供 _list_url 和 site_name）

    def _fetch_list(self, since_date: str, page_size: int) -> list[dict[str, Any]]:
        """分页拉取公告列表，按日期降序排列。
        当遇到早于 since_date 的记录时提前终止。
        """
        announcements: list[Any] = []
        session = requests.Session()
        session.headers["User-Agent"] = CHROME_UA
        page = 1
        while True:
            params = {
                "pageNumber": page,
                "pageSize": page_size,
                "sortName": "NOTICE_DATE",
                "sortOrder": "desc",
            }
            resp = safe_request(
                session,
                "GET",
                self._list_url,
                self.site_name,
                timeout=120,
                params=params,
            )
            if resp is None:
                break
            try:
                data = resp.json()
            except Exception as e:
                logger.error("%s公告响应解析失败: %s", self.standard_type.upper(), e)
                break
            rows = data.get("rows", [])
            if not rows:
                break
            for row in rows:
                if since_date and row.get("NOTICE_DATE", "") < since_date:
                    return announcements
                announcements.append(
                    {
                        "pid": row.get("PID", ""),
                        "code": row.get("CODE", ""),
                        "title": row.get("C_TITLE", ""),
                        "notice_date": row.get("NOTICE_DATE", ""),
                        "std_count": row.get("STD_COUNT", ""),
                    }
                )
            total = data.get("total", 0)
            if page * page_size >= total:
                break
            page += 1
        return announcements

    # ── 详情获取（通用实现，子类只需提供 _detail_url 和 site_name）──

    # _parse_items 提供默认实现（页面结构路由），子类可重写
    # _download_attachment 提供默认实现，子类可重写

    def _download_attachment(self, url: str) -> Optional[bytes]:
        """下载附件，子类可重写。"""
        from ..query.network import safe_raw_get

        resp = safe_raw_get(url, self.site_name, timeout=60)
        if resp and resp.status_code == 200:
            return resp.content
        return None

    # ── 详情获取（通用实现）──

    def _fetch_detail(self, pid: str) -> Optional[str]:
        """获取公告详情页 HTML，失败返回 None。"""
        resp = safe_raw_get(f"{self._detail_url}?id={pid}", self.site_name, timeout=120)
        if resp is not None:
            resp.encoding = "utf-8"
            return resp.text
        return None

    # ── 公共解析入口（页面结构路由）──

    def _parse_items(
        self, raw_detail: str, ocr_provider: Any = None
    ) -> list[dict[str, Any]]:
        """子类可重写。默认实现：HTML 表格优先，无数据时回退附件。"""
        from .parser import find_attachment_url, parse_announcement_detail

        html_items, meta = parse_announcement_detail(
            raw_detail, None, "", ocr_provider=ocr_provider
        )
        attachment_url = find_attachment_url(raw_detail) or ""

        # 纯网页：HTML 已拿到数据
        if html_items and not attachment_url:
            return self._finalize_items(html_items, attachment_url)

        # 纯附件：HTML 无表格
        if not html_items and attachment_url:
            att_bytes = self._download_attachment(attachment_url)
            if att_bytes:
                att_items, _meta = parse_announcement_detail(
                    raw_detail, att_bytes, attachment_url, ocr_provider=ocr_provider
                )
                return self._finalize_items(att_items, attachment_url)
            return self._finalize_items(html_items, attachment_url)

        # 混合：HTML 有数据 + 有附件。下载附件存档，但直接返回 HTML 结果（不重新解析）
        if html_items and attachment_url:
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                executor.submit(self._download_attachment, attachment_url)
            return self._finalize_items(html_items, attachment_url)

        return self._finalize_items(html_items, attachment_url)

    @staticmethod
    def _finalize_items(
        items: list[dict[str, Any]], attachment_url: str
    ) -> list[dict[str, Any]]:
        """为每条标准补默认字段。"""
        for item in items:
            item.setdefault("attachment_url", attachment_url)
            item.setdefault("attachment_path", "")
        return items

    def fetch_announcements(
        self,
        since_date: str = "",
        page_size: int = 20,
        ocr_provider=None,
        progress_callback: Callable[[int, int, str], None] | None = None,
        checkpoint_pids: set[Any] | None = None,
    ) -> list[dict[str, Any]]:
        """一站式：列表 → 并行详情+解析 → 标准清单。

        Args:
            progress_callback: 每条完成回调 (current, total, label)
            checkpoint_pids: 已处理的 pid 集合，跳过这些公告
        """
        ann_list = self._fetch_list(since_date, page_size)
        if not ann_list:
            return []

        # 过滤已处理的公告（断点续传）
        if checkpoint_pids:
            remaining = [a for a in ann_list if a["pid"] not in checkpoint_pids]
            skipped = len(ann_list) - len(remaining)
            if skipped > 0:
                logger.info(
                    "公告 %s: 跳过已完成 %d 条, 剩余 %d 条",
                    self.standard_type,
                    skipped,
                    len(remaining),
                )
            ann_list = remaining

        if not ann_list:
            return []

        total = len(ann_list)
        items = []
        completed = [0]
        lock = __import__("threading").Lock()
        _ann_t0 = __import__("time").monotonic()

        def _bump(pid: str) -> None:
            with lock:
                completed[0] += 1
                _elapsed = __import__("time").monotonic() - _ann_t0
                _pct = int(completed[0] / total * 100) if total > 0 else 0
                # 每条均输出（线程间交错自然节流），含进度百分比和耗时
                logger.info(
                    "公告进度: pid=%s (%d/%d %d%%) 已耗时 %.0fs",
                    pid,
                    completed[0],
                    total,
                    _pct,
                    _elapsed,
                )
                if progress_callback:
                    progress_callback(completed[0], total, pid)

        def _process_one(ann: dict[str, Any]) -> list[dict[str, Any]]:
            """处理单条公告：取详情 → 解析。线程安全。"""
            raw = self._fetch_detail(ann["pid"])
            if not raw:
                logger.warning(
                    "公告详情获取失败: pid=%s code=%s",
                    ann.get("pid", ""),
                    ann.get("code", ""),
                )
                _bump(ann.get("pid", "?"))
                return []
            parsed = self._parse_items(raw, ocr_provider=ocr_provider)
            if not parsed:
                logger.warning(
                    "公告解析为空: pid=%s code=%s title=%s",
                    ann.get("pid", ""),
                    ann.get("code", ""),
                    ann.get("title", "")[:60],
                )
            for item in parsed:
                item.setdefault(
                    "announcement_title", ann.get("title", ann.get("code", ""))
                )
                item.setdefault("pid", ann.get("pid", ""))
            _bump(ann.get("code", "?")[:20])
            return parsed

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=_MAX_DETAIL_WORKERS
        ) as executor:
            futures = {executor.submit(_process_one, ann): ann for ann in ann_list}
            for future in concurrent.futures.as_completed(futures):
                try:
                    items.extend(future.result())
                except Exception:
                    logger.exception("公告处理异常")
        return items
