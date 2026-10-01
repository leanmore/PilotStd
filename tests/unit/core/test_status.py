"""状态字典受控测试 + **中文契约哨兵**（#32-A/B/D，2026-10-01）。

## 哨兵机制（#32-D / R14-4d）

`Status` 枚举的 value 必须与**现网中文契约**逐字一致——它同时是：
外部系统/历史数据里的取值、API 返回的中文数据值、DB 落库值、前端旧书签的过滤参数。
一旦有人"顺手改"枚举 value（例如把 `现行` 改成 `有效`），生产代码不会报错，但会与
历史数据、外部系统、前端旧缓存静默脱节。因此本文件**刻意保留直写的中文字面量**作为哨兵：

    Sentinel 1：`test_sentinel_enum_values_match_live_chinese_contract`（9 值逐字比对）

同批另设 4 处哨兵（均带 `# Sentinel:` 注释，分布在不同层）：
    Sentinel 2：`tests/unit/core/test_status_convergence.py`（生产代码零裸字面量的扫描基准）
    Sentinel 3：`tests/unit/core/test_status_contract.py`（API 过滤的历史中文入参）
    Sentinel 4：`tests/test_adapters.py`（适配器解析真实中文状态文本）
    Sentinel 5：`tests/unit/core/test_migrate_v61.py`（DB 历史默认值）

除哨兵外，测试代码一律使用 `Status.*.value`（与生产同一事实源）。
"""

from __future__ import annotations

import pytest

from pilotstd.core import status as status_dict
from pilotstd.core.notification._format_utils import ABOLISHED_STATUS_TOKENS
from pilotstd.core.status import Status, normalize_status
from pilotstd.manager.classifier import QueryClassifier
from pilotstd.manager.facade._query import QueryHandler
from pilotstd.manager.facade._query_subsystem import QuerySubsystem
from pilotstd.organizer.mover import FileMover

EXPECTED_VALUES = tuple(member.value for member in Status)


# ── Sentinel 1：枚举 value 与现网中文契约逐字一致 ──────────────────────────


def test_sentinel_enum_values_match_live_chinese_contract():
    """**哨兵**：以下 9 个中文字面量是外部契约，禁止随枚举实现一起"顺手改"。"""
    # Sentinel: 确保枚举 value 与现网中文契约一致（外部系统 / 历史数据 / API / DB / 前端旧书签）
    assert Status.ACTIVE.value == "现行"
    assert Status.UPCOMING.value == "即将实施"
    assert Status.WITHDRAWN.value == "废止"
    assert Status.WITHDRAWN_NORMALIZED.value == "已废止"
    assert Status.SUPERSEDED.value == "被代替"
    assert Status.VOIDED.value == "作废"
    assert Status.EXPIRED.value == "过期"
    assert Status.PENDING.value == "待确认"
    assert Status.UNKNOWN.value == "未知"


def test_all_nine_values_round_trip():
    """9 值 round-trip：枚举成员与其 value 双向一致，且全集恰为 9 值。"""
    assert EXPECTED_VALUES == (
        Status.ACTIVE.value,
        Status.UPCOMING.value,
        Status.WITHDRAWN.value,
        Status.WITHDRAWN_NORMALIZED.value,
        Status.SUPERSEDED.value,
        Status.VOIDED.value,
        Status.EXPIRED.value,
        Status.PENDING.value,
        Status.UNKNOWN.value,
    )
    for member in Status:
        assert Status(member.value) is member
        assert member.value in status_dict.ALL_STATUS_VALUES
    assert status_dict.ALL_STATUS_VALUES == set(EXPECTED_VALUES)
    assert len(status_dict.ALL_STATUS_VALUES) == 9


def test_status_members_are_str_compatible():
    """`Status` 混入 str：成员可直接与现网字符串比较（B 阶段逐点替换的兼容前提）。"""
    assert Status.ACTIVE == Status.ACTIVE.value
    assert Status.WITHDRAWN_NORMALIZED == Status.WITHDRAWN_NORMALIZED.value
    assert f"{Status.UNKNOWN.value}" == Status.UNKNOWN.value


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (Status.WITHDRAWN.value, Status.WITHDRAWN_NORMALIZED.value),  # 别名归一（双拼写消除）
        (Status.WITHDRAWN_NORMALIZED.value, Status.WITHDRAWN_NORMALIZED.value),  # 规范值不变
        (f" {Status.WITHDRAWN.value} ", Status.WITHDRAWN_NORMALIZED.value),  # 空白剥离
        (Status.ACTIVE.value, Status.ACTIVE.value),  # 其它值原样
        (Status.UNKNOWN.value, Status.UNKNOWN.value),
        (Status.VOIDED.value, Status.VOIDED.value),
        ("", ""),
        (None, ""),
        ("自定义状态", "自定义状态"),  # 未知值不猜测、不改写
    ],
)
def test_normalize_status(raw, expected):
    assert normalize_status(raw) == expected


def test_i18n_and_english_scaffolding_cover_all_values():
    """中英文映射脚手架覆盖全部 9 值，双拼写映射到同一 i18n key / 英文枚举值。"""
    assert set(status_dict.STATUS_I18N_KEYS) == set(EXPECTED_VALUES)
    assert set(status_dict.STATUS_EN_KEYS) == set(EXPECTED_VALUES)
    assert all(key.startswith("status.") for key in status_dict.STATUS_I18N_KEYS.values())
    assert (
        status_dict.STATUS_I18N_KEYS[Status.WITHDRAWN.value]
        == status_dict.STATUS_I18N_KEYS[Status.WITHDRAWN_NORMALIZED.value]
    )
    assert (
        status_dict.STATUS_EN_KEYS[Status.WITHDRAWN.value]
        == status_dict.STATUS_EN_KEYS[Status.WITHDRAWN_NORMALIZED.value]
        == "withdrawn"
    )


# ── 容器等价性（基准由哨兵 pin 住的枚举值派生）────────────────────────────


def test_named_sets_equal_pre_refactor_literals():
    """命名集合与重构前字面量逐一等价（4 值／5 值／3 值／含待确认／API tuple 五种口径）。

    重构前的字面量取值由 Sentinel 1 的 9 个哨兵 pin 住，故此处用枚举值表达等价性
    （等价性判据不变，且不再重复散落中文字面量——#32-D）。
    """
    assert status_dict.ABOLISHED_STATUSES == {
        Status.WITHDRAWN.value,
        Status.WITHDRAWN_NORMALIZED.value,
        Status.VOIDED.value,
        Status.SUPERSEDED.value,
    }
    assert status_dict.ABOLISHED_STATUSES_WITH_EXPIRED == set(status_dict.ABOLISHED_STATUSES) | {Status.EXPIRED.value}
    assert status_dict.EXPIRED_STATUSES == {
        Status.WITHDRAWN.value,
        Status.WITHDRAWN_NORMALIZED.value,
        Status.VOIDED.value,
    }
    assert status_dict.NON_OVERRIDABLE_STATUSES == {
        Status.WITHDRAWN.value,
        Status.WITHDRAWN_NORMALIZED.value,
        Status.VOIDED.value,
        Status.PENDING.value,
    }
    assert status_dict.API_VALID_STATUSES == (
        Status.ACTIVE.value,
        Status.WITHDRAWN_NORMALIZED.value,
        Status.UNKNOWN.value,
    )


def test_containers_are_the_shared_sets():
    """可导入的容器与命名集合是**同一对象**（证明引用而非复制）。

    仅覆盖**不依赖 Qt** 的模块：`test-backend` 作业不安装 PyQt6（GUI 依赖），
    UI 侧容器（`ui/core/handlers/*`）由下面单独一例在 GUI 可用环境下断言。
    """
    assert QueryClassifier._EXPIRE_STATUSES is status_dict.ABOLISHED_STATUSES
    assert QueryHandler._EXPIRE_STATUSES is status_dict.ABOLISHED_STATUSES
    assert QuerySubsystem._EXPIRE_STATUSES is status_dict.ABOLISHED_STATUSES
    assert FileMover._EXPIRE_STATUSES is status_dict.ABOLISHED_STATUSES_WITH_EXPIRED
    assert ABOLISHED_STATUS_TOKENS is status_dict.ABOLISHED_STATUSES_WITH_EXPIRED

    from docker.api.standards import _VALID_STATUSES as api_valid_statuses

    assert api_valid_statuses is status_dict.API_VALID_STATUSES


def test_ui_containers_are_the_shared_sets():
    """UI 侧容器（`auto_flow_engine` / `query_flow_engine`）同样引用命名集合。

    这两个模块 import PyQt6，而 `test-backend` 作业不安装 GUI 依赖 → 用 `importorskip`
    做**环境守卫**（可选依赖缺失时跳过；本地与 CI 的 GUI 作业中会真实执行）。
    """
    pytest.importorskip("PyQt6", reason="后端测试作业不含 GUI 依赖（PyQt6）")

    from pilotstd.ui.core.handlers.auto_flow_engine import AutoFlowEngine
    from pilotstd.ui.core.handlers.query_flow_engine import _EXCLUDED_FROM_OVERRIDE

    assert AutoFlowEngine.EXPIRED_STATUSES is status_dict.EXPIRED_STATUSES
    assert _EXCLUDED_FROM_OVERRIDE is status_dict.NON_OVERRIDABLE_STATUSES


def test_api_valid_statuses_is_still_a_tuple():
    """`API_VALID_STATUSES` 类型保持 tuple（原 `_VALID_STATUSES` 为 tuple，`in` 判定语义不变）。"""
    assert isinstance(status_dict.API_VALID_STATUSES, tuple)
    assert Status.ACTIVE.value in status_dict.API_VALID_STATUSES
    assert Status.WITHDRAWN.value not in status_dict.API_VALID_STATUSES  # 旧拼写不在 API 白名单（与重构前一致）
