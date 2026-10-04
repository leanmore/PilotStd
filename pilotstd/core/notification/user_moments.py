"""用户时刻清单（第二 SSOT，阶段 C）。

数据来源：`docs/plans/notification-system-design/00-framework.md` §1.1（36 个 Docker 侧用户时刻），
程序化转录为 `data/user_moments.json`——数据与展示分离：本模块只做闭包判定，
不承载文案字面量（中文时刻名在数据文件里）。

用途：把门禁输入源从"单一事件清单"改为「用户时刻 × 事件」**双向闭包**，
替代原先的 `assert len(EVENTS) == 41`（病根：加一个时刻要动多处清单）。

声明的例外（设计裁决，不是遗漏）：
- `DECLARED_MOMENTS_WITHOUT_EVENT`：#5 无事件——裁决 3 采 (b)，由 `batch_query_summary` 文案承载；
- `DECLARED_EVENTS_WITHOUT_MOMENT`：裁决 1 采 (b) 的 3 个多余事件，保留事件、默认不订阅。
"""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class UserMoment:
    """一个用户时刻：编号 + 用户语言描述 + 优先级 + 承接事件键。"""

    no: int
    name: str
    priority: str
    events: tuple[str, ...]


def _load_moments() -> tuple[UserMoment, ...]:
    """从包内 JSON 读时刻清单（数据文件缺失即抛错，避免静默退化成空清单）。"""
    path = Path(__file__).with_name("data") / "user_moments.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return tuple(
        UserMoment(
            no=int(item["no"]),
            name=str(item["name"]),
            priority=str(item["priority"]),
            events=tuple(str(e) for e in item["events"]),
        )
        for item in payload["moments"]
    )


USER_MOMENTS: tuple[UserMoment, ...] = _load_moments()

# 设计裁决声明的例外（改动必须同步改本节与测试，避免静默放宽）
DECLARED_MOMENTS_WITHOUT_EVENT: tuple[int, ...] = (5,)  # 裁决 3(b)
DECLARED_EVENTS_WITHOUT_MOMENT: tuple[str, ...] = (
    "standard_first_registered",
    "normalize_complete",
    "download_started",
)  # 裁决 1(b)

# 【次要事件】与某时刻同刻的其它事件：设计 §1.3 的重复 5 + 粒度错配 7，
# 外加 §1.1 #9 的同刻补充（download_complete 由 batch_download_complete 承接）。
SECONDARY_EVENTS: tuple[str, ...] = (
    "download_complete",
    "scan_empty",
    "query_empty",
    "validity_batch_report",
    "announcement_check_complete",
    "announce_fetch_summary",
    "auto_backup",
    "batch_download_complete",
    "scan_complete",
    "standard_status_changed",
    "trust_ip_update",
    "image_update_available",
    "favorite_created",
)


def moments_without_event() -> list[int]:
    """没有任何事件承接的用户时刻编号（应等于声明的例外）。"""
    return [m.no for m in USER_MOMENTS if not m.events]


def events_claimed_by_moments() -> set[str]:
    """被任一用户时刻承接的事件键集合。"""
    claimed: set[str] = set()
    for moment in USER_MOMENTS:
        claimed.update(moment.events)
    return claimed


def all_attributable_events() -> set[str]:
    """可追溯到用户时刻的事件键 = 承接事件 ∪ 次要事件 ∪ 声明的多余事件。"""
    return (
        events_claimed_by_moments()
        | set(SECONDARY_EVENTS)
        | set(DECLARED_EVENTS_WITHOUT_MOMENT)
    )


def events_without_moment(event_keys: set[str]) -> list[str]:
    """平台可见但既非承接、也非次要、也非声明冗余的事件键（应为空）。"""
    return sorted(set(event_keys) - all_attributable_events())


def unknown_event_keys(event_keys: set[str]) -> list[str]:
    """时刻表引用了不存在的事件键（拼写/下线残留 ⇒ 必须为空）。"""
    return sorted(events_claimed_by_moments() - set(event_keys))
