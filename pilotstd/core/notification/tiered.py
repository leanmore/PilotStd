"""分档节流（阶段 B3，Docker 侧）：长阶段按主题节流 + 耗时埋点。

设计依据：
- [02-framework-update.md](../../../docs/plans/notification-system-design/02-framework-update.md) §三（分档策略）
  与 §四 W3 行「**分档策略需在两端一致**」；
- [03-impl-design-D.md](../../../docs/plans/notification-system-design/03-impl-design-D.md) §1.2 B 行
  验收「**长阶段 60 秒节流**」；
- 裁决 N3(a)「分档阈值**先补埋点**再定稿」⇒ 本模块同时负责把**实测耗时**写进
  `notification_log.task_context`（JSON，**无迁移号**）。

口径（与 Windows 端 W3 对齐，常量单源）：
- 阶段判定阈值 `LONG_STAGE_SECONDS = 30.0`——与桌面既有「30 秒内 3 条」熔断窗口同源；
- 长阶段节流窗口 `LONG_STAGE_THROTTLE_SECONDS = 60.0`——`pilotstd/platform/notify.py`
  的 `NotifyService.LONG_STAGE_WINDOW` **引用本常量**，避免两端各写一个 60 而漂移；
- **只允许升档、不允许降档**（§3.5 #7）：声明为短的阶段若实测超过阈值，按长阶段处理。
"""

import json
import time
from dataclasses import dataclass, field

# 阶段判定阈值（秒）：与桌面熔断窗口同源
LONG_STAGE_SECONDS = 30.0
# 长阶段节流窗口（秒）：必须 > 桌面熔断的「30 秒内 3 条」，否则进度类通知会自己触发熔断
LONG_STAGE_THROTTLE_SECONDS = 60.0

# task_context 中承载耗时的键（数据字典；前端目前不渲染该列）
CONTEXT_ELAPSED_KEY = "stage_elapsed_ms"
CONTEXT_TIER_KEY = "tier"


@dataclass
class TieredThrottle:
    """长阶段「同主题 60 秒一条」节流器（与 W3 的托盘节流同语义、同窗口）。

    `admit()` 返回 False 表示本次应节流掉（不投递、不写日志行——节流是正常行为，
    不是投递失败，写日志会污染投递健康统计）。
    """

    window_seconds: float = LONG_STAGE_THROTTLE_SECONDS
    _last: dict[str, float] = field(default_factory=dict)

    def admit(self, topic: str, is_long_stage: bool, now: float | None = None) -> bool:
        """长阶段才节流；短阶段一律放行（短阶段本就是「完成一条」）。"""
        if not is_long_stage:
            return True
        if not topic:
            return True
        current = time.time() if now is None else now
        last = self._last.get(topic)
        if last is not None and current - last < self.window_seconds:
            return False
        self._last[topic] = current
        return True

    def __len__(self) -> int:  # 便于观测
        return len(self._last)


def tier_of(elapsed_ms: float | None, declared_long: bool = False) -> str:
    """分档判定：**只允许升档**——声明短但实测超阈值 ⇒ 判为 long。"""
    if declared_long:
        return "long"
    if elapsed_ms is not None and elapsed_ms / 1000.0 >= LONG_STAGE_SECONDS:
        return "long"
    return "short"


def build_context(
    existing: object,
    elapsed_ms: float | None,
    declared_long: bool = False,
) -> dict:
    """把耗时与档位**并入**既有 task_context（保留原键，不覆盖业务上下文）。"""
    context: dict = dict(existing) if isinstance(existing, dict) else {}
    if elapsed_ms is None and not declared_long:
        # **无耗时且未声明长阶段时不写任何键**：保持「task_context 原样落库」的既有契约
        # （否则会改变所有历史调用方的落库结果，属不必要的行为变更）。
        return context
    if elapsed_ms is not None:
        context[CONTEXT_ELAPSED_KEY] = round(float(elapsed_ms), 1)
    context[CONTEXT_TIER_KEY] = tier_of(elapsed_ms, declared_long)
    return context


def is_enabled(config: object) -> bool:
    """节流开关（默认开）：`notification.tiered_throttle=false/0/off/v0` 可回退。"""
    raw = config.get("notification.tiered_throttle", True) if hasattr(config, "get") else True
    if isinstance(raw, str):
        return raw.strip().lower() not in ("false", "0", "off", "v0", "no")
    return bool(raw)


def parse_elapsed_ms(context: object) -> float | None:
    """从 task_context 里读回耗时（供门禁/诊断复用）。"""
    if isinstance(context, dict):
        value = context.get(CONTEXT_ELAPSED_KEY)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def dumps(context: dict) -> str:
    """便于测试与诊断的稳定序列化（局部变量标注，避免 no-any-return）。"""
    serialized: str = json.dumps(context, ensure_ascii=False, sort_keys=True)
    return serialized
