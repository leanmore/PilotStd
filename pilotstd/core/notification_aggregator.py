# 模块：项目/核心/_聚合器脚本
# 通知智能聚合器—适配层（内部委托新版）
"""桌面端通知聚合适配层（单例）：主题分组 + 熔断暂停（与 Web 端行为等价）。

职责边界（三套通知聚合/去重机制之一，禁止越界）：
- **本模块负责**：PyQt 桌面**托盘通知**的暂停/恢复决策、自动暂停触发（30 秒内累计
  3 条警告/错误 → 暂停 5 分钟）、暂停状态持久化，以及把通知**桥接**给服务端聚合器。
- **主题分组**：`_extract_topic(title, body)` 把标题映射为主题串（如 `scan`/`download`/
  `archive`），作为 `target_id` 传入服务端聚合器——这是桌面链路的实体标识来源。
- **本模块不负责**：实际的消息合并（委托 `notification/aggregate_buffer`）、
  渠道适配与发送、静音时段判断。
- **与 `notification/aggregate_buffer.NotificationAggregator` 的关系**：**独立链路、不共享状态**。
  本模块服务 `platform/notify.py` 触发的桌面托盘通知；后者服务 `manager.send_event`
  触发的服务端通知（Web / Webhook / 定时任务）。两者仅通过"持有实例并委托 `push()`"相连。

内部持有新版 pilotstd.core.notification.aggregate_buffer.NotificationAggregator，
should_show() 转为 push() 调用，_flush 逻辑由新版统一处理。
对外 API 保持向后兼容。
"""

import logging
import re
import secrets
import time
from typing import Any, cast

# 缓冲窗口：0.3 秒内同类通知合并为一条
# 设计意图（专项确认，不变更）：这是**桌面托盘气泡**的分组窗口，与服务端聚合器的
# `DEFAULT_WINDOW_SECONDS = 5.0s` 分属两条独立链路（见模块 docstring）。语义不同——
# 桌面要"两条 toast 几乎同时出现就并一条"，0.3s 足够；服务端要"5 秒内的事件合成
# 摘要后投递到 webhook"，需要更长。故本值不进 config，也不与 5.0s 对齐。
_BUFFER_WINDOW = 0.3  # 秒
# 计数窗口：30 秒内累计警告/错误数达阈值则触发暂停
_COUNT_WINDOW = 30  # 秒
# 暂停时长：触发暂停后 5 分钟内不弹通知
_PAUSE_DURATION = 300  # 秒 (5分钟)
# 配置键名：暂停状态持久化到配置脚本
_PAUSE_CONFIG_KEY = "notification.aggregation"

# ── 主题分组映射（i18n 契约驱动，专项修复）──
# 原实现用**简体中文关键词**猜测主题，导致繁中/英文标题全部落到"标题前 8 字符"
# 兜底分支——同一事件在不同语言下归入不同分组，跨语言完全不合并，且分组数随
# 标题数无界增长（实测三语下 65 条落兜底）。
#
# 修法：以 i18n 中的**真实标题**为契约。`notification.*` 的 47 个 `.title*` 键
# 经实测**全部可映射到事件**（39/39，唯一例外 `notification.channel.test.title`
# 不属任何事件），故把标题渲染值与事件的对应关系固化为映射表，用**准确匹配**
# 取代关键词猜测。事件 → 主题再由 `_TOPIC_BY_EVENT` 显式给出。
#
# **实际生效范围（实测）**：`_extract_topic` 在全库只有一个调用点（本模块
# `should_show`），而平台层调用方 `ui/core/handlers/_download.py` 传的是
# `_("download_results_title")` 这类**静态键**，其返回值随 UI 语言变化。因此本修复
# 的现实收益是：**UI 切到繁体/英文后，桌面 toast 的主题分组重新正确**——此前那些
# 标题一律落兜底、每个标题各成一组。含占位符的动态标题（如
# `Scan Complete ({failed} unrecognized)`）当前桌面链路并不产生，模板正则属
# **防御性覆盖**，为将来把含动态计数的标题接入桌面通知预留。
_TOPIC_BY_EVENT: dict[str, str] = {
    # 完成/成功类
    "scan_complete": "done",
    "batch_download_complete": "done",
    "archive_complete": "done",
    "normalize_complete": "done",
    "announcement_fetch_complete": "done",
    "announce_fetch_summary": "done",
    "download_complete": "done",
    "auto_backup": "backup",
    "notification_credential_changed": "done",
    "security_password_changed": "done",
    "security_token_refreshed": "done",
    # 失败/异常类
    "auto_scan_failed": "error",
    "validity_standard_failed": "error",
    "validity_system_failed": "error",
    "worker_error": "error",
    "download_failed": "error",
    "archive_abandoned": "error",
    "task_execution_failed": "error",
    "query_failed": "error",
    "archive_failed": "error",
    "announcement_fetch_failed": "error",
    "normalize_failed": "error",
    "security_login_failed": "error",
    # 领域类：跨语言稳定归组（避免同一事件因语言不同而分裂）
    "scan_empty": "scan",
    "batch_query_summary": "query",
    "query_empty": "query",
    "date_reminder": "validity",
    "validity_batch_report": "validity",
    "validity_round_summary": "validity",
    "image_update_available": "update",
    "trust_ip_update": "ip",
    "standard_status_changed": "validity",
    "standard_first_registered": "validity",
    "expire_standard_moved": "validity",
    "replacement_not_found": "validity",
    "quota_exhausted": "validity",
    "favorite_created": "download",
    "download_started": "download",
    "announcement_check_complete": "announce",
}

# 回退关键词（仅当标题不在 i18n 标题索引中时使用，如自定义/截断标题）。
# 保留原简体词表**及其原始顺序**以维持向后兼容——顺序即优先级，`done`/`error`
# 在前，与原实现一致，避免既有分组行为漂移。
_LEGACY_TOPIC_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("done", ("完成", "成功")),
    ("error", ("失败", "异常", "错误")),
    ("scan", ("扫描",)),
    ("download", ("下载",)),
    ("archive", ("归档",)),
    ("query", ("查询",)),
    ("backup", ("备份",)),
    ("announce", ("公告",)),
    ("update", ("更新", "镜像")),
    ("ip", ("ip",)),
)

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
    # 主题索引缓存（进程级）：(精确匹配表, 模板正则表)；三语标题固定，无需失效逻辑
    _title_index_cache: "tuple[dict[str, str], list[tuple[re.Pattern[str], str]]] | None" = None

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
    def _escape_with_placeholders(text: str, *, optional_placeholder: bool = False) -> str:
        """把片段中的 `{name}` 换成通配，其余字面量 `re.escape` 转义。

        `optional_placeholder=True` 时占位符用 `(.*?)`（允许空值），否则用 `(.+?)`。
        括号内需要宽松匹配：渲染器在取值为空时会产出 `Scan Complete ()` 这类空括号。
        """
        wildcard = "(.*?)" if optional_placeholder else "(.+?)"
        out: list[str] = []
        for part in re.split(r"(\{[^}]*\})", text):
            if not part:
                continue
            if part.startswith("{") and part.endswith("}"):
                out.append(wildcard)
            else:
                out.append(re.escape(part))
        return "".join(out)

    @staticmethod
    def _template_to_patterns(template: str) -> list[str]:
        """把含 `{name}` 占位符的 i18n 模板转为**一个或两个**正则源码。

        规则：
        1. 占位符 → 通配（括号内允许空值，括号外要求非空）；其余字面量转义；
        2. 含占位符的括号组额外生成一个**括号整段去掉**的变体。

        规则 2 的必要性（实测边界）：占位符取空串时渲染器会把括号内字面量一并省略，
        产出 `Scan Complete ()`，其内容不含 `unrecognized`；"括号去掉"的变体
        （`Scan Complete`）可命中该形态。

        单独出现的占位符（如 `第 {round} 轮…`）只生成一个正则——它为空即标题本身
        为空，不应归入任何主题。
        """
        split = re.split(r"([（(][^（()）]*\{[^}]*\}[^（()）]*[)）])", template)
        if len(split) == 1:
            return [NotificationAggregator._escape_with_placeholders(template)]

        complete: list[str] = []
        without: list[str] = []
        for part in split:
            if not part:
                continue
            if part[0] in "(（" and part[-1] in ")）":
                inner = NotificationAggregator._escape_with_placeholders(
                    part[1:-1], optional_placeholder=True
                )
                complete.append(re.escape(part[0]) + inner + re.escape(part[-1]))
            else:
                escaped = NotificationAggregator._escape_with_placeholders(part)
                complete.append(escaped)
                without.append(escaped)

        patterns = ["".join(complete)]
        stripped = "".join(without)
        if stripped and stripped != patterns[0]:
            patterns.append(stripped)
        return patterns

    @staticmethod
    def _strip_bracketed(title: str) -> str:
        """剔除标题中成对括号（含全角）包裹的整段内容，并折叠空白。

        用于动态计数标题：`Scan Complete (3 unrecognized)` -> `Scan Complete`。
        用逐字符扫描求配对（而非正则）——实测标题存在**嵌套括号**，
        非贪婪正则无法可靠匹配。
        """
        chars: list[str] = []
        depth = 0
        for ch in title:
            if ch in "(（":
                depth += 1
                continue
            if ch in ")）":
                depth = max(0, depth - 1)
                continue
            if depth == 0:
                chars.append(ch)
        return re.sub(r"\s+", " ", "".join(chars)).strip()

    @staticmethod
    def _compile_index() -> tuple[dict[str, str], list[tuple[re.Pattern[str], str]]]:
        """构建主题索引，返回 (精确匹配表, 模板正则表)。

        做法：扫 `pilotstd/i18n/*.json`，取 `notification.*` 下所有含 `.title` 的键，
        用**事件名**判定归属事件（键名中必然含事件名，实测 39/39 可映射），再经
        `_TOPIC_BY_EVENT` 得到主题。三语标题全部登记，故索引与"当前语言"无关。

        **为何跨语言建索引**：若只登记当前语言，用户切语言后索引即失效、退回关键词
        猜测。跨语言索引把"语言"从判定中彻底移除——同一事件在三语下得到同一主题。

        **为何需要模板正则**：含占位符的标题（如 `第 {round} 轮…`）实际投递时已被
        替换为具体值，与模板字面不相等，且不存在固定"规范化共同形"（轮次本身即变量），
        故用模板生成正则做模式匹配。
        """
        import json
        import os

        from pilotstd.core.notification.events import ALL_EVENTS

        event_names = {e.key for e in ALL_EVENTS}
        index: dict[str, str] = {}
        patterns: list[tuple[re.Pattern[str], str]] = []
        # 冲突检测：同一标题字面若被推导出**不同主题**，说明事件→主题映射有问题
        # （重复标题本身无害，仅当主题不一致时才是缺陷）。构建时即告警，
        # 不依赖测试——否则未来新增标题可能被 setdefault 静默忽略。
        conflicts: dict[str, set[str]] = {}
        base = os.path.join(os.path.dirname(__file__), "..", "i18n")
        for lang in ("zh_CN", "zh_TW", "en"):
            path = os.path.join(base, f"{lang}.json")
            try:
                with open(path, "r", encoding="utf-8") as f:
                    pack = json.load(f)
            except (OSError, ValueError):
                logger.warning("主题索引：语言包读取失败，跳过 %s", path, exc_info=True)
                continue
            for key, value in pack.items():
                if not (key.startswith("notification.") and ".title" in key):
                    continue
                if not isinstance(value, str) or not value:
                    continue
                owner = next((e for e in event_names if e in key.split(".")), None)
                topic = _TOPIC_BY_EVENT.get(owner or "")
                if not topic:
                    continue
                # 同一标题可能被多个事件共用（实测 1 例，同属 announce）——
                # 保留先登记者，但若推导出的主题**不一致**则记入冲突并告警。
                previous = index.get(value)
                if previous is None:
                    index[value] = topic
                elif previous != topic:
                    conflicts.setdefault(value, {previous}).add(topic)
                if "{" in value:
                    for source in NotificationAggregator._template_to_patterns(value):
                        try:
                            patterns.append((re.compile(source), topic))
                        except re.error:
                            logger.warning("主题索引：模板正则编译失败，跳过 %r", value, exc_info=True)
        if conflicts:
            logger.warning(
                "主题索引存在冲突（同一标题归属多个主题），已保留先登记者: %s",
                {k: sorted(v) for k, v in conflicts.items()},
            )
        return index, patterns

    @classmethod
    def _extract_topic(cls, title: str, _body: str) -> str:
        """从标题提取主题分类，用于新版聚合器的 target_id 分组。

        判定顺序（逐层收窄）：
        1. **精确匹配**：标题等于某 i18n 标题字面（绝大多数事件）；
        2. **括号剔除后匹配**：标题含动态计数（`Scan Complete (3 unrecognized)`）；
        3. **模板正则匹配**：标题含裸值型占位符（`第 3 轮有效性汇总报告`）；
        4. **关键词回退**：非 i18n 来源的自定义标题（保留原简体词表，向后兼容）；
        5. 兜底为"标题前 8 字符 + `_` 前缀"，保证返回值非空。
        """
        index, patterns = cls._title_index_data()
        hit = index.get(title)
        if hit:
            return hit
        stripped = cls._strip_bracketed(title)
        if stripped != title:
            hit = index.get(stripped)
            if hit:
                return hit
        for pattern, topic in patterns:
            if pattern.fullmatch(title) or pattern.fullmatch(stripped):
                return topic

        lowered = title.lower()
        for topic, words in _LEGACY_TOPIC_KEYWORDS:
            if any(w in lowered for w in words):
                return topic
        # 无法分类时取标题前 8 字符 + _ 前缀，确保不为空
        return "_" + (title[:8] or "default")

    @classmethod
    def _title_index_data(cls) -> tuple[dict[str, str], list[tuple[re.Pattern[str], str]]]:
        """惰性构建并缓存索引（进程级；三语与 i18n 文件固定，运行期无需失效）。"""
        if cls._title_index_cache is None:
            try:
                cls._title_index_cache = cls._compile_index()
            except Exception:
                logger.warning("主题索引构建失败，退回关键词匹配", exc_info=True)
                cls._title_index_cache = ({}, [])
        return cls._title_index_cache
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

        **调用方分支（`platform/notify.py`）**：仅当 `auto_pause_enabled` 为真时才进入
        本方法（默认真——`notification.auto_pause` 无 defaults 声明，属性侧以 True 兜底）；
        为假时平台层改走 `_check_dedup`（3 秒同标题防抖）后直发托盘，**不经过主题分组**。
        这是有意设计的两条互斥路径（见 `platform/notify.py` 的职责边界注释）：
        关闭自动暂停即放弃聚合与暂停能力，改由瞬时防抖去重。故主题分组在关闭
        自动暂停时不适用，本修复无需覆盖该分支。
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
