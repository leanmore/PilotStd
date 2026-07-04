# pilotstd/core/notification_aggregator.py
# 通知智能聚合器 — 缓冲合并 + 熔断暂停（与 Web 端行为等价）
"""单例聚合器：缓冲 300ms → 按主题合并 → 30s 窗口内 3 次 warning/error 触发 5min 暂停。"""

import time
from threading import Timer
from typing import Any

_BUFFER_WINDOW = 0.3  # 秒
_COUNT_WINDOW = 30  # 秒
_PAUSE_DURATION = 300  # 秒 (5分钟)
_PAUSE_CONFIG_KEY = "notification.aggregation"


class NotificationAggregator:
    """通知智能聚合器（单例，与 Web 端 useNotificationAggregator 行为等价）。"""

    _instance: "NotificationAggregator | None" = None

    def __new__(cls) -> "NotificationAggregator":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        self._buffer: list[dict[str, Any]] = []
        self._warning_errors: list[float] = []  # 时间戳
        self._paused = False
        self._paused_until: float | None = None
        self._timer: Timer | None = None
        self._on_show: Any = None  # callback(title, body, level)
        self._load_pause_state()

    # ── 主题提取 ──

    @staticmethod
    def _extract_topic(title: str, _body: str) -> str:
        lowered = title.lower()
        if any(k in lowered for k in ("完成", "成功")):
            return "done"
        if any(k in lowered for k in ("失败", "异常", "错误")):
            return "error"
        if "扫描" in lowered:
            return "scan"
        if "下载" in lowered:
            return "download"
        if "归档" in lowered:
            return "archive"
        if "查询" in lowered:
            return "query"
        if "备份" in lowered:
            return "backup"
        if "公告" in lowered:
            return "announce"
        if any(k in lowered for k in ("更新", "镜像")):
            return "update"
        if "ip" in lowered:
            return "ip"
        return "_" + (title[:8] or "default")

    # ── 暂停状态持久化 ──

    def _load_pause_state(self) -> None:
        try:
            from pilotstd.core.config.manager import ConfigManager

            cfg = ConfigManager()
            saved = cfg.get(_PAUSE_CONFIG_KEY)
            if saved and isinstance(saved, dict):
                if saved.get("paused") and isinstance(saved.get("paused_until"), (int, float)):
                    if saved["paused_until"] > time.time():
                        self._paused = True
                        self._paused_until = saved["paused_until"]
        except Exception:
            pass

    def _save_pause_state(self) -> None:
        try:
            from pilotstd.core.config.manager import ConfigManager

            cfg = ConfigManager()
            cfg.set(
                _PAUSE_CONFIG_KEY,
                {
                    "paused": self._paused,
                    "paused_until": self._paused_until,
                },
            )
            cfg.save()
        except Exception:
            pass

    # ── 滑动窗口清理 ──

    def _clean_warning_errors(self, now: float) -> None:
        self._warning_errors = [t for t in self._warning_errors if now - t <= _COUNT_WINDOW]

    # ── 合并输出 ──

    def _flush(self) -> None:
        self._timer = None
        if not self._buffer:
            return

        now = time.time()
        groups: dict[str, list[dict]] = {}
        for item in self._buffer:
            topic = self._extract_topic(item["title"], item["body"])
            groups.setdefault(topic, []).append(item)

        for topic, items in groups.items():
            if len(items) == 1:
                title = items[0]["title"]
                body = items[0]["body"]
                level = items[0]["level"]
            elif topic == "done":
                title = f"{len(items)} 项任务已完成"
                body = "\n".join(f"· {i['title']}" for i in items)
                level = "info"
            elif topic == "error":
                title = f"{len(items)} 项操作出现异常"
                body = "\n".join(f"· {i['title']}" for i in items)
                level = "warning"
            else:
                title = f"{len(items)} 条 {topic} 相关通知"
                body = "\n".join(f"· {i['title']}" for i in items)
                level = items[0]["level"]

            if level in ("warning", "error"):
                self._warning_errors.append(now)
                self._clean_warning_errors(now)
                if len(self._warning_errors) >= 3:
                    self._paused = True
                    self._paused_until = now + _PAUSE_DURATION
                    self._save_pause_state()
                    if self._on_show:
                        self._on_show(
                            "通知已暂停",
                            f"连续 {len(self._warning_errors)} 次警告，通知将在 5 分钟后自动恢复",
                            "warning",
                        )
                    return

            if self._on_show:
                self._on_show(title, body, level)

        self._buffer.clear()

    # ── 公共 API ──

    def should_show(self, level: str, title: str, body: str, on_show: Any = None) -> bool:
        """判断是否应显示通知。缓冲 300ms 后按主题合并输出。
        若暂停中或已缓冲暂未输出 → 返回 False。
        on_show: 实际显示回调 (title, body, level)。"""
        self._on_show = on_show

        if self._paused:
            if self._paused_until and time.time() >= self._paused_until:
                self._paused = False
                self._paused_until = None
                self._save_pause_state()
            else:
                return False

        self._buffer.append(
            {
                "level": level,
                "title": title,
                "body": body,
                "timestamp": time.time(),
            }
        )

        if not self._timer:
            self._timer = Timer(_BUFFER_WINDOW, self._flush)
            self._timer.daemon = True
            self._timer.start()

        return False  # 总是等待缓冲窗口结束再显示

    def get_pause_state(self) -> dict:
        """返回 {"is_paused": bool, "remaining_seconds": int}。"""
        if not self._paused or not self._paused_until:
            return {"is_paused": False, "remaining_seconds": 0}
        remaining = max(0, int(self._paused_until - time.time()))
        return {"is_paused": True, "remaining_seconds": remaining}

    def resume(self) -> None:
        """手动恢复通知。"""
        self._paused = False
        self._paused_until = None
        self._save_pause_state()

    @property
    def auto_pause_enabled(self) -> bool:
        try:
            from pilotstd.core.config.manager import ConfigManager

            return ConfigManager().get("notification.auto_pause", True)
        except Exception:
            return True
