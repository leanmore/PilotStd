"""状态字典受控测试（#32-A / R14-4a，2026-10-01）。

锁定 A 阶段的**零行为变化**契约：
  ① 9 值 round-trip：`Status(member.value).value == member.value`，且 `ALL_STATUS_VALUES` 恰为 9 值；
  ② 别名归一：`废止` → `已废止`（其它值不变；空白剥离；None/空串 → 空串）；
  ③ i18n / 英文枚举脚手架覆盖全部 9 值；
  ④ **9 处旧容器取值逐一等价**：
     · 命名集合（`status_dict.*`）== 重构前字面量集合（逐值）；
     · 可导入的容器对象与命名集合**同一对象**（证明容器确实引用字典，而非各自复制一遍）。
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

# 重构前 9 处容器的字面量取值（作为等价性基准，来源：各文件原定义行）
PRE_REFACTOR_4 = {"废止", "已废止", "作废", "被代替"}
PRE_REFACTOR_5 = {"废止", "已废止", "作废", "被代替", "过期"}
PRE_REFACTOR_3 = {"废止", "已废止", "作废"}
PRE_REFACTOR_EXCLUDED = {"废止", "已废止", "作废", "待确认"}
PRE_REFACTOR_API = ("现行", "已废止", "未知")

EXPECTED_VALUES = ("现行", "即将实施", "废止", "已废止", "被代替", "作废", "过期", "待确认", "未知")


def test_all_nine_values_round_trip():
    """9 值 round-trip：枚举 value 与现网字符串逐字一致，且全集恰为 9 值。"""
    assert tuple(member.value for member in Status) == EXPECTED_VALUES
    for member in Status:
        assert Status(member.value) is member
        assert member.value in status_dict.ALL_STATUS_VALUES
    assert status_dict.ALL_STATUS_VALUES == set(EXPECTED_VALUES)
    assert len(status_dict.ALL_STATUS_VALUES) == 9


def test_status_members_are_str_compatible():
    """`Status` 混入 str：成员可直接与现网字符串比较（B 阶段逐点替换时的兼容前提）。"""
    assert Status.ACTIVE == "现行"
    assert Status.WITHDRAWN_NORMALIZED == "已废止"
    assert f"{Status.UNKNOWN.value}" == "未知"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("废止", "已废止"),  # 别名归一（双拼写消除）
        ("已废止", "已废止"),  # 规范值不变
        (" 废止 ", "已废止"),  # 空白剥离
        ("现行", "现行"),  # 其它值原样
        ("未知", "未知"),
        ("作废", "作废"),
        ("", ""),
        (None, ""),
        ("自定义状态", "自定义状态"),  # 未知值不猜测、不改写
    ],
)
def test_normalize_status(raw, expected):
    assert normalize_status(raw) == expected


def test_i18n_and_english_scaffolding_cover_all_values():
    """中英文映射脚手架覆盖全部 9 值，且 i18n key 形如 status.*。"""
    assert set(status_dict.STATUS_I18N_KEYS) == set(EXPECTED_VALUES)
    assert set(status_dict.STATUS_EN_KEYS) == set(EXPECTED_VALUES)
    assert all(key.startswith("status.") for key in status_dict.STATUS_I18N_KEYS.values())
    # 双拼写映射到同一个 i18n key / 英文枚举值（同一语义）
    assert status_dict.STATUS_I18N_KEYS["废止"] == status_dict.STATUS_I18N_KEYS["已废止"]
    assert status_dict.STATUS_EN_KEYS["废止"] == status_dict.STATUS_EN_KEYS["已废止"] == "withdrawn"


# ── ③ 9 处旧容器等价性 ─────────────────────────────────────────────────────


def test_named_sets_equal_pre_refactor_literals():
    """命名集合与重构前字面量逐一等价（含 4 值／5 值／3 值／含待确认四种口径）。"""
    assert status_dict.ABOLISHED_STATUSES == PRE_REFACTOR_4
    assert status_dict.ABOLISHED_STATUSES_WITH_EXPIRED == PRE_REFACTOR_5
    assert status_dict.EXPIRED_STATUSES == PRE_REFACTOR_3
    assert status_dict.NON_OVERRIDABLE_STATUSES == PRE_REFACTOR_EXCLUDED
    assert status_dict.API_VALID_STATUSES == PRE_REFACTOR_API


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
    assert "现行" in status_dict.API_VALID_STATUSES
    assert "废止" not in status_dict.API_VALID_STATUSES  # 旧拼写不在 API 白名单（与重构前一致）
