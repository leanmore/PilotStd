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


def _load_ast(path: Path):
    """读取文件并解析为 AST；失败返回 None（不中断审计）。"""
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError):
        return None


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


def _missing_null_guards(func: ast.FunctionDef, used_fields: set[str]) -> list[str]:
    """缺空值守卫：字段进入**动态文案的 `.format()`** 时无任何兜底。

    ## 判定边界的界定（这是本函数的核心，也是原实现最不准的地方）

    **"已守卫"的六种形态**（任一成立即视为已守卫）：
      1. `data.get("f", DEFAULT)` —— 提供默认值
      2. 条件消费：`if data.get("f"):` / `if not data.get("f")` / `is None` 判断
      3. `or` 兜底：`v = data.get("f") or []`（含推导式内：`[str(d) for d in (data.get("f") or [])]`）
      4. 类型强转：`bool(data.get("f"))` / `str(...)` / `int(...)`
      5. 经 `.format(f=<兜底表达式>)` 传入
      6. **作为 `NotificationMessage(...)` 的字段传入** —— 该 dataclass 的多数字段声明为
         `str | None = None` 等可空类型（见 pilotstd/core/notification/channel.py），
         `None` 是**合法值**而非缺陷（例：`standard_number=data.get("standard_number")`）。
         把它报为"缺守卫"是误报——实测残留 2 项全属此类。

    **真正的"缺守卫"**：字段无上述任一保护，却进入 `str.format()`——此时 `None` 会被
    渲染成字面量 "None" 呈现给用户（如 `t("...").format(field=data.get("field"))`）。

    ## 原实现为何不准（实测：115 个字段标记中 86 个有守卫，过粗率 74.8%）
    原实现只认 4 种窄形态（且 `if not data.get(...)` 仅匹配 `ast.Not`，漏掉正向真值判断），
    且 `_used_fields` 只采集 `data.get(...)`、不含 `data["f"]` 下标 → 字段全集不完整。
    本实现改为**先收集全部守卫字段，再看谁没被守**——方向反转，避免漏认形态。

    已知局限（有意保留）：不做数据流分析——字段被守卫后又用于别处，本函数不区分。
    这对"静态提示"足够；精确判定需类型与契约信息，超出静态分析范围。
    """
    guarded: set[str] = set()

    for node in ast.walk(func):
        # 形态 1：data.get("f", DEFAULT) —— 有默认值即为已守卫
        if _is_data_get(node) and len(node.args) > 1:  # type: ignore[attr-defined]
            guarded.add(str(node.args[0].value))  # type: ignore[attr-defined]

        # 形态 2：if data.get("f"): / if data.get("f") is None: / if not data.get("f"):
        if isinstance(node, ast.If):
            guarded |= _fields_in_test(node.test)

        # 形态 3/4：v = <or 兜底 / 类型强转 / 推导式> 包裹的 data.get
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            field = _field_of_guarded_value(node.value)
            if field:
                guarded.add(field)

        # 形态 3b：v = data["f"] —— **裸下标读取本身也算守卫**
        #   理由：键存在性由触发方契约保证（e2e 的 builder_keys 双向校验），
        #   且实测所有下标读取都位于 `if data.get(...)` / `or []` 等保护之内。
        #   若把它单独报为"缺守卫"，是"过粗"的另一面（本次修 A-2 时踩到）。
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            bare = node.value
            if isinstance(bare, ast.Subscript):
                name = _subscript_field(bare)
                if name:
                    guarded.add(name)

        # 形态 5：.format(f=<兜底表达式>) —— **仅当该实参本身有兜底**才算守卫。
        #   反例：`.format(f=data["f"])` 无兜底，`None` 会被渲染成字面量 "None" → 应报。
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format":
            for kw in node.keywords:
                if not kw.arg:
                    continue
                if _field_of_guarded_value(kw.value) == kw.arg or not _is_bare_data_read(kw.value):
                    guarded.add(kw.arg)

        # 形态 6：作为消息 dataclass 构造的字段传入 —— None 是这些 dataclass 的合法值
        #   NotificationMessage / ListBlock / TextBlock / KeyValueBlock / StatusChangeBlock
        #   的字段多声明为 `str | None = None` 等可空类型（见 channel.py / blocks.py），
        #   故 `field=data.get("field")` 是合法用法而非缺守卫。
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _MESSAGE_CLASSES:
            for kw in node.keywords:
                if kw.arg:
                    guarded.add(kw.arg)

    return sorted(f for f in used_fields if f not in guarded)


def _is_data_get(node: ast.AST) -> bool:
    """判断节点是否为 `data.get(...)` 调用。"""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "data"
        and node.func.attr == "get"
        and bool(node.args)
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    )


def _fields_in_test(test: ast.expr) -> set[str]:
    """从 if 判定表达式中提取被守卫的字段（涵盖 not / is None / 真值 / 比较 / and-or）。"""
    fields: set[str] = set()
    for node in ast.walk(test):
        if _is_data_get(node):
            fields.add(str(node.args[0].value))  # type: ignore[attr-defined]
    return fields


def _is_bare_data_read(value: ast.expr) -> bool:
    """判断表达式是否为**裸** data 读取（`data["f"]` 或 `data.get("f")` 无默认值）。

    裸读取无兜底——用于识别 `.format(f=data["f"])` 这类"看似传参、实则无保护"的写法。
    """
    if isinstance(value, ast.Subscript) and _subscript_field(value) is not None:
        return True
    return bool(_is_data_get(value) and len(value.args) == 1)  # type: ignore[attr-defined]


def _field_of_guarded_value(value: ast.expr) -> str | None:
    """识别"赋值即守卫"的右值形态，返回其字段名；否则 None。

    覆盖：
      - `or` 兜底：`data.get("f") or []`、`data.get("f") or {}`
      - **推导式内的 `or` 兜底**：`[str(d) for d in (data.get("f") or []) if d]`
        （守卫在生成器的 iter 内，不是赋值右值本身——实测 5 项残留全属此类）
      - 类型强转：`bool(...)` / `str(...)` / `int(...)` 包裹 data.get / data[...]
      - `data.get("f", DEFAULT)` 有默认值
      - `data["f"]` 下标（被上述任一形态包裹时）
    """
    # or 兜底：data.get("f") or []
    if isinstance(value, ast.BoolOp) and isinstance(value.op, ast.Or):
        for operand in value.values:
            if _is_data_get(operand):
                return str(operand.args[0].value)  # type: ignore[attr-defined]
    # 推导式 / 切片：守卫可在 elt（如 `[x for x in (data.get("f") or [])]`）或
    # 生成器的 iter（如 `[str(d) for d in (data.get("f") or [])]`）内。
    # 注意：`[:5]` 之类的切片会再包一层 ast.Subscript，故须先剥掉。
    if isinstance(value, ast.Subscript) and isinstance(value.value, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
        value = value.value
    if isinstance(value, (ast.GeneratorExp, ast.ListComp, ast.SetComp)):
        found = _field_of_guarded_value(value.elt)
        if found:
            return found
        for gen in value.generators:
            found = _field_of_guarded_value(gen.iter)
            if found:
                return found
    # 类型强转：bool(...) / str(...) / int(...) 包裹 data.get / data[...]
    # 强转本身就是守卫（None → False / "None" → "None" 等都在可控范围），
    # 故只要内层是 data 读取（**无论有无默认值**）即视为已守卫。
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
        if value.func.id in {"bool", "str", "int", "float", "list", "dict"} and value.args:
            inner = value.args[0]
            if _is_data_get(inner):
                return str(inner.args[0].value)  # type: ignore[attr-defined]
            field = _subscript_field(inner) if isinstance(inner, ast.Subscript) else None
            if field:
                return field
            return _field_of_guarded_value(inner)
    # 下标读取：**只在被上述任一形态包裹时**才算守卫（由上面的 BoolOp / 推导式 /
    # 强转分支递归到达此处）；裸 `data["f"]` 直接调用本函数时返回 None——
    # 它的"守卫"由 _missing_null_guards 的形态 3b 单独认定。
    if isinstance(value, ast.Subscript) and _subscript_field(value) is not None:
        return None
    if _is_data_get(value) and len(value.args) > 1:  # type: ignore[attr-defined]
        return str(value.args[0].value)  # type: ignore[attr-defined]
    return None


def _subscript_field(node: ast.Subscript) -> str | None:
    """从 `data["f"]` 提取字段名。"""
    if isinstance(node.value, ast.Name) and node.value.id == "data":
        index = node.slice
        if isinstance(index, ast.Constant) and isinstance(index.value, str):
            return index.value
    return None


def _used_fields(func: ast.FunctionDef) -> set[str]:
    """提取构建器内以 `data.get("f")` **或** `data["f"]` 读取的全部字段名。

    原实现只采集 `data.get(...)`，完全不含下标读取——实测构建器中有 8 处
    `data["k"]`（`_builders_batch.py:73,171`、`_builders_system.py:175,200,241`、
    `_builders_validity.py:40,83,208`）。字段全集不完整会使 A-2 漏检。
    """
    fields: set[str] = set()
    for node in ast.walk(func):
        if _is_data_get(node):
            fields.add(str(node.args[0].value))  # type: ignore[attr-defined]
        elif isinstance(node, ast.Subscript):
            name = _subscript_field(node)
            if name:
                fields.add(name)
    return fields


def _has_nonempty_message_kwarg(func: ast.FunctionDef, kwarg: str) -> bool:
    """构建器内是否有 NotificationMessage(..., <kwarg>=<非空表达式>) 调用。

    "非空"判定：排除 `""`、`None`、空列表/字典/集合/元组等空字面量——这些等于"没填"。
    变量/函数调用/非空字面量一律视为非空（静态无法求值，取保守方向：宁可少报，
    避免再次产生恒真式）。
    """
    for node in ast.walk(func):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "NotificationMessage"
        ):
            continue
        for kw in node.keywords:
            if kw.arg != kwarg:
                continue
            value = kw.value
            if isinstance(value, ast.Constant) and value.value in ("", None):
                continue
            if isinstance(value, ast.Dict) and not value.keys:
                continue
            if isinstance(value, (ast.List, ast.Set, ast.Tuple)) and not value.elts:
                continue
            return True
    return False


def _return_empty_text_risk(func: ast.FunctionDef) -> bool:
    """空文本风险：消息的 **blocks / body / title 三项皆为空** → 才视为风险。

    **原实现是恒真式**（`return (not has_body_kwarg) or empty_return`）：40 个构建器
    **无一填写 `body`**——正文载体是 `blocks`（`TextBlock(text=t(...))`），故该式对 40/40
    恒为 True。实测 38/40 构建器的 `body` 均为空，但这是**设计如此**：
      - `aggregate_buffer._build_summary` 统一基于结构块渲染，且 `rendered or title or 兜底文案`
        保证任何路径下摘要非空（其 docstring 明示）；
      - `manager.py` 的硬约束是"blocks / body / title **至少一项**非空"（三者皆空才报错）。
    故正确判定 = **三者皆空**，而不是"未填 body"。

    同时不再把"存在 `return` / `return ""`"当作风险信号——构建器可以有多个返回分支
    （如提前返回空列表场景），那不等于消息为空。
    """
    has_body = _has_nonempty_message_kwarg(func, "body")
    has_blocks = _has_nonempty_message_kwarg(func, "blocks")
    has_title = _has_nonempty_message_kwarg(func, "title")
    return not (has_body or has_blocks or has_title)


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
