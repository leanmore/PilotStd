# 模块：项目/核心//锁脚本
"""通知架构重设计的**阶段开关**（阶段 2a 建立机制，本批不消费）。

## 为什么需要它

06-阶段0-1实施方案.md §3.0 把"一键回滚"设计为贯穿全阶段的机制：每个阶段交付后，
默认值 = 该阶段；回滚 = 把环境变量改成前一阶段的稳定值（**不改代码、不迁移数据**）。

阶段 0（前端轮询）与阶段 1（纯追加列）的回滚本来就是"代码回退"，不需要开关；
**阶段 2 是第一个真正需要它的地方**——"映射是否生效"必须是可即时切换的，
否则一旦新映射导致通知异常，只能回滚代码。

## 取值与语义

| 取值 | 含义 |
|------|------|
| `0` | 通知链路完全按改造前的现状 |
| `1` | 阶段 1 已交付（新字段写入 `notification_log`），映射不生效 |
| `2` | 阶段 2 映射生效（`notify_event` / `content_type` 回填）← **当前默认** |
| `2.5` | 聚合键切 `notify_event × correlation_id × target_id` |
| `3` | 交互能力启用（回调端点 + 动作） |
| `4` | 三层模型全面生效（配置粒度切换） |

**默认值 = 最高稳定阶段**：阶段 2b-接入期间为 `1`（接入但不生效，行为零变化）；
**2b-启用批把默认值提为 `2`**——这是"启用"这个行为变更点，独立提交以便单独回滚
（回滚 = 把 `HIGHEST_STABLE_STAGE` 改回 `1.0` 或设 `NOTIFY_REDESIGN_STAGE=1`）。

## 非法值处理（判断依据）

环境变量**任何非空但不可识别**的值（如 `"abc"` / `"9"` / `"2.6"`）→ **一律回退默认值并记 warning**，
不抛异常。理由：

1. **这是基础设施开关，不是业务参数**：用户在部署时写错一个字符（拼写错误、多余空格），
   不该让整套通知链路起不来；
2. **与项目既有口径一致**：i18n 的非法语言码"回退默认语言并告警"（`pilotstd/i18n/__init__.py`），
   `_json_codec` 的非法输入"回退空容器并告警"——同一原则：**降级可见，但不致命**；
3. **安全方向**：回退到默认值（本批为"最保守"的 `1` = 新行为不生效）比"回退到 0"
   或"抛异常"都更安全——宁可少开启新能力，不可让链路中断。

`0` 与 `"0"`、`2` 与 `"2.0"` 皆合法（数值比较按 float，故 `2` 与 `2.0` 等价）。
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

__all__ = [
    "ENV_STAGE",
    "HIGHEST_STABLE_STAGE",
    "KNOWN_STAGES",
    "current_stage",
    "is_aggregation_key_v2",
    "is_interaction_enabled",
    "is_mapping_enabled",
]

ENV_STAGE = "NOTIFY_REDESIGN_STAGE"

# 已知阶段取值（回退判定用）。注意 **2.5 是阶段 2.5 的取值**，不是"2 的补丁号"。
KNOWN_STAGES: tuple[float, ...] = (0.0, 1.0, 2.0, 2.5, 3.0, 4.0)

# 当前"最高稳定阶段"：随批次推进而人工提升（每次交付同批改这里 + 本文件表格）。
# 2a 交付后为 1（纯新增）；2b-接入交付后仍为 1（接入但不生效，行为零变化）；
# **2b-启用批提为 2**——映射生效，这是可独立回滚的行为变更点。
HIGHEST_STABLE_STAGE: float = 2.0


def current_stage() -> float:
    """读当前生效阶段；未设置或值不可识别时回退 `HIGHEST_STABLE_STAGE` 并告警。"""
    raw = os.environ.get(ENV_STAGE)
    if raw is None or not raw.strip():
        return HIGHEST_STABLE_STAGE
    try:
        value = float(raw.strip())
    except ValueError:
        logger.warning(
            # i18n-allow: 开发者日志（运维排查用，不进 i18n）——标记须紧邻含中文的那一行
            "环境变量 %s 取值无法解析（%r），回退默认阶段 %s", ENV_STAGE, raw, HIGHEST_STABLE_STAGE
        )
        return HIGHEST_STABLE_STAGE
    if value not in KNOWN_STAGES:
        logger.warning(
            # i18n-allow: 开发者日志（同上）——标记须紧邻含中文的那一行
            "环境变量 %s 取值不在已知阶段集合 %s 内（%r），回退默认阶段 %s",
            ENV_STAGE,
            KNOWN_STAGES,
            raw,
            HIGHEST_STABLE_STAGE,
        )
        return HIGHEST_STABLE_STAGE
    return value


def is_mapping_enabled() -> bool:
    """映射（`mapping.project()` 的字段回填）是否生效——阶段 2 起为真。"""
    return current_stage() >= 2.0


def is_aggregation_key_v2() -> bool:
    """聚合键是否已切三元组（`notify_event × correlation_id × target_id`）——阶段 2.5 起为真。

    注意：阶段 2a/2b **不消费**本谓词——聚合键在 2.5 才切换（见 03-实施路径.md §3.3）。
    """
    return current_stage() >= 2.5


def is_interaction_enabled() -> bool:
    """交互能力（回调端点 + 动作）是否启用——阶段 3 起为真。"""
    return current_stage() >= 3.0
