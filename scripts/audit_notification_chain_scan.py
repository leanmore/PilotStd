#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""事件通知全链路审计工具 · 静态扫描库（被入口脚本引用）。

纯静态分析（不连接数据库、不发网络请求），仅使用 Python 标准库。
职责：从代码库提取事件清单、构建器映射、调用点，并检测吞错模式。
入口：scripts/audit_notification_chain.py（参数解析、过滤、报告输出）。

能力：
  1. 自动扫描 events.py 提取事件清单（ALL_EVENTS 字符串字面量）
  2. 自动扫描 _builders*.py 提取构建器映射（_build_*_message 函数 + event_type 字段）
  3. 自动检测空值守卫缺失（builder 入口对必填字段无 if not x 检查）
  4. 自动检测 except: pass / 静默吞错模式
  5. 调用点采集（send_event / notify / push 全库）
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

# ── 项目根（脚本位于 scripts/ 下） ─────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
NOTIFICATION_DIR = ROOT / "pilotstd" / "core" / "notification"
EVENTS_FILE = NOTIFICATION_DIR / "events.py"
BUILDERS_PATTERN = re.compile(r"_builders.*\.py$")

# 需要扫描的调用点目录（事件触发方）
CALL_SITE_DIRS = [ROOT / "pilotstd", ROOT / "docker"]

# 事件名前缀 → 模块关键词（--module 过滤）
MODULE_KEYWORDS = {
    "favorite": ("favorite",),
    "download": ("download",),
    "archive": ("archive",),
    "announce": ("announce",),
    "query": ("query",),
    "validity": ("validity",),
    "scan": ("scan",),
    "normalize": ("normalize",),
    "backup": ("backup",),
}


def _load_ast(path: Path):
    """读取文件并解析为 AST；失败返回 None（不中断审计）。"""
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError):
        return None


# ── 1. 事件清单提取 ────────────────────────────────────────────────────────

def extract_events(events_file: Path) -> list[dict]:
    """从 events.py 提取事件定义。

    策略（按优先级）：
      1. ALL_EVENTS = [EventDef("key"), ...] 字面量（唯一数据源）
      2. 兜底：EVENT_XXX = "key" 常量赋值
    """
    events: list[dict] = []
    tree = _load_ast(events_file)
    if tree is None:
        return events

    # 预扫描：EVENT_XXX = "key" 常量符号表（用于解析 ALL_EVENTS 中的 Name 引用）
    const_map: dict[str, str] = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id.startswith("EVENT_")
        ):
            const_map[node.targets[0].id] = node.value.value

    # 策略 1：ALL_EVENTS 列表（可能是 Assign 或 AnnAssign `ALL_EVENTS: list[EventDef] = [...]`）
    for node in ast.walk(tree):
        target_names: list[str] = []
        value_node = None
        if isinstance(node, ast.Assign):
            target_names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            value_node = node.value
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                target_names = [node.target.id]
            value_node = node.value
        if "ALL_EVENTS" not in target_names or not isinstance(value_node, ast.List):
            continue
        for elt in value_node.elts:
            # EventDef("key") / EventDef(EVENT_X) / EventDef("key", bypass_aggregation=True)
            if isinstance(elt, ast.Call) and isinstance(elt.func, ast.Name) and elt.func.id == "EventDef":
                key: str | None = None
                for a in elt.args:
                    if isinstance(a, ast.Constant) and isinstance(a.value, str):
                        key = a.value
                    elif isinstance(a, ast.Name):
                        key = const_map.get(a.id)
                    if key is not None:
                        break
                bypass = False
                for kw in elt.keywords:
                    if kw.arg == "bypass_aggregation" and isinstance(kw.value, ast.Constant):
                        bypass = bool(kw.value.value)
                if key is not None:
                    events.append({"key": key, "bypass_aggregation": bypass})
        if events:
            return events

    # 策略 2：EVENT_XXX = "key" 常量（无 ALL_EVENTS 时兜底）
    for key, value in const_map.items():
        events.append({"key": value, "bypass_aggregation": False})
    return events


# ── 2. 构建器映射提取 ──────────────────────────────────────────────────────

def _func_has_return_notification_message(func: ast.FunctionDef) -> bool:
    """粗略判断函数是否返回通知消息（存在返回消息构造调用的分支）。"""
    for node in ast.walk(func):
        if (
            isinstance(node, ast.Return)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "NotificationMessage"
        ):
            return True
    return False


def _extract_event_type_from_func(func: ast.FunctionDef) -> str | None:
    """从函数体内事件类型关键字提取事件名。"""
    for node in ast.walk(func):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "NotificationMessage"
        ):
            for kw in node.keywords:
                if kw.arg == "event_type" and isinstance(kw.value, ast.Constant):
                    return str(kw.value.value)
    return None


def _missing_null_guards(func: ast.FunctionDef, used_fields: set[str]) -> list[str]:
    """检测空值守卫缺失。

    识别两种守卫形态：
      1. if not data.get("field"): / if data.get("field") is None:
      2. 先赋值局部变量 field_var = data.get("field")，再 if not field_var: / if field_var:
    对每个读取的字段，命中任一形态 → 视为有守卫；否则标记"缺守卫"（P2 提示）。
    """
    # 形态 2 的映射：data.get("field") → 局部变量名
    field_to_var: dict[str, str] = {}
    for node in ast.walk(func):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            value = node.value
            if (
                isinstance(target, ast.Name)
                and isinstance(value, ast.Call)
                and isinstance(value.func, ast.Attribute)
                and isinstance(value.func.value, ast.Name)
                and value.func.value.id == "data"
                and value.func.attr == "get"
                and value.args
                and isinstance(value.args[0], ast.Constant)
                and isinstance(value.args[0].value, str)
            ):
                field_to_var[value.args[0].value] = target.id

    guarded: set[str] = set()
    for node in ast.walk(func):
        if isinstance(node, ast.If):
            test = node.test
            # 形态 1a：if not data.get("x"):
            if (
                isinstance(test, ast.UnaryOp)
                and isinstance(test.op, ast.Not)
                and isinstance(test.operand, ast.Call)
            ):
                call = test.operand
                if (
                    isinstance(call.func, ast.Attribute)
                    and isinstance(call.func.value, ast.Name)
                    and call.func.value.id == "data"
                    and call.func.attr == "get"
                    and call.args
                    and isinstance(call.args[0], ast.Constant)
                ):
                    guarded.add(str(call.args[0].value))
            # 形态 1b：if data.get("x") is None:
            elif (
                isinstance(test, ast.Compare)
                and len(test.comparators) == 1
                and isinstance(test.comparators[0], ast.Constant)
                and test.comparators[0].value is None
                and isinstance(test.left, ast.Call)
                and isinstance(test.left.func, ast.Attribute)
                and test.left.func.attr == "get"
                and test.left.args
                and isinstance(test.left.args[0], ast.Constant)
            ):
                guarded.add(str(test.left.args[0].value))
            # 形态 2：if not field_var:（field_var 来自 data.get）
            if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not) and isinstance(
                test.operand, ast.Name
            ):
                var = test.operand.id
                for f, v in field_to_var.items():
                    if v == var:
                        guarded.add(f)
            # 形态 2b：if field_var:（存在性判断）
            elif isinstance(test, ast.Name) and test.id in field_to_var.values():
                for f, v in field_to_var.items():
                    if v == test.id:
                        guarded.add(f)
    missing = sorted(f for f in used_fields if f not in guarded)
    return missing


def _used_fields(func: ast.FunctionDef) -> set[str]:
    """提取构建器内 data.get("field") 的所有字段名。"""
    fields: set[str] = set()
    for node in ast.walk(func):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "data"
            and node.func.attr == "get"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            fields.add(node.args[0].value)
    return fields


def _return_empty_text_risk(func: ast.FunctionDef) -> bool:
    """返回空串风险：正文字段从未被赋值（构建器只填结构块），或存在空串返回分支。

    判定：函数内消息构造调用中未出现正文关键字参数，
    且存在无值返回或空串返回的分支 → 视为"返回空串风险"（P1 级提示）。
    """
    has_body_kwarg = False
    empty_return = False
    for node in ast.walk(func):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "NotificationMessage"
        ):
            for kw in node.keywords:
                if kw.arg == "body":
                    has_body_kwarg = True
        if isinstance(node, ast.Return) and (
            node.value is None
            or (
                isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
                and node.value.value == ""
            )
        ):
            empty_return = True
    # 结构块全部由渲染器消费；若正文从未赋值则聚合路径会渲染空文本
    return (not has_body_kwarg) or empty_return


def extract_builders() -> list[dict]:
    """扫描构建器文件，提取构建器元信息。"""
    builders: list[dict] = []
    if not NOTIFICATION_DIR.exists():
        return builders
    for path in sorted(NOTIFICATION_DIR.glob("*.py")):
        if not BUILDERS_PATTERN.search(path.name):
            continue
        tree = _load_ast(path)
        if tree is None:
            continue
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
                "_build_"
            ) and node.name.endswith("_message"):
                event_type = _extract_event_type_from_func(node)
                used = _used_fields(node)
                missing = _missing_null_guards(node, used)
                empty_risk = _return_empty_text_risk(node)
                builders.append(
                    {
                        "builder": node.name,
                        "file": str(path.relative_to(ROOT)),
                        "lineno": node.lineno,
                        "event_type": event_type,
                        "payload_fields": sorted(used),
                        "missing_null_guards": missing,
                        "empty_text_risk": empty_risk,
                    }
                )
    return builders


# ── 3. 吞错模式检测 ────────────────────────────────────────────────────────

def _is_pass_body(node: ast.expr | None) -> bool:
    """判断异常处理体是否仅为空操作（静默吞错）。"""
    if node is None:
        return True  # 无类型但体为空操作已在调用方处理
    return isinstance(node, ast.Pass)


def detect_swallowed_exceptions(scope: str = "notification") -> list[dict]:
    """扫描通知目录（默认）或全库（scope=all）中的静默吞错模式。"""
    findings: list[dict] = []
    if scope == "all":
        dirs = [ROOT / "pilotstd", ROOT / "docker"]
    else:
        dirs = [NOTIFICATION_DIR]
    seen: set[tuple[str, int]] = set()

    for d in dirs:
        for path in sorted(d.rglob("*.py")):
            tree = _load_ast(path)
            if tree is None:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.ExceptHandler):
                    continue
                body = node.body
                # 异常处理体仅为空操作（单语句）
                if len(body) == 1 and isinstance(body[0], ast.Pass):
                    key = (str(path.relative_to(ROOT)), node.lineno)
                    if key in seen:
                        continue
                    seen.add(key)
                    exc_name = None
                    if node.type is not None:
                        if isinstance(node.type, ast.Name):
                            exc_name = node.type.id
                        elif isinstance(node.type, ast.Attribute):
                            exc_name = node.type.attr
                    findings.append(
                        {
                            "file": str(path.relative_to(ROOT)),
                            "lineno": node.lineno,
                            "pattern": f"except {exc_name or ''}: pass".strip(),
                            "severity": "P1" if exc_name == "Exception" else "P2",
                        }
                    )
    return findings


# ── 4. 调用点采集 ──────────────────────────────────────────────────────────

def extract_call_sites() -> list[dict]:
    """扫描事件发送调用点（全库）。"""
    sites: list[dict] = []
    for d in CALL_SITE_DIRS:
        if not d.exists():
            continue
        for path in sorted(d.rglob("*.py")):
            tree = _load_ast(path)
            if tree is None:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                fname = None
                if isinstance(func, ast.Attribute):
                    fname = func.attr
                elif isinstance(func, ast.Name):
                    fname = func.id
                if fname not in ("send_event", "notify", "push"):
                    continue
                event_type = None
                if node.args:
                    if isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                        event_type = node.args[0].value
                    elif isinstance(node.args[0], ast.Name):
                        event_type = f"<const:{node.args[0].id}>"
                payload_keys: list[str] = []
                if len(node.args) > 1 and isinstance(node.args[1], (ast.Dict, ast.Call)):
                    payload_keys = ["<dict>"]
                for kw in node.keywords:
                    if kw.arg == "event_type" and isinstance(kw.value, ast.Constant):
                        event_type = str(kw.value.value)
                sites.append(
                    {
                        "file": str(path.relative_to(ROOT)),
                        "lineno": node.lineno,
                        "function": fname,
                        "event_type": event_type,
                        "payload": payload_keys,
                    }
                )
    return sites
