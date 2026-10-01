"""标准状态值权威字典（#32-A / R14-4a，2026-10-01）。

## 设计意图（技术债 #32）

状态值当前是**中文化自由字符串**：由 `pilotstd/query/adapters/` 适配器、公告匹配器
（`announcement/matcher.py`）、时效检查器（`core/validity_checker.py`）与 DB 默认值
（`core/db/_migrate_v2_v15.py` 等）**各自独立**产生；前端只能硬编码中文与之比较
（13 处 `i18n-allow`），同一语义还存在 `废止` / `已废止` 双拼写。后果是 i18n 无法收口、
跨页状态判定可能不一致、改文案会静默破坏前端（无类型保护）。

本模块是 **A 阶段**的产物——**纯增量、零行为变化**：

1. `Status` 枚举的 **value 与现网字符串逐字一致**（API 返回、DB 落库、前端比较全部向后兼容）；
2. `STATUS_I18N_KEYS` / `STATUS_EN_KEYS` 是后续 B/C 阶段「后端英文枚举 + 前端 enum→i18n key
   映射」的**脚手架**（本阶段只登记映射，不改任何返回字符串）；
3. `normalize_status()` 提供 `废止` → `已废止` 的**别名归一**（供统计/展示统一口径使用）；
4. 收敛原先散落在 9 处的容器定义到本模块的命名集合，**取值集合与重构前逐一等价**
   （由 `tests/unit/core/test_status.py` 断言）。

本阶段**不替换**业务逻辑中的状态字面量（B 阶段）、**不改 DB 迁移脚本**、
**不改 API 返回字符串**。
"""

from __future__ import annotations

from enum import Enum
from typing import Final


class Status(str, Enum):
    """标准状态枚举：**value ＝ 现网中文字符串**（向后兼容，不改变 API/DB 行为）。

    `str` 混入使成员可直接当作字符串使用（`Status.ACTIVE == "现行"` 为真），
    便于 B 阶段逐点替换字面量时不改变调用方语义。
    """

    ACTIVE = "现行"
    UPCOMING = "即将实施"
    WITHDRAWN = "废止"  # 旧拼写：见 normalize_status()
    WITHDRAWN_NORMALIZED = "已废止"  # 规范拼写
    SUPERSEDED = "被代替"
    VOIDED = "作废"
    EXPIRED = "过期"
    PENDING = "待确认"
    UNKNOWN = "未知"


# ── 映射脚手架（B/C 阶段使用；本阶段不改任何返回值）──────────────────────

STATUS_I18N_KEYS: Final[dict[str, str]] = {
    Status.ACTIVE.value: "status.active",
    Status.UPCOMING.value: "status.upcoming",
    Status.WITHDRAWN.value: "status.withdrawn",
    Status.WITHDRAWN_NORMALIZED.value: "status.withdrawn",
    Status.SUPERSEDED.value: "status.superseded",
    Status.VOIDED.value: "status.voided",
    Status.EXPIRED.value: "status.expired",
    Status.PENDING.value: "status.pending",
    Status.UNKNOWN.value: "status.unknown",
}

#: B/C 阶段的目标英文枚举名（写入 API/DB 的规范值）——当前仅登记，不参与任何返回
STATUS_EN_KEYS: Final[dict[str, str]] = {
    Status.ACTIVE.value: "active",
    Status.UPCOMING.value: "upcoming",
    Status.WITHDRAWN.value: "withdrawn",
    Status.WITHDRAWN_NORMALIZED.value: "withdrawn",
    Status.SUPERSEDED.value: "superseded",
    Status.VOIDED.value: "voided",
    Status.EXPIRED.value: "expired",
    Status.PENDING.value: "pending",
    Status.UNKNOWN.value: "unknown",
}

#: 全部合法状态值（9 值全集）
ALL_STATUS_VALUES: Final[frozenset[str]] = frozenset(member.value for member in Status)

# 别名表：仅登记“同一语义的不同拼写”，不删除任何历史值
_STATUS_ALIASES: Final[dict[str, str]] = {
    Status.WITHDRAWN.value: Status.WITHDRAWN_NORMALIZED.value,
}


def normalize_status(value: str | None) -> str:
    """把状态值归一到规范拼写（当前仅 `废止` → `已废止`）。

    空白被剥离；未知值原样返回（不做任何猜测性改写）。
    """
    text = (value or "").strip()
    return _STATUS_ALIASES.get(text, text)


# ── 容器收敛：与原 9 处定义逐一等价 ────────────────────────────────────────
# 说明：下列 4 组集合的存在差异（是否含「过期」、是否含「待确认」）源自历史演进，
# A 阶段**保持取值不变**（零行为变化）；统一口径留待 B 阶段按模块逐个收敛。

#: 4 值：废止 / 已废止 / 作废 / 被代替
#: 原 `manager/classifier.py:26`、`manager/facade/_query.py:33`、`manager/facade/_query_subsystem.py:48`
ABOLISHED_STATUSES: Final[frozenset[str]] = frozenset(
    {Status.WITHDRAWN.value, Status.WITHDRAWN_NORMALIZED.value, Status.VOIDED.value, Status.SUPERSEDED.value}
)

#: 5 值：上述 4 值 + 过期
#: 原 `manager/facade/_organize.py:186`、`organizer/mover.py:35`、`core/notification/_format_utils.py:10`
ABOLISHED_STATUSES_WITH_EXPIRED: Final[frozenset[str]] = frozenset(
    set(ABOLISHED_STATUSES) | {Status.EXPIRED.value}
)

#: 3 值：废止 / 已废止 / 作废（原 `ui/core/handlers/auto_flow_engine.py:18`）
EXPIRED_STATUSES: Final[frozenset[str]] = frozenset(
    {Status.WITHDRAWN.value, Status.WITHDRAWN_NORMALIZED.value, Status.VOIDED.value}
)

#: 4 值（含待确认）：废止 / 已废止 / 作废 / 待确认（原 `ui/core/handlers/query_flow_engine.py:30`）
NON_OVERRIDABLE_STATUSES: Final[frozenset[str]] = frozenset(
    {Status.WITHDRAWN.value, Status.WITHDRAWN_NORMALIZED.value, Status.VOIDED.value, Status.PENDING.value}
)

#: 对外 API 的合法状态取值（原 `docker/api/standards.py:17`；类型保持 tuple）
API_VALID_STATUSES: Final[tuple[str, ...]] = (
    Status.ACTIVE.value,
    Status.WITHDRAWN_NORMALIZED.value,
    Status.UNKNOWN.value,
)
