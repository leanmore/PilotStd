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
3. `normalize_status()` 提供别名归一（`废止` → `已废止`；历史兼容别名 `未生效` → `即将实施`，
   C3 存量清洗后自然收敛），`normalize_status_for_write()` 是写入端（`file_index.status`）
   的统一归一入口（落库拼写保持既有数据值）；
4. 收敛原先散落在 9 处的容器定义到本模块的命名集合，**取值集合与重构前逐一等价**
   （由 `tests/unit/core/test_status.py` 断言）；
5. `API_FILTER_ACCEPTED_VALUES` 是「API 过滤参数可接受取值」的**单一事实源**，
   `API_VALID_STATUSES` 由其派生，杜绝「契约常量 3 值 / 端点实收 9 值」的不一致
   （P1-5 §5.3）。

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
# - `废止` → `已废止`：同一状态的两种拼写（读取侧展示口径归一）。
# - `未生效` → `即将实施`：**历史兼容别名（C3 存量清洗后自然收敛）**。P1-5 复核（
#   `docs/plans/2026-11-25-p1-unknown-refresh.md` §3.3）实测 10 条 `status='未生效'` 的
#   公告口径 **10/10 = 即将实施**，二者是不同数据源对同一语义的两种写法，不是两个状态。
_STATUS_ALIASES: Final[dict[str, str]] = {
    Status.WITHDRAWN.value: Status.WITHDRAWN_NORMALIZED.value,
    "未生效": Status.UPCOMING.value,  # i18n-allow: 历史数据契约值（非 UI 文案）
}


def normalize_status(value: str | None) -> str:
    """把状态值归一到规范拼写（`废止` → `已废止`；`未生效` → `即将实施`）。

    空白被剥离；无法识别的值原样返回（不做任何猜测性改写）。
    """
    text = (value or "").strip()
    return _STATUS_ALIASES.get(text, text)


def normalize_status_for_write(value: str | None) -> str:
    """[FUNC] 写入端统一归一：把状态值映射为 `file_index.status` 的既有数据值。

    与读取侧 `normalize_status()` 同源（历史兼容别名 `未生效` → `即将实施`），但落库拼写
    必须保持 DB 既有数据值：规范拼写 `已废止` **回写为** `废止`（`file_index` 历史落库值
    统一为 `废止`，否则新增行会漏出「已废止」筛选口径）。

    无法识别的枚举外值原样返回、不猜测语义（存量脏数据治理属批次 12 维护窗口）。
    """
    canonical = normalize_status(value)
    if canonical == Status.WITHDRAWN_NORMALIZED.value:
        return Status.WITHDRAWN.value
    return canonical


#: 英文键 → 数据值（API 契约：调用方可用英文键过滤，与历史中文值入参**并存**）
STATUS_KEY_TO_VALUE: Final[dict[str, str]] = {
    STATUS_EN_KEYS[Status.ACTIVE.value]: Status.ACTIVE.value,
    STATUS_EN_KEYS[Status.UPCOMING.value]: Status.UPCOMING.value,
    STATUS_EN_KEYS[Status.WITHDRAWN_NORMALIZED.value]: Status.WITHDRAWN_NORMALIZED.value,
    STATUS_EN_KEYS[Status.SUPERSEDED.value]: Status.SUPERSEDED.value,
    STATUS_EN_KEYS[Status.VOIDED.value]: Status.VOIDED.value,
    STATUS_EN_KEYS[Status.EXPIRED.value]: Status.EXPIRED.value,
    STATUS_EN_KEYS[Status.PENDING.value]: Status.PENDING.value,
    STATUS_EN_KEYS[Status.UNKNOWN.value]: Status.UNKNOWN.value,
}

#: **单一事实源**：API 过滤参数可接受的取值全集 = 英文契约键 ∪ 全部中文数据值 ∪ 历史兼容别名。
#: 端点（`docker/api/standards.py`）的 400 校验与契约常量 `API_VALID_STATUSES` 均由此派生，
#: 避免出现「常量 3 值 / 端点实收 9 值 / docstring 只列 3 个」的契约漂移（P1-5 §5.3）。
API_FILTER_ACCEPTED_VALUES: Final[frozenset[str]] = (
    frozenset(STATUS_KEY_TO_VALUE) | ALL_STATUS_VALUES | frozenset(_STATUS_ALIASES)
)


def status_key(value: str | None) -> str:
    """数据状态值 → **稳定英文键**（API 契约字段 `status_key`，供前端做与文案无关的比较）。

    未知/空值回退 `"unknown"` —— 前端只比较 ASCII 键，不再比较中文文案。
    入参若已是英文键则原样返回（幂等，便于数据穿透处理）。
    """
    text = normalize_status(value)
    if text in STATUS_KEY_TO_VALUE:
        return text
    return STATUS_EN_KEYS.get(text, STATUS_EN_KEYS[Status.UNKNOWN.value])


def resolve_status_filter(raw: str | None) -> str | None:
    """把 API 过滤入参解析为数据值：**同时接受英文键、历史中文值与历史兼容别名**。

    解析顺序：英文契约键 → 中文数据值（含别名归一）→ 无法识别返回 `None`。
    **注意**：`None` 只表示「空值或不合法」；调用方（API 端点）对**非空但不合法**的入参
    必须显式 400，不得静默忽略过滤（P1-5 §5.1 的 P0 缺陷）。
    """
    text = (raw or "").strip()
    if not text:
        return None
    if text in STATUS_KEY_TO_VALUE:
        return STATUS_KEY_TO_VALUE[text]
    normalized = normalize_status(text)
    return normalized if normalized in ALL_STATUS_VALUES else None


def is_valid_status_filter(raw: str | None) -> bool:
    """[FUNC] 判断 API 过滤入参是否为**可识别的合法取值**（空值不算合法）。

    与 `resolve_status_filter()` 接受集合同源（`API_FILTER_ACCEPTED_VALUES`），供端点
    对非法取值返回 400；空值由调用方按「未传过滤」处理。
    """
    text = (raw or "").strip()
    return bool(text) and text in API_FILTER_ACCEPTED_VALUES


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

#: 对外 API 的合法状态取值（**由 `API_FILTER_ACCEPTED_VALUES` 派生**，类型保持 `tuple`）。
#: 历史问题（P1-5 §5.3）：此处曾手写 3 个展示桶（现行/已废止/未知），而端点实际接受
#: 9 个中文值 + 8 个英文键，docstring 也只列 3 个键 —— 契约与实际行为不一致。
API_VALID_STATUSES: Final[tuple[str, ...]] = tuple(sorted(API_FILTER_ACCEPTED_VALUES))
