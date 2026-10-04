# 模块：脚本/—通知规格读取助手
"""通知规格读取助手（从 `audit_notification_coverage.py` 抽出，G-010 压缩）。

**只用 `ast.parse` 读源，不 import 被检对象**（门禁硬约束）；四个函数分别负责：
规格声明字段、两个值域闭集、构建器函数名集合、以及"契约四字段"的合法性校验。
2026-10-03 步 B D6 后半段引入；同批的压缩把本模块从门禁脚本里拆出，使其回到 400 行以内。
"""

# 只依赖标准库：门禁脚本不引入第三方依赖（与 G-010 同批的既有约束）
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOTIF = ROOT / "pilotstd" / "core" / "notification"


# 规格声明字段的**唯一读取口**：只认字面量实参（常量 / 元组 / frozenset），
# 非字面量取值被忽略——让"把值算出来"的写法在门禁侧显形（门禁要能看见声明，而不是执行它）。
def spec_declarations() -> dict[str, dict]:
    """从 `event_spec.py` 提取每个事件的声明字段（**AST 读源，不 import 被检对象**）。

    **为什么改读规格（2026-10-03 步 B D6 后半段）**：D4 完整形态后，e2e 的 `EVENTS`
    已由事件规格派生（源码里不再有字面量清单）——继续解析契约既无可读字面量、又
    恒等于规格（同源比较恒真）。故本维度以**规格声明**为源：契约只是它的投影。
    """
    src = (NOTIF / "event_spec.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    out: dict[str, dict] = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "EventSpec"):
            continue
        fields: dict[str, object] = {}
        for kw in node.keywords:
            if kw.arg is None:
                continue
            value = kw.value
            if isinstance(value, ast.Constant):
                fields[kw.arg] = value.value
            elif isinstance(value, ast.Tuple):
                fields[kw.arg] = tuple(e.value for e in value.elts if isinstance(e, ast.Constant))
            elif isinstance(value, ast.Call) and getattr(value.func, "id", "") == "frozenset":
                args = value.args[0] if value.args else None
                fields[kw.arg] = (
                    frozenset(e.value for e in args.elts if isinstance(e, ast.Constant))
                    if isinstance(args, ast.Set)
                    else frozenset()
                )
        key = fields.get("key")
        if isinstance(key, str):
            out[key] = fields
    return out


# 值域闭集同样读源而不写死：闭集在规格里增删后，门禁口径自动跟随（免两份漂移）。
def spec_closed_sets() -> tuple[tuple[str, ...], tuple[str, ...]]:
    """AST 读规格里的两个值域闭集：`LEVEL_ORDER`（严重度升序）与 `AGGREGATION_VALUES`。"""
    tree = ast.parse((NOTIF / "event_spec.py").read_text(encoding="utf-8"))
    found: dict[str, tuple[str, ...]] = {}
    for node in ast.walk(tree):
        target = getattr(getattr(node, "target", None), "id", None)
        value = getattr(node, "value", None)
        if target in ("LEVEL_ORDER", "AGGREGATION_VALUES") and isinstance(value, ast.Tuple):
            found[target] = tuple(e.value for e in value.elts if isinstance(e, ast.Constant))
    return found.get("LEVEL_ORDER", ()), found.get("AGGREGATION_VALUES", ())


# 构建器函数名集合：只按 `_builders_*.py` 的 `def` 名判定函数是否存在，不 import 构建器模块
# （导入会拉起渠道/凭证等重依赖，门禁须保持轻量且无副作用）。
def _builder_defs() -> dict[str, set[str]]:
    """构建器模块名 → 该模块内 `def` 的函数名集合（AST 读源，不 import）。"""
    out: dict[str, set[str]] = {}
    for path in sorted(NOTIF.glob("_builders_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        out[path.stem] = {
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        }
    return out


def spec_field_problems(
    event: str,
    meta: dict,
    packs: dict[str, dict[str, str]],
    level_order: tuple[str, ...],
    aggregation_values: tuple[str, ...],
    builder_defs: dict[str, set[str]],
) -> list[str]:
    """校验规格四字段的定义（D6 后半段：`level`/`module`/`aggregation`/`builder_keys`）。

    这四项在 D4 完整形态后**唯一存在于规格**，故校验其定义本身，而不是校验一份
    跟它同源的副本：`levels` 非空且按严重度升序；`module_key` 为 i18n 键且三语齐备；
    `aggregation` 取值落闭集；`payload_keys` 全为非空字符串；`builder_ref` 指向
    真实存在的构建器函数（读 `_builders_*.py` 的 `def`——仍不 import 被检对象）。
    """
    # 逐项收集全部问题而非遇错即返：一次运行暴露所有越界字段，免去"改一个跑一次"。
    problems: list[str] = []
    levels = meta.get("levels")
    if not isinstance(levels, tuple) or not levels:
        problems.append("levels 缺失或为空")
    else:
        unknown = [x for x in levels if x not in level_order]
        ranks = [level_order.index(x) for x in levels if x in level_order]
        if unknown:
            problems.append(f"levels 取值越界 -> {unknown}")
        elif ranks != sorted(ranks):
            problems.append(f"levels 未按严重度升序 -> {levels}")

    module_key = meta.get("module_key")
    if not isinstance(module_key, str) or not module_key.startswith("notification.module."):
        problems.append(f"module_key 非模块键 -> {module_key!r}")
    else:
        missing_lang = [lang for lang, pack in packs.items() if module_key not in pack]
        if missing_lang:
            problems.append(f"module_key 缺语言 -> {missing_lang}")

    aggregation = meta.get("aggregation")
    if aggregation not in aggregation_values:
        problems.append(f"aggregation 越界 -> {aggregation!r}")

    keys = meta.get("payload_keys")
    if not isinstance(keys, frozenset) or any(not isinstance(k, str) or not k for k in keys):
        problems.append(f"payload_keys 非字符串集合 -> {keys!r}")

    ref = meta.get("builder_ref")
    if not isinstance(ref, str) or ":" not in ref:
        problems.append(f"builder_ref 形态非法 -> {ref!r}")
    else:
        module_name, func_name = ref.rsplit(":", 1)
        short = module_name.rsplit(".", 1)[-1]
        if short not in builder_defs:
            problems.append(f"builder_ref 指向未知构建器模块 -> {module_name}")
        elif func_name not in builder_defs[short]:
            problems.append(f"builder_ref 指向不存在的函数 -> {ref}")
    return problems
