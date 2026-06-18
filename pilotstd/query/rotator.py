# pilotstd/query/rotator.py
# 查询网站轮转冷却机制：限流保护、故障冷却、备用地址切换

import time
import logging
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# 站点冷却默认时长（秒）
DEFAULT_COOLDOWN_SECONDS = 600   # 10 分钟
# 等待冷却恢复的最大超时（秒）
WAIT_FOR_RECOVERY_TIMEOUT = 900  # 15 分钟


@dataclass
class SiteState:
    """单个查询网站的运行状态。"""
    name: str                          # 网站标识（如 csres）
    base_url: str                      # 主URL
    fallback_urls: List[str] = field(default_factory=list)  # 备用URL
    max_requests: int = 200            # 每轮冷却前最大请求数
    daily_limit: int = 800             # 每日最大请求数（次日凌晨自动重置）
    cooldown_seconds: int = 600        # 冷却时长（10分钟）
    request_count: int = 0             # 当前轮次请求计数（冷却后归零）
    daily_count: int = 0               # 当日累计请求数
    daily_date: str = ""               # 日计数器日期（YYYY-MM-DD，跨天自动重置）
    cooldown_until: float = 0.0        # 冷却到期时间戳
    consecutive_errors: int = 0        # 连续错误计数
    active_url: str = ""               # 当前使用的URL

    def __post_init__(self):
        if not self.active_url:
            self.active_url = self.base_url


class SiteRotator:
    """管理多个查询网站的轮转调度。

    规则：
    1. 按优先级顺序尝试各站点
    2. 单站达到 max_requests 后进入冷却（cooldown_seconds）
    3. 连续 3 次错误自动切换备用 URL
    4. 备用 URL 全部失败则该站进入冷却
    5. 冷却期间跳过该站，到期自动恢复
    """

    def __init__(self, sites: List[SiteState] = None, db=None):
        self._lock = threading.Lock()
        self._sites: Dict[str, SiteState] = {}
        self._last_cooldown_log: Dict[str, float] = {}  # 冷却日志节流
        self._was_cooling: Dict[str, bool] = {}  # 追踪冷却退出
        self._db = db  # 可选：数据库实例，用于持久化冷却状态
        if sites:
            for s in sites:
                self._sites[s.name] = s
        # 从数据库恢复上次冷却状态（跨进程共享）
        if db:
            self._load(db)

    def register(self, site: SiteState) -> None:
        with self._lock:
            self._sites[site.name] = site

    @staticmethod
    def _today() -> str:
        """返回当天日期字符串 YYYY-MM-DD，用于日计数器重置判断。"""
        return time.strftime("%Y-%m-%d")

    @staticmethod
    def _check_daily_reset(site: SiteState) -> None:
        """跨天自动重置日计数器。"""
        today = SiteRotator._today()
        if site.daily_date != today:
            site.daily_count = 0
            site.daily_date = today

    def get_available(self, priority_order: List[str]) -> List[str]:
        """返回当前可用站点列表（按优先级排序，跳过冷却/日限达标的站点）。"""
        with self._lock:
            now = time.time()
            available = []
            for name in priority_order:
                site = self._sites.get(name)
                if site is None:
                    available.append(name)
                    continue
                # 日上限检查——到上限后当天不再使用
                self._check_daily_reset(site)
                if site.daily_limit > 0 and site.daily_count >= site.daily_limit:
                    logger.info("[QUOTA] site=%s action=daily_exhausted daily_count=%d daily_limit=%d",
                                name, site.daily_count, site.daily_limit)
                    continue
                # 检测冷却退出
                was_cooling = self._was_cooling.get(name, False)
                if site.cooldown_until > 0 and now < site.cooldown_until:
                    remaining = site.cooldown_until - now
                    last_log = self._last_cooldown_log.get(name, 0)
                    if now - last_log >= 60:
                        logger.info("[COOLDOWN] site=%s action=status remaining_s=%.0f cooldown_s=%d",
                                    name, remaining, site.cooldown_seconds)
                        self._last_cooldown_log[name] = now
                    self._was_cooling[name] = True
                    continue
                if site.cooldown_until > 0 and now >= site.cooldown_until:
                    # 冷却已到期，自动恢复
                    duration = now - (site.cooldown_until - site.cooldown_seconds)
                    site.cooldown_until = 0.0
                    site.request_count = 0
                    self._was_cooling[name] = False
                    logger.info("[COOLDOWN] site=%s action=exit duration_s=%.0f cooldown_configured_s=%d",
                                name, duration, site.cooldown_seconds)
                elif was_cooling and site.cooldown_until == 0:
                    # 冷却被 reset_all_cooldowns 或其他方式清零
                    self._was_cooling[name] = False
                if site.request_count >= site.max_requests:
                    self._enter_cooldown(site)
                    self._save()
                    logger.info("[COOLDOWN] site=%s action=enter reason=max_requests "
                                "request_count=%d max_requests=%d cooldown_s=%d daily_count=%d daily_limit=%d",
                                name, site.request_count, site.max_requests,
                                site.cooldown_seconds, site.daily_count, site.daily_limit)
                    self._was_cooling[name] = True
                    continue
                self._was_cooling[name] = False
                available.append(name)
            return available

    def record_success(self, name: str) -> None:
        with self._lock:
            site = self._sites.get(name)
            if site:
                self._check_daily_reset(site)
                site.request_count += 1
                site.daily_count += 1
                site.consecutive_errors = 0
                # 里程碑日志：50%/75%/90% 阈值
                pct = site.request_count / site.max_requests if site.max_requests else 0
                if pct >= 0.9 or (site.max_requests > 0 and
                                   site.request_count in (site.max_requests // 2,
                                                          site.max_requests * 3 // 4)):
                    logger.info("[ROTATOR] site=%s request_count=%d/%d (%.0f%%) "
                                "daily_count=%d/%d",
                                name, site.request_count, site.max_requests,
                                pct * 100, site.daily_count, site.daily_limit)

    def record_error(self, name: str) -> Optional[str]:
        """记录一次错误。返回切换后的新 URL（如有），或 None。"""
        with self._lock:
            site = self._sites.get(name)
            if not site:
                return None
            self._check_daily_reset(site)
            site.consecutive_errors += 1
            site.request_count += 1
            site.daily_count += 1

            if site.consecutive_errors >= 3:
                if site.fallback_urls:
                    new_url = site.fallback_urls.pop(0)
                    site.active_url = new_url
                    site.consecutive_errors = 0
                    site.fallback_urls.append(site.base_url)  # 原URL作为最后的回退
                    site.base_url = new_url
                    logger.warning("[ROTATOR] site=%s action=switch_url url=%s",
                                   name, new_url)
                    return new_url
                else:
                    self._enter_cooldown(site)
                    self._save()
                    logger.warning("[COOLDOWN] site=%s action=enter reason=error_threshold "
                                   "request_count=%d max_requests=%d cooldown_s=%d "
                                   "consecutive_errors=%d",
                                   name, site.request_count, site.max_requests,
                                   site.cooldown_seconds, site.consecutive_errors)
                    return new_url
            return None

    def force_cooldown(self, name: str, seconds: int = DEFAULT_COOLDOWN_SECONDS) -> None:
        """强制进入冷却（如检测到被网站拒绝）。已在冷却中则跳过。"""
        with self._lock:
            site = self._sites.get(name)
            if site:
                now = time.time()
                if site.cooldown_until > now:
                    return  # 已在冷却中，跳过重复触发
                site.cooldown_until = now + seconds
                site.request_count = 0
                site.consecutive_errors = 0
                self._save()  # 持久化冷却状态
                logger.info("[COOLDOWN] site=%s action=enter reason=forced cooldown_s=%d",
                            name, seconds)

    def all_in_cooldown(self, priority_order: List[str]) -> bool:
        with self._lock:
            now = time.time()
            for name in priority_order:
                site = self._sites.get(name)
                if site is None:
                    return False
                if site.cooldown_until == 0 or now >= site.cooldown_until:
                    return False
            return True

    def wait_for_any_recovery(self, priority_order: List[str], timeout: int = WAIT_FOR_RECOVERY_TIMEOUT) -> bool:
        """阻塞等待任一站点冷却恢复，最长 timeout 秒。返回 True=有站点恢复。"""
        import time as _time
        deadline = _time.time() + timeout
        while _time.time() < deadline:
            now = _time.time()
            with self._lock:
                for name in priority_order:
                    site = self._sites.get(name)
                    if site and (site.cooldown_until == 0 or now >= site.cooldown_until):
                        return True
            _time.sleep(5)
        return False

    def list_sites(self) -> list:
        """返回所有已知站点名称列表。"""
        with self._lock:
            return list(self._sites.keys())

    def reset_all_cooldowns(self) -> None:
        """重置所有站点冷却状态（测试用）。"""
        with self._lock:
            for site in self._sites.values():
                site.cooldown_until = 0.0
                site.request_count = 0
                site.consecutive_errors = 0
            # 也清理数据库中的冷却记录
            if self._db:
                try:
                    self._db.execute("DELETE FROM rotator_state")
                except Exception:
                    pass
        logger.info("所有站点冷却已重置")

    def get_cooldown_remaining(self, name: str) -> float:
        """返回站点剩余冷却秒数，0=不在冷却中。"""
        with self._lock:
            site = self._sites.get(name)
            if not site or site.cooldown_until == 0:
                return 0.0
            remaining = site.cooldown_until - time.time()
            return max(0.0, remaining)

    @staticmethod
    def _enter_cooldown(site: SiteState) -> None:
        site.cooldown_until = time.time() + site.cooldown_seconds
        site.request_count = 0
        site.consecutive_errors = 0

    def _save(self, db=None) -> None:
        """持久化所有站点冷却状态到数据库。"""
        target = db or self._db
        if not target:
            return
        try:
            for name, site in self._sites.items():
                target.execute(
                    "INSERT OR REPLACE INTO rotator_state "
                    "(site_name, request_count, daily_count, daily_date, cooldown_until, consecutive_errors, active_url, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))",
                    (name, site.request_count, site.daily_count, site.daily_date,
                     site.cooldown_until, site.consecutive_errors, site.active_url))
        except Exception:
            logger.warning("持久化站点冷却状态时出错", exc_info=True)

    def _load(self, db) -> None:
        """从数据库恢复冷却状态（仅恢复仍在冷却期内的状态）。"""
        try:
            rows = db.fetchall("SELECT * FROM rotator_state")
        except Exception:
            logger.debug("冷却状态恢复跳过", exc_info=True)
            return  # 表不存在或查询失败，跳过恢复
        now = time.time()
        for row in rows:
            name = row["site_name"]
            if name in self._sites:
                site = self._sites[name]
                # 恢复日计数（跨天自动失效）
                daily_date = row.get("daily_date", "")
                if daily_date == self._today():
                    site.daily_count = row.get("daily_count", 0)
                    site.daily_date = daily_date
                if row["cooldown_until"] > now:
                    site.cooldown_until = row["cooldown_until"]
                else:
                    # 冷却已过期，request_count 清零
                    site.request_count = 0
                    continue
                site.request_count = row["request_count"]
                site.consecutive_errors = row["consecutive_errors"] if row["cooldown_until"] > now else 0
                if row["active_url"]:
                    site.active_url = row["active_url"]
