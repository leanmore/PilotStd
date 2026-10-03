# 模块：脚本/门禁公共/通知渠道派生一致性审计脚本
"""G-045 的 **B 类**：渠道声明（`channel_spec.py`）与实现/前端之间的**跨层一致性**。

与 A 类的根本差别：A 类查"事件覆盖度"（数据完备性），B 类查"**派生一致性**"。
**每一项都必须锚定非派生对象**——若比较双方都由同一来源派生，断言会退化为恒真、
判别力归零（这正是 C1 替换掉的旧锁的毛病）。故四项分别锚在：

- **B1** `channels/*.py` **源码**里真实定义的子类名（不是 spec 的另一个视图）
- **B2** spec **自身**的结构约束（唯一来源的内部自洽）
- **B3** 后端**源码 AST**（不得残留"与渠道名常量比较"的写法）
- **B4** 前端**源码文本**（硬编码字面量的**棘轮** + 与 spec 的集合一致性）

设计依据：`docs/plans/notification-system-design/07-impl-design-A.md` §八。
"""

from __future__ import annotations

import ast
from pathlib import Path

from _frontend_channel_scan import FRONTEND_FILES, scan, structural_keys

# B 类检查项数（用于覆盖摘要的"检查项"计数）
B_RULE_COUNT = 4
# B3 的扫描范围（后端两个落点：渠道构造与配置接口）
BACKEND_SCAN_FILES: tuple[str, ...] = (
    "pilotstd/core/notification/manager.py",
    "docker/api/notification.py",
)
# B4 存量基线：C3（前端 schema 驱动改造）已落地，前端不再硬编码渠道键 ⇒ **基线归零**。
# 此前（C1..C2）为 26 行、缓阻断；归零后本项为**全阻断**：任何新增硬编码当场红灯。
FRONTEND_LITERAL_BASELINE = 0
# 允许的控件形态闭集（与 channel_spec.FIELD_TYPES 同源，由 AST 读取校验）
PASSWORD_TYPES = ("password", "text_password")


def _const(node: ast.AST) -> object:
    """取常量节点/常量元组的字面值（非字面量返回 None，供"缺省即报错"使用）。"""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Tuple):
        items = [_const(e) for e in node.elts]
        return tuple(items) if all(i is not None for i in items) else None
    return None


def _kwargs(call: ast.Call) -> dict[str, ast.AST]:
    """把调用节点的关键字参数整理为 `{名: 节点}`。"""
    return {kw.arg: kw.value for kw in call.keywords if kw.arg}


def _find_assignment(tree: ast.Module, name: str) -> ast.AST | None:
    """在模块顶层找 `name = ...`（含带注解赋值）的右侧节点。"""
    for node in tree.body:
        targets = getattr(node, "targets", None) or [getattr(node, "target", None)]
        for tgt in targets:
            if isinstance(tgt, ast.Name) and tgt.id == name:
                return getattr(node, "value", None)
    return None


def _spec_calls(root: Path) -> tuple[list[ast.Call], ast.Module]:
    """AST 解析 `channel_spec.py`，返回 `ChannelSpec(...)` 调用列表与语法树。

    用 AST 而非 import：门禁不执行被检对象，避免 import 副作用与路径依赖。
    """
    path = root / "pilotstd/core/notification/channel_spec.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    node = _find_assignment(tree, "CHANNEL_SPECS")
    if not isinstance(node, ast.Tuple):
        return [], tree
    return [e for e in node.elts if isinstance(e, ast.Call)], tree


def _field_types(tree: ast.Module) -> tuple[str, ...]:
    """从同一模块的 `FIELD_TYPES` 常量读允许的控件形态（单一口径）。"""
    node = _find_assignment(tree, "FIELD_TYPES")
    value = _const(node) if node is not None else None
    return tuple(str(v) for v in value) if isinstance(value, tuple) else ()


def _actual_class_names(root: Path) -> set[str]:
    """AST 扫 `channels/*.py`，取 `NotificationChannel` 的**直接子类**名。"""
    names: set[str] = set()
    for path in (root / "pilotstd/core/notification/channels").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ClassDef) and any(
                isinstance(b, ast.Name) and b.id == "NotificationChannel" for b in node.bases
            ):
                names.add(node.name)
    return names


def check_b1(root: Path) -> tuple[list[str], str]:
    """B1：spec 声明的实现类名集合 vs 源码中真实存在的子类名集合。"""
    calls, _ = _spec_calls(root)
    declared = {
        str(v) for c in calls if isinstance((v := _const(_kwargs(c).get("cls_name"))), str)
    }
    actual = _actual_class_names(root)
    if declared == actual:
        return [], f"✅ {len(declared)}/{len(actual)} 声明类与实现一致"
    missing = sorted(declared - actual)
    extra = sorted(actual - declared)
    return (
        [f"[派生·B1] 声明类与实现类不一致：spec 多声明 {missing}；源码多出 {extra}"],
        f"❌ 声明 {len(declared)} / 实现 {len(actual)}",
    )


def check_b2(root: Path) -> tuple[list[str], str]:
    """B2：spec 自身的结构约束（字段非空、名唯一、形态合法、构造引用有效）。"""
    calls, tree = _spec_calls(root)
    allowed = _field_types(tree)
    errs: list[str] = []
    for call in calls:
        kw = _kwargs(call)
        name = str(_const(kw.get("name")))
        fields = kw.get("fields")
        field_calls = [e for e in fields.elts if isinstance(e, ast.Call)] if isinstance(
            fields, ast.Tuple
        ) else []
        if not field_calls:
            errs.append(f"[派生·B2] {name}: 字段集为空")
            continue
        fnames = [str(_const(_kwargs(fc).get("name"))) for fc in field_calls]
        if len(fnames) != len(set(fnames)):
            errs.append(f"[派生·B2] {name}: 字段名重复 {sorted({n for n in fnames if fnames.count(n) > 1})}")
        for fc in field_calls:
            fkw = _kwargs(fc)
            fname = str(_const(fkw.get("name")))
            ftype = str(_const(fkw.get("type")))
            fpass = _const(fkw.get("password"))
            if allowed and ftype not in allowed:
                errs.append(f"[派生·B2] {name}.{fname}: 控件形态 {ftype!r} 不在 {list(allowed)} 内")
            if bool(fpass) != (ftype in PASSWORD_TYPES):
                errs.append(f"[派生·B2] {name}.{fname}: password={fpass} 与 type={ftype!r} 不自洽")
        ctor = _const(kw.get("ctor")) or ()
        guards = _const(kw.get("ctor_required")) or ()
        if not set(ctor) <= set(fnames):
            errs.append(f"[派生·B2] {name}: ctor 引用了未声明字段 {sorted(set(ctor) - set(fnames))}")
        if not set(guards) <= set(ctor):
            errs.append(f"[派生·B2] {name}: ctor_required 不在 ctor 内 {sorted(set(guards) - set(ctor))}")
    return errs, ("✅ 全部自洽" if not errs else f"❌ {len(errs)} 项不自洽")


def _literal_compares(tree: ast.Module, keys: set[str]) -> list[int]:
    """找出"与渠道名常量比较"或"含渠道名的 in 元组"的行号（AST 级，跳过注释与 docstring）。"""
    rows: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            for comp in [node.left, *node.comparators]:
                if isinstance(comp, ast.Constant) and comp.value in keys:
                    rows.append(node.lineno)
                if isinstance(comp, (ast.Tuple, ast.List, ast.Set)) and any(
                    isinstance(e, ast.Constant) and e.value in keys for e in comp.elts
                ):
                    rows.append(node.lineno)
    return sorted(set(rows))


def check_b3(root: Path) -> tuple[list[str], str]:
    """B3：后端源码中不得残留渠道名字面量比较（构造与配置接口已改语句派生）。"""
    calls, _ = _spec_calls(root)
    keys = {str(_const(_kwargs(c).get("name"))) for c in calls}
    errs: list[str] = []
    for rel in BACKEND_SCAN_FILES:
        rows = _literal_compares(ast.parse((root / rel).read_text(encoding="utf-8")), keys)
        if rows:
            errs.append(f"[派生·B3] {rel} 仍有渠道名字面量比较（行 {rows}）——应由 channel_spec 派生")
    return errs, ("✅ 无残留" if not errs else f"❌ {len(errs)} 个文件残留")


def check_b4(root: Path, keys: set[str]) -> tuple[list[str], list[str], str]:
    """B4：前端硬编码字面量的**棘轮**（不阻断存量、阻断增量）+ 渠道集合一致性。

    返回 `(阻断项, 警告项, 状态摘要)`。C3 落地后字面量归零，本项自动转为全阻断。
    """
    hits = scan(root, sorted(keys))
    struct = structural_keys(root)
    blocking: list[str] = []
    warnings: list[str] = []
    # 结构位扫描（与键集无关）才能发现"前端写了 spec 未声明的渠道"；键集扫描对它恒真。
    if struct - keys:
        blocking.append(f"[派生·B4] 前端出现未知渠道键 {sorted(struct - keys)}（spec 未声明）")
    if struct and struct != keys:
        blocking.append(f"[派生·B4] 前端渠道集合 {sorted(struct)} != spec {sorted(keys)}——三层漂移")
    if len(hits) > FRONTEND_LITERAL_BASELINE:
        blocking.append(
            f"[派生·B4] 前端硬编码渠道键 {len(hits)} 行 > 基线 {FRONTEND_LITERAL_BASELINE}"
            "（C3 未完成前不得增长）"
        )
    elif hits:
        warnings.append(
            f"[派生·B4] 前端仍有 {len(hits)} 行硬编码渠道键（= 基线 {FRONTEND_LITERAL_BASELINE}）："
            "**缓阻断**——清理方案与截止点见 docs/governance/notification_coverage.md（C3 落地即归零转全阻断）"
        )
    elif FRONTEND_LITERAL_BASELINE > 0:
        warnings.append(
            f"[派生·B4] 前端硬编码已归零，但基线仍为 {FRONTEND_LITERAL_BASELINE}——请把 "
            "FRONTEND_LITERAL_BASELINE 收紧为 0（否则棘轮失效）"
        )
    state = f"{len(hits)} 行 / 基线 {FRONTEND_LITERAL_BASELINE}"
    return blocking, warnings, state


def audit_spec_derivations(root: Path) -> tuple[list[str], list[str], dict[str, str]]:
    """执行 B1-B4，返回 `(阻断项, 警告项, 逐项状态摘要)`。"""
    calls, _ = _spec_calls(root)
    keys = {str(_const(_kwargs(c).get("name"))) for c in calls}
    blocking: list[str] = []
    warnings: list[str] = []
    states: dict[str, str] = {}

    for label, result in (
        ("B1 声明类 vs 实现类", check_b1(root)),
        ("B2 spec 自洽性", check_b2(root)),
        ("B3 后端无渠道名字面量", check_b3(root)),
    ):
        b, state = result
        blocking.extend(b)
        states[label] = state

    b4_block, b4_warn, b4_state = check_b4(root, keys)
    blocking.extend(b4_block)
    warnings.extend(b4_warn)
    states["B4 前端硬编码棘轮"] = b4_state
    states["B4 扫描范围"] = "、".join(FRONTEND_FILES)
    return blocking, warnings, states
