# 模块：项目/核心/_聚合器脚本
# 通知智能聚合器—适配层（内部委托新版）
"""单例聚合器：缓冲合并 + 熔断暂停（与 Web 端行为等价）。

内部持有新版 pilotstd.core.notification.aggregate_buffer.NotificationAggregator，
should_show() 转为 push() 调用，_flush 逻辑由新版统一处理。
对外 API 保持向后兼容。
"""

import logging
import secrets
import time
from typing import Any, cast

# 缓冲窗口：0.3 秒内同类通知合并为一条
_BUFFER_WINDOW = 0.3  # 秒
# 计数窗口：30 秒内累计警告/错误数达阈值则触发暂停
_COUNT_WINDOW = 30  # 秒
# 暂停时长：触发暂停后 5 分钟内不弹通知
_PAUSE_DURATION = 300  # 秒 (5分钟)
# 配置键名：暂停状态持久化到配置脚本
_PAUSE_CONFIG_KEY = "notification.aggregation"

logger = logging.getLogger(__name__)


def _log_trace_id() -> str:
    """生成日志结构化上下文用的短随机追踪号（线程安全，无依赖）。"""
    return secrets.token_hex(4)


class NotificationAggregator:
    """通知智能聚合器（单例，适配层）。

    公开 API 保持向后兼容：
      - should_show(level, title, body, on_show) → bool
      - get_pause_state() → {"is_paused": bool, "remaining_seconds": int}
      - resume() → None
      - auto_pause_enabled → bool
      - shutdown() → None  (新增)
    """

    _instance: "NotificationAggregator | None" = None

    def __new__(cls) -> "NotificationAggregator":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        """初始化内部状态：警告计数器、暂停标记、回调引用、新版聚合器。"""
        # 时间戳列表，用于滑动窗口统计/频率
        self._warning_errors: list[float] = []  # 时间戳
        self._paused = False
        self._paused_until: float | None = None
        self._on_show: Any = None  # callback(title, body, level)
        # 从持久化配置恢复暂停状态（服务重启后保留）
        self._load_pause_state()

        # 初始化新版聚合器（线程安全+滑动窗口+_）
        from pilotstd.core.notification.aggregate_buffer import NotificationAggregator as NewAggregator

        self._new = NewAggregator(
            sender_func=self._on_new_flush,
            window_seconds=_BUFFER_WINDOW,
            batch_size=50,
        )

    # ──主题提取（保留，用于设置_）──

    @staticmethod
    def _extract_topic(title: str, _body: str) -> str:
        """从标题提取主题分类，用于新版聚合器的 target_id 分组。"""
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
        # 无法分类时取标题前 8 字符 + _ 前缀，确保不为空
        return "_" + (title[:8] or "default")

    # ── 暂停状态持久化 ──

    def _load_pause_state(self) -> None:
        """从持久化配置恢复暂停状态（服务重启后保留）。"""
        try:
            from pilotstd.core.config.manager import ConfigManager

            cfg = ConfigManager()
            saved = cfg.get(_PAUSE_CONFIG_KEY)
            # 仅当暂停标记为且暂停截止时间未过期时才恢复
            if saved and isinstance(saved, dict):
                if saved.get("paused") and isinstance(saved.get("paused_until"), (int, float)):
                    if saved["paused_until"] > time.time():
                        self._paused = True
                        self._paused_until = saved["paused_until"]
        except Exception:
            # D-3 修复：暂停状态恢复失败需带结构化上下文记录，禁止静默吞错
            logger.warning(
                "聚合器暂停状态恢复失败: trace_id=%s source_type=notification_aggregator target_chat_id=-",
                _log_trace_id(),
                exc_info=True,
            )

    def _save_pause_state(self) -> None:
        """将当前暂停状态持久化到配置文件。"""
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
            # D-3 修复：暂停状态保存失败需带结构化上下文记录，禁止静默吞错
            logger.warning(
                "聚合器暂停状态保存失败: trace_id=%s source_type=notification_aggregator target_chat_id=-",
                _log_trace_id(),
                exc_info=True,
            )

    # ── 暂停计数 ──

    def _clean_warning_errors(self, now: float) -> None:
        """清理超过 _COUNT_WINDOW 秒的旧警告/错误时间戳。"""
        self._warning_errors = [t for t in self._warning_errors if now - t <= _COUNT_WINDOW]

    def _check_pause_trigger(self, level: str) -> bool:
        """检查是否触发暂停。返回 True 表示已触发暂停。"""
        if level in ("warning", "error"):
            now = time.time()
            self._warning_errors.append(now)
            self._clean_warning_errors(now)
            # 30 秒内累计 3 条警告/错误 → 触发 5 分钟暂停
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
                return True
        return False

    # ──新版聚合器回调→桥接到旧版__（线程安全）──

    def _on_new_flush(self, msg: Any, _channels: list[str]) -> None:
        """新版聚合器合并后的回调。

        msg: NotificationMessage（新版数据类）
        1. 通过 format_for_desktop 剥离 Emoji + 截断长度
        2. 优先通过 QTimer.singleShot 回到主线程
        """
        if self._check_pause_trigger(msg.level):
            return

        if not self._on_show:
            return

        from pilotstd.core.notification.desktop_formatter import format_for_desktop

        safe_title, safe_body = format_for_desktop(msg.title, msg.body)

        try:
            from PyQt6.QtCore import QCoreApplication, QTimer

            app = QCoreApplication.instance()
            if app is not None:
                QTimer.singleShot(0, lambda: self._on_show(safe_title, safe_body, msg.level))
                return
        except ImportError:
            pass

        self._on_show(safe_title, safe_body, msg.level)

    # ──公共接口──

    def should_show(self, level: str, title: str, body: str, on_show: Any = None) -> bool:
        """判断是否应显示通知。委托新版聚合器处理缓冲合并。

        on_show: 实际显示回调 (title, body, level)。
        返回 False：通知已入队，聚合后通过 on_show 输出。
        """
        if on_show is not None:
            self._on_show = on_show

        # 暂停期间静默吞掉所有通知
        if self._paused:
            if self._paused_until and time.time() >= self._paused_until:
                # 暂停已过期，自动恢复
                self._paused = False
                self._paused_until = None
                self._save_pause_state()
            else:
                return False

        # 提取主题作为_，复用新版的分组能力
        topic = self._extract_topic(title, body)
        status = "failure" if level in ("warning", "error") else "success"

        self._new.push(
            event_type="desktop_toast",
            title=title,
            content=body,
            level=level,
            target_id=topic,
            status=status,
        )
        # 始终返回：通知不立即显示，由聚合器合并后统一推送
        return False

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

    def shutdown(self) -> None:
        """优雅关闭：刷新新版聚合器中所有缓冲消息（防止丢失）。"""
        self._new.shutdown()

    @property
    def auto_pause_enabled(self) -> bool:
        """读取 notification.auto_pause 配置，控制是否启用自动暂停。"""
        try:
            from pilotstd.core.config.manager import ConfigManager

            return cast(bool, ConfigManager().get("notification.auto_pause", True))
        except Exception:
            return True
