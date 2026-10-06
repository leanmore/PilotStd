# 模块：项目/核心//事件规格脚本
"""事件规格（SSOT）——41 个通知事件的唯一声明源（设计见 notification-system-design/06 §一）。

本模块只做声明：**D1 起由 `mapping` 接入**（`EVENT_MAPPINGS` 由其派生）；其余消费方
（`manager` 构建器注册 / `defaults` 订阅规则）按 D2 / D3 逐步接入。四条硬约束：

1. **单向依赖**：只 import 标准库与 ``.events``（该模块零内部依赖、10 个消费方，
   不能被拖重）。**不 import 构建器实现模块**——构建器位置以 ``builder_ref``
   字符串登记、运行期由 ``builder_callable()`` 延迟解析，以免 ``mapping`` /
   ``defaults`` 这类轻消费方在取规格时被动加载渲染链路。
2. **静态字面量**：门禁以 ``ast.parse`` 读取本文件，不做运行期推导；每条声明的
   15 个字段一律写字面量。
3. **15 字段**：``key`` / ``notify_event`` / ``content_type`` / ``task_kind`` /
   ``builder_ref`` / ``i18n_category`` / ``default_channels`` / ``levels`` /
   ``module_key`` / ``trigger_file`` / ``payload_keys`` / ``security`` /
   ``branch_by`` / ``subscribable`` / ``aggregation``。取值来自映射表、端到端契约、
   默认配置与语言包；构建器文件与函数名不入规格（由 ``builder`` 反射派生）。
4. **级别有序**：``levels`` 按 ``LEVEL_ORDER`` 的严重度升序书写，与既有端到端
   契约的斜杠连接字面值完全同序。

**字段值一律机器可读，不写展示文案**（决策者 2026-10-03 裁决方案 c）：

- 业务模块名改用 i18n 键（``module_key``）——文案本体在 ``pilotstd/i18n/*.json``
  的 ``notification.module.*`` 键族里，本模块只登记键；中文模块名不可出现在此。
- 聚合策略改用 ASCII 枚举（``aggregate`` / ``bypass``）——它是系统内部状态标识，
  **不进 i18n**（不展示给用户，做成键反而增加一层无意义的间接）。
- **不登记互斥说明**：互斥关系是设计文档里的说明，不是数据；需要时查设计文档，
  不在此复制一份中文散文（e2e 契约自留该字段用于自身比对，与本模块无关）。

留待后续批次：``branch_by`` 一律为 ``None``（4 个待分支事件尚无分支实现）；
``subscribable``（用户可勾选）与 ``default_channels``（出厂默认订阅）不同轴；
``security`` 判定**是否强制审计留痕**，与 ``notify_event`` 是否为安全告警不同轴。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .events import ALL_EVENTS

# 级别的**唯一排序口径**（设计 06 §三 2 遗留项 1，2026-10-05 落地）。
# 为什么用严重度序而非字母序：级别是给人看、给策略判定的语义标签，字母序
# （error/info/warning）会误导读者，也与端到端契约的斜杠连接字面值（"info/warning/error"）不同序。
# 为什么允许"跳级"：`("info", "error")` 是真实业务事实（该事件不产生 warning）⇒
# 校验只要求**保序**，不要求连续覆盖——统一的是**顺序口径**，不是**值集合**。
# 校验位置：`tests/test_notification_e2e.py` 的 D4 契约测试类（该文件是计划内的规格消费方；
# 新建独立测试文件会被 `test_event_spec.py` 的"接入白名单"守卫正确拦截）。
LEVEL_ORDER: tuple[str, ...] = ("info", "warning", "error")

__all__ = [
    "AGGREGATION_VALUES",
    "EVENT_SPECS",
    "EVENT_SPEC_KEYS",
    "LEVEL_ORDER",
    "EventSpec",
    "builder_callable",
    "spec_for",
]

# 聚合策略值域闭集（纯英文枚举，非展示文案）：与端到端契约的 38 聚合 + 3 绕过同义
AGGREGATION_VALUES: tuple[str, ...] = ("aggregate", "bypass")

# 级别值域闭集，按严重度升序——声明里的级别序列必须按本次序书写


@dataclass(frozen=True)
class EventSpec:
    """单个通知事件的声明（`builder_ref` 是静态指针，`builder` 按需解析）。"""

    key: str
    notify_event: str
    content_type: str
    task_kind: str
    builder_ref: str
    i18n_category: str
    default_channels: tuple[str, ...]
    levels: tuple[str, ...]
    module_key: str
    trigger_file: str
    payload_keys: frozenset[str]
    security: bool
    branch_by: Callable[[dict[str, Any]], str] | None
    subscribable: bool
    aggregation: str
    # ── 声明式可验证性（2026-10-06 · P6/P7 甲案；**注册时必填**）────────────────
    # `verify` 为**必填**（无默认值 ⇒ 漏填在 import 期直接 TypeError，属"声明式"门禁，零过程式负担）：
    #   · "e2e"            —— 由 e2e/集成链路驱动，可由 `scripts/audit_notification_trigger_map.py` 运行时校验；
    #   · "manual:<理由>"  —— 环境相关、极难在正常运行中触发（如凭证轮换、库损坏类告警），需人工/场景验证；
    #   · "ui_only:<理由>" —— 仅桌面 UI 触发。
    # `verify_reason`：`verify` 非 "e2e" 时**必须非空**（由 G-045 的静态维度校验）。
    verify: str
    verify_reason: str = ""

    @property
    def builder(self) -> Callable[[dict[str, Any]], Any]:
        """本事件的构建器函数（延迟解析，见模块说明第 1 条）。"""
        return builder_callable(self)


def builder_callable(spec: EventSpec) -> Callable[[dict[str, Any]], Any]:
    """把静态指针解析为构建器函数；模块名或函数名有误时抛导入类异常。"""
    import importlib

    module_name, _, func_name = spec.builder_ref.partition(":")
    resolved: Callable[[dict[str, Any]], Any] = getattr(importlib.import_module(module_name), func_name)
    return resolved


def spec_for(key: str) -> EventSpec:
    """按键取规格；未登记的键视为契约违背（调用方应先做键集校验）。"""
    for spec in EVENT_SPECS:
        if spec.key == key:
            return spec
    raise KeyError(key)


# ── 声明（42 条；**数据已迁至 `event_spec_data.py`**，T-41/1 守 G-010）────────────────
# **延迟导入**：必须放在数据类/工厂定义之后，否则与 `event_spec_data` 形成初始化期循环。
from .event_spec_data import EVENT_SPECS  # noqa: E402

# 派生视图（非第二份声明）：只需键集的消费方不必遍历规格对象
EVENT_SPEC_KEYS: tuple[str, ...] = tuple(s.key for s in EVENT_SPECS)

# 护栏：规格集合必须与事件注册表一一对应（设计 §1.1.2 要求；单测同口径复核）
assert set(EVENT_SPEC_KEYS) == {e.key for e in ALL_EVENTS}
