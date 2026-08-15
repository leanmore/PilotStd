# 模块：项目//脚本
# 公告抓取适配器抽象基类

import concurrent.futures
import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional

import requests

from ..query.network import CHROME_UA, safe_raw_get, safe_request
from ._circuit_breaker import AdapterFrozenError, CircuitBreaker  # noqa: F401 — 重导出
from ._raw_store import _store_raw_content

logger = logging.getLogger(__name__)

# 逐条详情抓取间隔（秒），多线程模式下仅在线程间抖动
FETCH_DELAY_RANGE = (0.5, 1.0)
# 详情获取最大并发数
_MAX_DETAIL_WORKERS = 3


class BaseAnnounceCrawler(ABC):
    """公告抓取适配器基类。每个站点/公告类型一个子类。"""

    def __init__(self, config: Any = None, _http: Any = None):
        # 熔断状态以标准类型为键写入适配器状态表，与状态接口读取口径一致
        self._cb = CircuitBreaker(lambda: self.standard_type)  # 组合，非继承
        self._http = _http

    # ──熔断委托（→）──

    def _cb_load_health(self) -> None:
        self._cb.load_health()

    def _cb_save_health(self) -> None:
        self._cb.save_health()

    def _cb_check_frozen(self) -> None:
        self._cb.check_frozen()

    def _cb_record_success(self) -> None:
        self._cb.record_success()

    def _cb_record_failure(self) -> bool:
        return self._cb.record_failure()

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
        """写入 announcement_match 的 source_site 值。"""
        return f"announcement_{self.standard_type}"

    # ──列表拉取（通用实现，子类只需提供__和_）

    def _fetch_list(self, since_date: str, page_size: int) -> list[dict[str, Any]]:
        """分页拉取公告列表，按日期降序排列。
        当遇到早于 since_date 的记录时提前终止。
        """
        announcements: list[Any] = []
        session = self._http if self._http is not None else requests.Session()
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
                        "title": row.get("TITLE", row.get("C_TITLE", "")),
                        "notice_date": row.get("NOTICE_DATE", ""),
                        "std_count": row.get("STD_COUNT", ""),
                    }
                )
            total = data.get("total", 0)
            if page * page_size >= total:
                break
            page += 1
        return announcements

    # ──详情获取（通用实现，子类只需提供__和_）──

    # __提供默认实现（页面结构路由），子类可重写
    # _下载_提供默认实现，子类可重写

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
        url = f"{self._detail_url}?id={pid}"
        resp = safe_raw_get(url, self.site_name, timeout=120)
        if resp is None:
            logger.warning("公告详情请求失败: type=%s url=%s", self.standard_type, url[:100])
            return None
        if resp.status_code != 200:
            logger.warning(
                "公告详情HTTP错误: type=%s status=%d url=%s",
                self.standard_type,
                resp.status_code,
                url[:100],
            )
            return None
        resp.encoding = "utf-8"
        return resp.text

    # ── 公共解析入口（页面结构路由）──

    def _parse_items(self, raw_detail: str, ocr_provider: Any = None) -> list[dict[str, Any]]:
        """子类可重写。默认实现：HTML 表格优先，无数据时回退附件。"""
        from .parser import find_attachment_url, parse_announcement_detail

        html_items, meta = parse_announcement_detail(raw_detail, None, "", ocr_provider=ocr_provider)
        attachment_url = find_attachment_url(raw_detail) or ""

        # 纯网页：网页已拿到数据
        if html_items and not attachment_url:
            return self._finalize_items(html_items, attachment_url)

        # 纯附件：网页无表格
        if not html_items and attachment_url:
            att_bytes = self._download_attachment(attachment_url)
            if att_bytes:
                att_items, _meta = parse_announcement_detail(
                    raw_detail, att_bytes, attachment_url, ocr_provider=ocr_provider
                )
                return self._finalize_items(att_items, attachment_url, "附件解析")
            return self._finalize_items(html_items, attachment_url)

        # 混合：网页有数据+有附件。下载附件存档，但直接返回网页结果（不重新解析）
        if html_items and attachment_url:
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                executor.submit(self._download_attachment, attachment_url)
            return self._finalize_items(html_items, attachment_url)

        return self._finalize_items(html_items, attachment_url)

    @staticmethod
    def _finalize_items(
        items: list[dict[str, Any]], attachment_url: str, source_type: str = "网页解析"
    ) -> list[dict[str, Any]]:
        """为每条标准补默认字段。"""
        for item in items:
            item.setdefault("attachment_url", attachment_url)
            item.setdefault("attachment_path", "")
            item.setdefault("source_type", source_type)
        return items

    def _process_one_detail(
        self,
        ann: dict[str, Any],
        ocr_provider: Any,
        _bump: Callable[[str], None],
    ) -> list[dict[str, Any]]:
        """处理单条公告：取详情 → 解析。线程安全。"""
        raw = self._fetch_detail(ann["pid"])
        if not raw:
            logger.warning(
                "公告详情获取失败: type=%s pid=%s code=%s",
                self.standard_type,
                ann.get("pid", "")[:32],
                ann.get("code", ""),
            )
            _bump(ann.get("pid", "?"))
            return []
        # 提取公告正文写入._
        _store_raw_content(
            ann.get("code", ""),
            ann.get("pid", ""),
            ann.get("title", ""),
            ann.get("notice_date", ""),
            self.source_site,
            raw,
        )
        parsed = self._parse_items(raw, ocr_provider=ocr_provider)
        if not parsed:
            logger.warning(
                "公告解析为空: type=%s pid=%s code=%s html_size=%d title=%s",
                self.standard_type,
                ann.get("pid", "")[:32],
                ann.get("code", ""),
                len(raw),
                ann.get("title", "")[:60],
            )
        else:
            logger.debug(
                "公告解析成功: type=%s code=%s items=%d",
                self.standard_type,
                ann.get("code", ""),
                len(parsed),
            )
        notice_date = ann.get("notice_date", "")
        for item in parsed:
            item.setdefault("announcement_title", ann.get("title", ann.get("code", "")))
            item["_pid"] = ann.get("pid", "")
            item["announce_no"] = ann.get("code", "")
            raw_std_count = ann.get("std_count", "")
            item["standard_count"] = int(raw_std_count) if raw_std_count else len(parsed)
            # 列表接口的_是公告权威发布日期，覆盖所有条目
            # 网页表格和附件解析可能产生不同的_（甚至为空），
            # 不一致会导致查询返回重复行
            if notice_date:
                item["publish_date"] = notice_date
            item["notice_date"] = notice_date
        _bump(ann.get("code", "?")[:20])
        return parsed

    def _fetch_details_parallel(
        self,
        ann_list: list[dict[str, Any]],
        ocr_provider: Any,
        progress_callback: Callable[[int, int, str], None] | None,
    ) -> list[dict[str, Any]]:
        """并行拉取公告详情并解析，返回标准条目列表。"""
        total = len(ann_list)
        items: list[dict[str, Any]] = []
        completed: list[int] = [0]
        lock = __import__("threading").Lock()
        _ann_t0 = __import__("time").monotonic()

        def _bump(pid: str) -> None:
            """进度推进：计数+1并输出日志，可选回调通知调用方。"""
            with lock:
                completed[0] += 1
                _elapsed = __import__("time").monotonic() - _ann_t0
                _pct = int(completed[0] / total * 100) if total > 0 else 0
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

        with concurrent.futures.ThreadPoolExecutor(max_workers=_MAX_DETAIL_WORKERS) as executor:
            futures = {executor.submit(self._process_one_detail, ann, ocr_provider, _bump): ann for ann in ann_list}
            for future in concurrent.futures.as_completed(futures):
                try:
                    items.extend(future.result())
                except Exception:
                    logger.exception("公告处理异常")
        return items

    def fetch_announcements(
        self,
        since_date: str = "",
        page_size: int = 20,
        ocr_provider: Any = None,
        progress_callback: Callable[[int, int, str], None] | None = None,
        complete_pids: set[Any] | None = None,
    ) -> list[dict[str, Any]]:
        """一站式：列表 → 去重过滤 → 并行详情+解析 → 标准清单。

        Args:
            progress_callback: 每条完成回调 (current, total, label)
            complete_pids: 已完全解析的公告 PID 集合，跳过这些公告的阶段2抓取
        """
        self._cb_check_frozen()

        try:
            ann_list = self._fetch_list(since_date, page_size)
            if not ann_list:
                self._cb_record_success()
                return []

            # 过滤已完全解析的公告
            if complete_pids:
                remaining = [a for a in ann_list if a["pid"] not in complete_pids]
                skipped = len(ann_list) - len(remaining)
                if skipped > 0:
                    logger.info(
                        "公告 %s: 跳过已完全解析 %d 条, 剩余 %d 条",
                        self.standard_type,
                        skipped,
                        len(remaining),
                    )
                ann_list = remaining

            if not ann_list:
                self._cb_record_success()
                return []

            items = self._fetch_details_parallel(ann_list, ocr_provider, progress_callback)

            if items:
                self._cb_record_success()
            else:
                self._cb_record_failure()
            return items
        except AdapterFrozenError:
            raise
        except Exception:
            self._cb_record_failure()
            raise
