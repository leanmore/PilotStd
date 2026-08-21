# 模块：项目//__脚本
# 适配器熔断器—从脚本拆分，组合模式（非）

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, cast

from pilotstd.core.config import ConfigManager, get_db_path
from pilotstd.core.db import Database

logger = logging.getLogger(__name__)

# ── 默认参数 ──
_DEFAULT_FREEZE_DURATIONS = [1800, 7200, 21600, 43200]  # 秒：30m/2h/6h/12h
_DEFAULT_FAILURE_THRESHOLD = 3
_DEFAULT_RESET_WINDOW_HOURS = 24
_HEALTH_TABLE = "adapter_state"


class AdapterFrozenError(Exception):
    """适配器处于冻结状态，请求被熔断拦截。"""

    def __init__(self, adapter_name: str, remaining_seconds: int) -> None:
        self.adapter_name = adapter_name
        self.remaining_seconds = remaining_seconds
        super().__init__(f"{adapter_name} 冻结中，剩余 {remaining_seconds} 秒")


class CircuitBreaker:
    """适配器熔断器：阈值检测 + 指数退避冻结 + 24h 窗口归零。

    组合到 BaseAnnounceCrawler 中，通过 _get_site_name 回调获取站点名。
    """

    def __init__(self, get_site_name) -> None:
        self._get_site_name = get_site_name
        self.freeze_count: int = 0
        self.first_freeze_time: Optional[datetime] = None
        self.frozen_until: Optional[datetime] = None
        self.fail_streak: int = 0
        self._loaded: bool = False

    @property
    def _site(self) -> str:
        return cast(str, self._get_site_name())

    # ──配置（实时读取，支持热加载）──

    @property
    def _threshold(self) -> int:
        try:
            v = ConfigManager().get("adapter.circuit_breaker.failure_threshold")
            return v if v is not None else _DEFAULT_FAILURE_THRESHOLD
        except Exception:
            return _DEFAULT_FAILURE_THRESHOLD

    @property
    def _durations(self) -> list[int]:
        try:
            durations = ConfigManager().get("adapter.circuit_breaker.freeze_durations")
            if durations and isinstance(durations, list) and len(durations) > 0:
                return [int(m) * 60 for m in durations]
        except Exception:
            pass
        return list(_DEFAULT_FREEZE_DURATIONS)

    @property
    def _reset_hours(self) -> int:
        try:
            v = ConfigManager().get("adapter.circuit_breaker.reset_window_hours")
            return v if v is not None else _DEFAULT_RESET_WINDOW_HOURS
        except Exception:
            return _DEFAULT_RESET_WINDOW_HOURS

    # ── 数据库读写 ──

    def load_health(self) -> None:
        """从 adapter_health 表加载健康状态。"""
        if self._loaded:
            return
        try:
            db = Database(get_db_path())
            row = db.fetchone(f"SELECT * FROM {_HEALTH_TABLE} WHERE adapter_name=?", (self._site,))
            if row:
                self.freeze_count = row["freeze_count"] or 0
                self.fail_streak = row["fail_streak"] or 0
                ft = row["first_freeze_time"]
                fu = row["frozen_until"]
                self.first_freeze_time = datetime.fromisoformat(ft) if ft else None
                self.frozen_until = datetime.fromisoformat(fu) if fu else None
            else:
                now = datetime.now(timezone.utc).isoformat()
                db.execute(
                    f"INSERT INTO {_HEALTH_TABLE} (adapter_name, freeze_count, fail_streak, updated_at) "
                    "VALUES (?, 0, 0, ?)",
                    (self._site, now),
                )
            db.close()
            self._loaded = True
        except Exception as e:
            logger.warning("[CB] %s: 加载健康状态失败: %s", self._site, e)

    def save_health(self) -> None:
        """全量保存健康状态到 adapter_state 表（UPSERT，仅更新公告侧字段组）。"""
        try:
            now = datetime.now(timezone.utc).isoformat()
            ft = self.first_freeze_time.isoformat() if self.first_freeze_time else None
            fu = self.frozen_until.isoformat() if self.frozen_until else None
            db = Database(get_db_path())
            db.execute(
                f"INSERT INTO {_HEALTH_TABLE} "
                "(adapter_name, freeze_count, first_freeze_time, frozen_until, fail_streak, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(adapter_name) DO UPDATE SET "
                "freeze_count = excluded.freeze_count, "
                "first_freeze_time = excluded.first_freeze_time, "
                "frozen_until = excluded.frozen_until, "
                "fail_streak = excluded.fail_streak, "
                "updated_at = excluded.updated_at",
                (self._site, self.freeze_count, ft, fu, self.fail_streak, now),
            )
            db.close()
        except Exception as e:
            logger.warning("[CB] %s: 保存健康状态失败: %s", self._site, e)

    # ── 熔断检查（请求前调用）──

    def check_frozen(self) -> None:
        """检查是否处于冻结状态。冻结中→抛 AdapterFrozenError。冻结到期→解冻。"""
        self.load_health()
        if self.frozen_until is None:
            return
        now = datetime.now(timezone.utc)
        if now < self.frozen_until:
            remaining = int((self.frozen_until - now).total_seconds())
            logger.info("[FREEZE] %s 冻结中，剩余 %d 秒", self._site, remaining)
            raise AdapterFrozenError(self._site, remaining)
        self.frozen_until = None
        if self.first_freeze_time:
            if (now - self.first_freeze_time) >= timedelta(hours=self._reset_hours):
                self.freeze_count = 0
                self.first_freeze_time = None
                logger.info("[THAW] %s 24小时窗口到期，冻结计数归零", self._site)
        logger.info("[THAW] %s 冻结到期，已自动解冻", self._site)
        self.save_health()

    # ── 成功/失败记录 ──

    def record_success(self) -> None:
        """请求成功：重置 fail_streak。"""
        self.fail_streak = 0
        self.save_health()

    def record_failure(self) -> bool:
        """请求失败：累加 fail_streak，达到阈值时触发冻结。返回 True 表示触发了冻结。"""
        self.fail_streak += 1
        self.save_health()
        if self.fail_streak < self._threshold:
            return False
        now = datetime.now(timezone.utc)
        if self.first_freeze_time:
            if (now - self.first_freeze_time) >= timedelta(hours=self._reset_hours):
                self.freeze_count = 0
                self.first_freeze_time = None
                logger.info("[THAW] %s 24小时窗口到期，冻结计数归零", self._site)
        idx = min(self.freeze_count, len(self._durations) - 1)
        duration = self._durations[idx]
        self.freeze_count += 1
        self.frozen_until = now + timedelta(seconds=duration)
        if self.first_freeze_time is None:
            self.first_freeze_time = now
        self.fail_streak = 0
        self.save_health()
        logger.info(
            "[FREEZE] %s 触发冻结，第 %d 次，持续 %d 分钟",
            self._site,
            self.freeze_count,
            duration // 60,
        )
        return True
