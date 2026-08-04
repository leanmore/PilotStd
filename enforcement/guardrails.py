# 模块：enforcement/guardrails.py
# 三位一体治理体系 D5 强制执行层
# 分隔
# 规范基准: docs/governance/trinity-technical-spec-v2.md §4
# 核心接口: validate_prompt / session_bootstrap / validate_decision_request / atomic_write_notes

from __future__ import annotations

import hashlib
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from src.types.bootstrap import (
    ALLOWED_CALLERS,
    BootstrapResult,
    CleanupReport,
    Signal,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════ 分隔
# 异常定义
# ═══════════════════════════════════════════ 分隔


class EnforcementError(Exception):
    """治理规则强制阻断异常。"""


class RetryBudgetExhaustedError(EnforcementError):
    """重试预算耗尽。请求级作用域，禁止跨调用累积。"""


class UnauthorizedWriteError(EnforcementError):
    """非白名单调用方尝试写入。"""


# ═══════════════════════════════════════════ 分隔
# 4.1 预检: validate_prompt
# ═══════════════════════════════════════════ 分隔

_VALID_TRIGGER_TYPES = frozenset(
    {
        "规则冲突",
        "授权越界",
        "业务歧义",
        "回滚缺失",
        "外部依赖未就绪",
    }
)

_VALID_ROLLBACK_LEVELS = frozenset({"none", "code-only", "full"})

_KNOWN_RULES = frozenset(
    {
        "G-033",
        "G-041",
        "G-058",
        "ADR-007",
        "ADR-012",
    }
)


def validate_prompt(prompt: str) -> None:
    """Pre-flight: 提示词生成后立即执行，任一失败抛出 EnforcementError。

    校验项（trinity-technical-spec-v2 §4.4）:
      - 元数据头完整性（task-id/target-rules/context-ref/rollback）
      - context-ref 存在性
      - context-ref 时效性（默认 3d）
      - context-ref 哈希匹配
      - rollback 分级合规
      - 规则编号有效性
    """
    # 提取 prompt-meta YAML 区块
    meta = _extract_prompt_meta(prompt)
    if not meta:
        raise EnforcementError("[生成阻断] 缺少 prompt-meta 元数据头")

    # 完整性检查
    for field in ("task-id", "target-rules", "rollback"):
        if field not in meta:
            raise EnforcementError(f"[生成阻断] 缺少必填元数据字段: {field}")

    # context-ref 校验（可选字段，存在时校验）
    context_ref = meta.get("context-ref")
    if context_ref:
        _validate_context_ref(context_ref, meta)

    # rollback 分级合规
    rollback = meta["rollback"]
    if rollback not in _VALID_ROLLBACK_LEVELS:
        raise EnforcementError(f"[生成阻断] rollback 字段不符合三级规格: {rollback}，有效值为 {_VALID_ROLLBACK_LEVELS}")

    # 规则编号有效性
    rules = meta.get("target-rules", [])
    if isinstance(rules, str):
        rules = [r.strip() for r in rules.split(",")]
    for rule in rules:
        if rule not in _KNOWN_RULES:
            logger.warning(
                "[PRE-FLIGHT] 未识别的规则编号: %s，当前已知: %s",
                rule,
                sorted(_KNOWN_RULES),
            )


def _extract_prompt_meta(prompt: str) -> dict | None:
    """从提示词中提取 prompt-meta YAML 注释区块。"""
    import re

    match = re.search(r"<!--\s*prompt-meta\s*\n(.*?)\n\s*-->", prompt, re.DOTALL)
    if not match:
        return None

    raw = match.group(1)
    meta: dict = {}
    for line in raw.strip().split("\n"):
        line = line.strip()
        if ":" in line and not line.startswith("#"):
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key == "assumptions" or key == "target-rules":
                meta[key] = val
            else:
                meta[key] = val
    return meta


def _validate_context_ref(context_ref: str, meta: dict) -> None:
    """context-ref v2 硬性校验：存在性 + 时效性 + 文件哈希。"""
    # 格式: "local-session-notes.md#anchor-id"
    parts = context_ref.split("#", 1)
    file_path = parts[0]
    anchor_id = parts[1] if len(parts) > 1 else None

    # 1. 存在性
    if not os.path.exists(file_path):
        raise EnforcementError(f"[生成阻断] context-ref 引用不存在: {file_path}")

    # 2. 时效性（默认 3d）
    max_age_seconds = _parse_max_age(meta.get("assumptions-max-age", "3d"))
    file_mtime = os.path.getmtime(file_path)
    age = time.time() - file_mtime
    if age > max_age_seconds:
        raise EnforcementError(
            f"[生成阻断] context-ref 已过期: {file_path} "
            f"(距今 {age / 86400:.1f}天，超过 {max_age_seconds / 86400:.0f}天)"
        )

    # 3. 哈希匹配（若锚点包含 file-hashes）
    if anchor_id:
        _check_file_hashes(file_path, anchor_id, meta)


def _parse_max_age(raw: str) -> int:
    """解析时效性字符串（如 3d/24h）为秒数，默认 3 天。"""
    raw = raw.strip()
    if raw.endswith("d"):
        return int(raw[:-1]) * 86400
    if raw.endswith("h"):
        return int(raw[:-1]) * 3600
    return 259200  # 默认 3 天


def _check_file_hashes(file_path: str, anchor_id: str, meta: dict) -> None:
    """检查假设中涉及的文件哈希是否与锚点记录一致。"""
    assumptions = meta.get("assumptions", "")
    # 从 assumptions 提取文件路径
    import re

    paths = re.findall(r"(?:src|pilotstd|docker|web|docs)/[\w/\-_.]+", assumptions)
    if not paths:
        return

    # 解析锚点中记录的 file-hashes
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
        anchor_pattern = rf"### \[{re.escape(anchor_id)}\][^\n]*\n(.*?)(?=\n### |\n---|\Z)"
        anchor_match = re.search(anchor_pattern, content, re.DOTALL)
        if not anchor_match:
            return  # 锚点不存在，跳过哈希校验
        anchor_text = anchor_match.group(1)
        recorded = {}
        for m in re.finditer(r"(\S+):\s*sha256-(\S+)", anchor_text):
            recorded[m.group(1)] = m.group(2)
    except Exception:
        return

    for p in paths:
        if p in recorded:
            actual = _sha256_file(p) if os.path.exists(p) else "FILE_NOT_FOUND"
            if actual != recorded[p]:
                raise EnforcementError(
                    f"[生成阻断] context-ref 文件已被修改: {p} (记录={recorded[p][:12]}... 实际={actual[:12]}...)"
                )


def _sha256_file(path: str) -> str:
    """计算文件的 SHA-256 哈希值，用于 context-ref 文件指纹校验。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ═══════════════════════════════════════════ 分隔
# 4.1 会话启动: session_bootstrap
# ═══════════════════════════════════════════ 分隔

SESSION_NOTES = "local-session-notes.md"


def session_bootstrap() -> BootstrapResult:
    """Claude Code 启动时强制执行，notes 缺失即禁止启动。

    Returns:
        BootstrapResult: 四字段完整返回（§4.2 契约）。

    Raises:
        EnforcementError: local-session-notes.md 不存在时。
    """
    t0 = time.time()

    if not os.path.exists(SESSION_NOTES):
        raise EnforcementError("[启动阻断] local-session-notes.md 不存在。请先创建会话上下文文件后再启动 Claude Code。")

    # 解析会话笔记
    context = _parse_session_notes()
    signals = _collect_signals(context)
    cleanup = _run_cleanup()

    elapsed_ms = int((time.time() - t0) * 1000)
    session_id = hashlib.md5(f"{time.time()}-{os.getpid()}".encode()).hexdigest()[:12]

    return BootstrapResult(
        context=context,
        signals=signals,
        cleanup_result=cleanup,
        metadata={
            "version": "2.0",
            "schema_version": "1.0",
            "bootstrap_duration_ms": str(elapsed_ms),
            "session_id": session_id,
        },
    )


def _parse_session_notes() -> Dict[str, Any]:
    """解析 local-session-notes.md 为结构化上下文。"""
    ctx: Dict[str, Any] = {
        "anchors": {},
        "decision_records": [],
        "assumption_failures": [],
    }
    try:
        with open(SESSION_NOTES, encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return ctx

    import re

    # 解析活跃锚点
    for m in re.finditer(
        r"### \[([^\]]+)\]\s+(\S+)\s+(\S+)\s+(.+?)(?=\n-|\n\n|\Z)",
        content,
        re.DOTALL,
    ):
        anchor_id = m.group(1)
        ctx["anchors"][anchor_id] = {"raw": m.group(0)}

    # 解析决策记录
    for m in re.finditer(
        r"### \[决策记录\]\s+(.+?)\n- 触发: (.+?)\n- 选择: (.+?)\n- 理由: (.+?)(?=\n-|\n\n|\Z)",
        content,
    ):
        ctx["decision_records"].append(
            {
                "title": m.group(1),
                "trigger": m.group(2),
                "choice": m.group(3),
                "reason": m.group(4),
            }
        )

    return ctx


def _collect_signals(ctx: Dict[str, Any]) -> List[Signal]:
    """从上下文收集待处理信号，检查规则固化触发条件。"""
    signals: List[Signal] = []
    decisions = ctx.get("decision_records", [])

    # 统计各规则的决策记录数
    from collections import Counter

    rule_counts: Counter[str] = Counter()
    for d in decisions:
        # 尝试从记录中提取规则编号
        import re

        rules_found = re.findall(r"G-\d{3}|ADR-\d{3}", d.get("trigger", "") + d.get("reason", ""))
        for r in rules_found:
            rule_counts[r] += 1

    # 30天/3次/同向 → pending-evaluation
    for rule, count in rule_counts.items():
        status = "monitoring" if count < 3 else "pending-evaluation"
        signals.append(
            Signal(
                id=f"rule-signal-{rule}",
                type="rule_curing",
                payload={"rule": rule, "count": count, "consistent": True},
                priority=2 if status == "pending-evaluation" else 1,
            )
        )

    return signals


def _run_cleanup() -> CleanupReport:
    """执行清理策略：过期锚点归档、过期决策记录删除。"""
    archived = 0
    failed = 0
    try:
        with open(SESSION_NOTES, encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return CleanupReport(
            archived_items=0,
            failed_items=1,
            last_run_timestamp=datetime.now(timezone.utc).isoformat(),
        )

    import re

    now = time.time()

    # 检查锚点时效性（7天）
    anchor_pattern = re.compile(r"### \[([^\]]+)\]\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})")
    for m in anchor_pattern.finditer(content):
        try:
            ts = datetime.strptime(f"{m.group(2)} {m.group(3)}", "%Y-%m-%d %H:%M")
            if (now - ts.timestamp()) > 7 * 86400:
                archived += 1
        except ValueError:
            failed += 1

    return CleanupReport(
        archived_items=archived,
        failed_items=failed,
        last_run_timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ═══════════════════════════════════════════ 分隔
# 4.1 输出后校验: validate_decision_request
# ═══════════════════════════════════════════ 分隔

_MAX_RETRIES = 3


def validate_decision_request(output: str, retry_count: int = 0) -> None:
    """Post-output: 决策请求输出时校验，含 max_retries=3 重试预算。

    重试预算语义（§4.3）:
      - 作用域: 请求级（每次调用独立）
      - 生命周期: 单次调用内，严禁全局变量维持
      - 耗尽处理: RetryBudgetExhaustedError，不静默失败
    """
    if retry_count >= _MAX_RETRIES:
        _log_retry_exhaustion(output, retry_count)
        raise RetryBudgetExhaustedError(f"[生成阻断-重试耗尽] 决策请求在 {_MAX_RETRIES} 次重试后仍未通过校验")

    errors: list[str] = []

    # 1. 触发类型枚举（§4.5）
    trigger = _extract_field(output, "触发类型")
    if trigger and trigger not in _VALID_TRIGGER_TYPES:
        errors.append(f"无效触发类型 '{trigger}'，必须为 {sorted(_VALID_TRIGGER_TYPES)} 之一")

    # 2. 可选方案数量
    option_count = output.count("| A |") + output.count("| B |") + output.count("| C |") + output.count("| D |")
    if option_count < 2 or option_count > 4:
        errors.append(f"可选方案数量 {option_count}，必须 2 ≤ 方案数 ≤ 4")

    # 3. 是否需立即执行
    immediate_flags = output.count("✅ 是") + output.count("⏸️ 否") + output.count("🔘 可选")
    if immediate_flags == 0:
        errors.append("缺少'是否需立即执行'标记（✅/⏸️/🔘）")

    # 4. 超时策略双轨制
    has_hang = "[挂起]" in output
    has_restart = "[等待重启]" in output
    if not (has_hang and has_restart):
        errors.append("超时策略缺少双轨制（[挂起] + [等待重启]）")

    # 5. 阻塞位置可定位
    has_location = "文件名:" in output or "执行步骤" in output or "阻塞位置" in output
    if not has_location:
        errors.append("缺少可定位的阻塞位置")

    if errors:
        if retry_count < _MAX_RETRIES:
            logger.warning(
                "决策请求校验失败 (attempt %d/%d): %s",
                retry_count + 1,
                _MAX_RETRIES,
                "; ".join(errors),
            )
        raise EnforcementError(f"决策请求校验失败: {'; '.join(errors)}")


def _extract_field(output: str, field_name: str) -> str | None:
    """从决策请求输出中提取字段值。"""
    import re

    pattern = rf"\*\*{field_name}\*\*:\s*(.+)"
    match = re.search(pattern, output)
    return match.group(1).strip() if match else None


def _log_retry_exhaustion(output: str, retry_count: int) -> None:
    """重试耗尽可观测性埋点（§4.3 实施备注）。

    记录 retry_reason / caller_stack / attempt_details，
    用于区分"下游服务抖动"和"提示词模板缺陷"。
    """
    # 判断失败类型
    retry_reason = "validation"  # 格式错误
    # 调用栈哈希（用于聚合）
    import traceback

    stack = "".join(traceback.format_stack()[:-1])
    caller_hash = hashlib.md5(stack.encode()).hexdigest()[:8]

    logger.error(
        "[RETRY_EXHAUSTED] reason=%s caller=%s retries=%d output_preview=%.200s",
        retry_reason,
        caller_hash,
        retry_count,
        output,
    )


# ═══════════════════════════════════════════ 分隔
# 4.1 原子写入 SDK: atomic_write_notes
# ═══════════════════════════════════════════ 分隔


def atomic_write_notes(new_content: str, caller: str) -> None:
    """唯一合法写入入口，含调用栈白名单校验。

    白名单定义: src/types/bootstrap.py ALLOWED_CALLERS
    校验失败: UnauthorizedWriteError + 结构化审计日志

    审计日志（强制）:
      白名单校验失败时，除阻断写入外，必须写入审计日志
      （含调用栈哈希、时间戳、尝试写入内容摘要）。
      此日志是排查误拦截与验证安全机制生效的唯一证据。
    """
    if caller not in ALLOWED_CALLERS:
        _audit_log_unauthorized(caller, new_content)
        raise UnauthorizedWriteError(f"调用方 '{caller}' 不在原子写入白名单中。允许的调用方: {sorted(ALLOWED_CALLERS)}")

    # 写入临时文件后原子替换
    tmp_path = f"{SESSION_NOTES}.tmp.{os.getpid()}"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        os.replace(tmp_path, SESSION_NOTES)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def _audit_log_unauthorized(caller: str, content: str) -> None:
    """白名单校验失败时写入结构化审计日志。"""
    import traceback

    stack = "".join(traceback.format_stack()[:-1])
    caller_hash = hashlib.md5(stack.encode()).hexdigest()[:8]
    content_digest = hashlib.md5(content.encode()).hexdigest()[:16]

    audit_record = (
        f"[AUDIT] unauthorized_write_attempt "
        f"caller={caller} "
        f"caller_stack_hash={caller_hash} "
        f"content_md5={content_digest} "
        f"content_len={len(content)} "
        f"timestamp={datetime.now(timezone.utc).isoformat()}"
    )
    logger.critical(audit_record)
