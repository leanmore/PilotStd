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
# 消息 dataclass 构造名：其字段普遍可空（见 channel.py / blocks.py），
# 故 `field=data.get("field")` 传入 None 属合法用法，不计为"缺空值守卫"。
_MESSAGE_CLASSES = frozenset(
    {"NotificationMessage", "ListBlock", "TextBlock", "KeyValueBlock", "StatusChangeBlock"}
)

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



# ── 空值护栏 AST 助手（实现在 `_chain_scan_guards.py`；T-41/2-A 拆分，此处**再导出**保持公开面）──
# `__all__` 同时承担两件事：① 声明对外公开面（含再导出的助手族名字）；② 让再导出不被 ruff 视为未使用。
__all__ = [
    "BUILDERS_PATTERN",
    "CALL_SITE_DIRS",
    "EVENTS_FILE",
    "NOTIFICATION_DIR",
    "ROOT",
    "_field_of_guarded_value",
    "_fields_in_test",
    "_has_nonempty_message_kwarg",
    "_is_bare_data_read",
    "_is_data_get",
    "_load_ast",
    "_missing_null_guards",
    "_return_empty_text_risk",
    "_subscript_field",
    "_used_fields",
    "detect_swallowed_exceptions",
    "event_const_map",
    "extract_builders",
    "extract_call_sites",
    "extract_events",
    "load_event_const_map",
]

from _chain_scan_guards import (  # noqa: E402
    _field_of_guarded_value,
    _fields_in_test,
    _has_nonempty_message_kwarg,
    _is_bare_data_read,
    _is_data_get,
    _load_ast,
    _missing_null_guards,
    _return_empty_text_risk,
    _subscript_field,
    _used_fields,
)

# ── 1. 事件清单提取 ────────────────────────────────────────────────────────

def event_const_map(tree: ast.Module) -> dict[str, str]:
    """构建 `EVENT_XXX = "key"` 常量符号表（模块级共享）。

    事件定义侧与构建器侧共用同一符号表——否则两侧解析口径不一致（A-3 的成因）。
    """
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
    return const_map


_CONST_MAP_CACHE: dict[str, dict[str, str]] = {}


def load_event_const_map() -> dict[str, str]:
    """读取 EVENTS_FILE 并返回常量符号表（带缓存）。"""
    key = str(EVENTS_FILE)
    if key not in _CONST_MAP_CACHE:
        tree = _load_ast(EVENTS_FILE)
        _CONST_MAP_CACHE[key] = event_const_map(tree) if tree is not None else {}
    return _CONST_MAP_CACHE[key]


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

    const_map = event_const_map(tree)

    # 策略 1：ALL_EVENTS 列表（可能是 Assign 或 AnnAssign 赋值形态）
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

def _extract_event_type_from_func(func: ast.FunctionDef) -> str | None:
    """从函数体内 `event_type=` 提取事件名，**同时解析 EVENT_* 常量名**（A-3 修复）。

    A-3 的成因：原实现只认 `ast.Constant` 字面量，遇到 `event_type=EVENT_ARCHIVE_COMPLETE`
    这类常量名即返回 None → 构建器与事件配对断裂、`--module` 过滤漏项。
    现从模块级共享的常量符号表解析；**不在表中的 Name 一律返回 None**
    （不臆造解析——避免"过度解析"引入新误报）。
    """
    const_map = load_event_const_map()
    for node in ast.walk(func):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "NotificationMessage"
        ):
            continue
        for kw in node.keywords:
            if kw.arg != "event_type":
                continue
            value = kw.value
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                return value.value
            if isinstance(value, ast.Name):
                # 常量名 → 解析为字面量；不在符号表中则视为动态（无法静态确定）
                return const_map.get(value.id)
    return None















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

def _resolve_event_arg(arg: ast.expr, params: frozenset[str]) -> str | None:
    """解析 send_event 的第 1 个实参为事件名（A-3 修复的核心）。

    优先级：
      1. 字符串字面量 → 直接返回；
      2. `EVENT_*` 常量名 → 从**模块级共享的常量符号表**解析（原实现只标记
         `<const:EVENT_X>` 而不解析，导致构建器/事件配对断裂、`--module` 过滤漏项）；
      3. 其它 `ast.Name`（含函数形参）→ 返回 `"<dynamic>"`。
         **不臆造解析**——不在符号表中的名字一律视为动态，避免"过度解析"引入新误报；
         形参尤其如此（同一个函数可被多处调用、传入不同事件）。
    """
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value
    if isinstance(arg, ast.Name):
        const_map = load_event_const_map()
        if arg.id in const_map:
            return const_map[arg.id]
        if arg.id in params:
            return "<dynamic>"  # 形参：静态无法确定唯一事件
        return "<dynamic>"
    return None


def extract_call_sites() -> list[dict]:
    """扫描事件发送调用点（全库）。

    A-3 修复：第一实参为 `EVENT_*` 常量名时解析为字面量；无法静态确定者标 `<dynamic>`。
    """
    sites: list[dict] = []
    for d in CALL_SITE_DIRS:
        if not d.exists():
            continue
        for path in sorted(d.rglob("*.py")):
            tree = _load_ast(path)
            if tree is None:
                continue
            # 逐作用域遍历，**每个 Call 只记一次**。
            # 注意：不能用 `ast.walk(tree)` 再对每个函数各走一遍——那会把每个函数
            # 重复扫 N 次（实测把调用点数从 50 膨胀到 74622）。
            fn_nodes = [
                n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            nested_ids = {
                id(inner)
                for fn in fn_nodes
                for inner in ast.walk(fn)
                if isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef)) and inner is not fn
            }
            scopes: list[tuple[ast.AST, frozenset[str]]] = [(tree, frozenset())]
            for fn in fn_nodes:
                if id(fn) in nested_ids:
                    continue  # 嵌套函数已由其所属外层作用域覆盖
                params = frozenset(
                    a.arg
                    for a in list(fn.args.args) + list(fn.args.kwonlyargs) + list(fn.args.posonlyargs)
                )
                if fn.args.vararg:
                    params |= {fn.args.vararg.arg}
                if fn.args.kwarg:
                    params |= {fn.args.kwarg.arg}
                scopes.append((fn, params))

            seen: set[tuple[str, int]] = set()
            for scope, params in scopes:
                for node in ast.walk(scope):
                    if not isinstance(node, ast.Call):
                        continue
                    key = (str(path), node.lineno)
                    if key in seen:
                        continue
                    func = node.func
                    fname = None
                    if isinstance(func, ast.Attribute):
                        fname = func.attr
                    elif isinstance(func, ast.Name):
                        fname = func.id
                    if fname not in ("send_event", "notify", "push"):
                        continue
                    seen.add(key)
                    event_type = None
                    if node.args:
                        event_type = _resolve_event_arg(node.args[0], params)
                    payload_keys: list[str] = []
                    if len(node.args) > 1 and isinstance(node.args[1], (ast.Dict, ast.Call)):
                        payload_keys = ["<dict>"]
                    for kw in node.keywords:
                        if kw.arg == "event_type":
                            event_type = _resolve_event_arg(kw.value, params)
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
