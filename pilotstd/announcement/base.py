# pilotstd/announcement/base.py
# 公告抓取适配器抽象基类

import concurrent.futures
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

import requests

from ..query.network import CHROME_UA, safe_raw_get, safe_request

logger = logging.getLogger(__name__)

# 逐条详情抓取间隔（秒），多线程模式下仅在线程间抖动
FETCH_DELAY_RANGE = (0.5, 1.0)
# 详情获取最大并发数
_MAX_DETAIL_WORKERS = 3

# ── 熔断默认参数 ──
_DEFAULT_FREEZE_DURATIONS = [1800, 7200, 21600, 43200]  # 秒：30m/2h/6h/12h
_DEFAULT_FAILURE_THRESHOLD = 3
_DEFAULT_RESET_WINDOW_HOURS = 24
_HEALTH_TABLE = "adapter_health"


class AdapterFrozenError(Exception):
    """适配器处于冻结状态，请求被熔断拦截。"""

    def __init__(self, adapter_name: str, remaining_seconds: int):
        self.adapter_name = adapter_name
        self.remaining_seconds = remaining_seconds
        super().__init__(f"{adapter_name} 冻结中，剩余 {remaining_seconds} 秒")


class BaseAnnounceAdapter(ABC):
    """公告抓取适配器基类。每个站点/公告类型一个子类。"""

    def __init__(self, config: Any = None):
        self._cb_freeze_count: int = 0
        self._cb_first_freeze_time: Optional[datetime] = None
        self._cb_frozen_until: Optional[datetime] = None
        self._cb_fail_streak: int = 0
        self._cb_loaded: bool = False
        # 从配置读取熔断参数
        if config:
            self._cb_threshold = config.get("adapter.circuit_breaker.failure_threshold") or _DEFAULT_FAILURE_THRESHOLD
            raw_durations = config.get("adapter.circuit_breaker.freeze_durations")
            if raw_durations and isinstance(raw_durations, list):
                self._cb_durations = [int(m) * 60 for m in raw_durations]
            else:
                self._cb_durations = _DEFAULT_FREEZE_DURATIONS
            self._cb_reset_hours = (
                config.get("adapter.circuit_breaker.reset_window_hours") or _DEFAULT_RESET_WINDOW_HOURS
            )
        else:
            self._cb_threshold = _DEFAULT_FAILURE_THRESHOLD
            self._cb_durations = _DEFAULT_FREEZE_DURATIONS
            self._cb_reset_hours = _DEFAULT_RESET_WINDOW_HOURS

    # ── 熔断：数据库读写 ──

    def _cb_load_health(self) -> None:
        """从 adapter_health 表加载健康状态。"""
        if self._cb_loaded:
            return
        try:
            from pilotstd.core.config import get_db_path
            from pilotstd.core.db import Database

            db = Database(get_db_path())
            row = db.fetchone(f"SELECT * FROM {_HEALTH_TABLE} WHERE adapter_name=?", (self.site_name,))
            if row:
                self._cb_freeze_count = row["freeze_count"] or 0
                self._cb_fail_streak = row["fail_streak"] or 0
                ft = row["first_freeze_time"]
                fu = row["frozen_until"]
                self._cb_first_freeze_time = datetime.fromisoformat(ft) if ft else None
                self._cb_frozen_until = datetime.fromisoformat(fu) if fu else None
            else:
                now = datetime.now(timezone.utc).isoformat()
                db.execute(
                    f"INSERT INTO {_HEALTH_TABLE} (adapter_name, freeze_count, fail_streak, updated_at) "
                    "VALUES (?, 0, 0, ?)",
                    (self.site_name, now),
                )
            db.close()
            self._cb_loaded = True
        except Exception as e:
            logger.warning("[CB] %s: 加载健康状态失败: %s", self.site_name, e)

    def _cb_save_health(self) -> None:
        """全量保存健康状态到 adapter_health 表。"""
        try:
            from pilotstd.core.config import get_db_path
            from pilotstd.core.db import Database

            now = datetime.now(timezone.utc).isoformat()
            ft = self._cb_first_freeze_time.isoformat() if self._cb_first_freeze_time else None
            fu = self._cb_frozen_until.isoformat() if self._cb_frozen_until else None
            db = Database(get_db_path())
            db.execute(
                f"INSERT OR REPLACE INTO {_HEALTH_TABLE} "
                "(adapter_name, freeze_count, first_freeze_time, frozen_until, fail_streak, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (self.site_name, self._cb_freeze_count, ft, fu, self._cb_fail_streak, now),
            )
            db.close()
        except Exception as e:
            logger.warning("[CB] %s: 保存健康状态失败: %s", self.site_name, e)

    # ── 熔断检查（请求前调用）──

    def _cb_check_frozen(self) -> None:
        """检查是否处于冻结状态。冻结中→抛 AdapterFrozenError。冻结到期→解冻（含24h归零）。"""
        self._cb_load_health()
        if self._cb_frozen_until is None:
            return
        now = datetime.now(timezone.utc)
        if now < self._cb_frozen_until:
            remaining = int((self._cb_frozen_until - now).total_seconds())
            logger.info("[FREEZE] %s 冻结中，剩余 %d 秒", self.site_name, remaining)
            raise AdapterFrozenError(self.site_name, remaining)
        # 触发点B：冻结到期，检查24h窗口归零
        self._cb_frozen_until = None
        if self._cb_first_freeze_time:
            if (now - self._cb_first_freeze_time) >= timedelta(hours=self._cb_reset_hours):
                self._cb_freeze_count = 0
                self._cb_first_freeze_time = None
                logger.info("[THAW] %s 24小时窗口到期，冻结计数归零", self.site_name)
        logger.info("[THAW] %s 冻结到期，已自动解冻", self.site_name)
        self._cb_save_health()

    # ── 成功/失败记录 ──

    def _cb_record_success(self) -> None:
        """请求成功：重置 fail_streak。"""
        self._cb_fail_streak = 0
        self._cb_save_health()

    def _cb_record_failure(self) -> bool:
        """请求失败：累加 fail_streak，达到阈值时触发冻结。返回 True 表示触发了冻结。"""
        self._cb_fail_streak += 1
        self._cb_save_health()
        if self._cb_fail_streak < self._cb_threshold:
            return False
        # 触发点A：即将冻结时检查24h窗口
        now = datetime.now(timezone.utc)
        if self._cb_first_freeze_time:
            if (now - self._cb_first_freeze_time) >= timedelta(hours=self._cb_reset_hours):
                self._cb_freeze_count = 0
                self._cb_first_freeze_time = None
                logger.info("[THAW] %s 24小时窗口到期，冻结计数归零", self.site_name)
        idx = min(self._cb_freeze_count, len(self._cb_durations) - 1)
        duration = self._cb_durations[idx]
        self._cb_freeze_count += 1
        self._cb_frozen_until = now + timedelta(seconds=duration)
        if self._cb_first_freeze_time is None:
            self._cb_first_freeze_time = now
        self._cb_fail_streak = 0
        self._cb_save_health()
        logger.info(
            "[FREEZE] %s 触发冻结，第 %d 次，持续 %d 分钟",
            self.site_name,
            self._cb_freeze_count,
            duration // 60,
        )
        return True

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

    def _parse_items(self, raw_detail: str, ocr_provider: Any = None) -> list[dict[str, Any]]:
        """子类可重写。默认实现：HTML 表格优先，无数据时回退附件。"""
        from .parser import find_attachment_url, parse_announcement_detail

        html_items, meta = parse_announcement_detail(raw_detail, None, "", ocr_provider=ocr_provider)
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
    def _finalize_items(items: list[dict[str, Any]], attachment_url: str) -> list[dict[str, Any]]:
        """为每条标准补默认字段。"""
        for item in items:
            item.setdefault("attachment_url", attachment_url)
            item.setdefault("attachment_path", "")
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
        # 熔断检查
        self._cb_check_frozen()

        try:
            ann_list = self._fetch_list(since_date, page_size)
            if not ann_list:
                self._cb_record_success()
                return []

            # 过滤已完全解析的公告（去重前移：阶段1后、阶段2前检查）
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
                    item.setdefault("announcement_title", ann.get("title", ann.get("code", "")))
                    item["_pid"] = ann.get("pid", "")
                    item["announce_no"] = ann.get("code", "")
                _bump(ann.get("code", "?")[:20])
                return parsed

            with concurrent.futures.ThreadPoolExecutor(max_workers=_MAX_DETAIL_WORKERS) as executor:
                futures = {executor.submit(_process_one, ann): ann for ann in ann_list}
                for future in concurrent.futures.as_completed(futures):
                    try:
                        items.extend(future.result())
                    except Exception:
                        logger.exception("公告处理异常")

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
