# 模块：源码//脚本
# 类型契约—三位一体治理体系5强制层
# 分隔
# 规范基准://---版本二§4.2
# 版本:表结构_=1.0,_=2.0

from __future__ import annotations

from typing import Any, Dict, List, TypedDict


class CleanupReport(TypedDict):
    """上一会话清理结果报告。"""

    archived_items: int
    failed_items: int
    last_run_timestamp: str


class Signal(TypedDict):
    """待处理治理信号。"""

    id: str
    type: str
    payload: Dict[str, Any]
    priority: int


class BootstrapResult(TypedDict):
    """会话引导返回值强契约 — 四字段缺一不可。

    字段语义:
      - context: 当前会话上下文快照（从 local-session-notes.md 解析）
      - signals: 待处理信号队列（规则固化信号、决策记录、假设失效等）
      - cleanup_result: 上一会话清理结果（过期锚点/决策记录/失效记录）
      - metadata: 版本号、引导耗时等扩展元数据

    metadata 约定键:
      - version (str): 规范文档版本，用于人工对齐。如 "2.0"
      - schema_version (str): 数据结构版本，用于机器解析兼容性。如 "1.0"
      - bootstrap_duration_ms (str): 引导耗时（毫秒）
      - session_id (str): 会话标识

    契约约束:
      - 四字段缺一不可，缺失任一字段时 session_bootstrap() 必须抛出 EnforcementError
      - metadata 必须包含 version 和 schema_version 两个键
    """

    context: Dict[str, Any]
    signals: List[Signal]
    cleanup_result: CleanupReport
    metadata: Dict[str, str]


# 受保护治理文档路径（-+持续集成强制校验）
PROTECTED_GOVERNANCE_PATHS = (
    "docs/governance/prompt-crafting-guide.md",
    "docs/governance/rule-quickref.md",
    "docs/governance/development-flow.md",
    "docs/governance/trinity-technical-spec-v2.md",
    "docs/governance/phase1-startup-checklist.md",
)

# 原子写入调用栈白名单（阶段1）
ALLOWED_CALLERS = frozenset(
    {
        "claude_code",
        "post_execution_hook",
        "session_bootstrap",
    }
)
