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
# T-41/1：事件声明的 AST 解析源（拆分后指向数据模块；**唯一出处**，避免多处漂移）
EVENT_SPEC_SRC = NOTIF / "event_spec_data.py"
# T-41/1：主模块（数据类/工厂/**值域闭集常量**仍在此）——闭集与构建器注册读这里
EVENT_SPEC_MAIN_SRC = NOTIF / "event_spec.py"

# ── 声明式可验证性的闭集（2026-10-06 · P6/P7 甲案）────────────────────────────
# `verify`：该事件的触发点**如何被验证**。**不要求 42/42 运行时覆盖**——极难在正常运行中
# 触发的环境相关事件（凭证轮换、库损坏类告警）显式声明为 `manual`/`ui_only` 即可。
VERIFY_VALUES: tuple[str, ...] = ("e2e", "manual", "ui_only")
# `verify_reason`：非 `e2e` 时必须给出**机器可读枚举码**（避免自由文本漂移；文案在报告 17）。
VERIFY_REASON_CODES: tuple[str, ...] = (
    "env_dependent",  # 需真实环境/凭证/用户动作（含解密上下文、风控阈值）
    "external_state",  # 依赖外部系统状态（站点、公告源、镜像仓库、配额）
    "external_event",  # 依赖外部事件推送（如企微可信 IP 变更）
    "time_based",  # 依赖真实时钟/定时任务
    "data_condition",  # 依赖特定数据条件（空结果、废止无替换等）
    "chaos_condition",  # 依赖故障场景（如数据库损坏类告警）
    "real_chain_only",  # 真实链路完成才触发（现有测试以桩替代）
    "ui_only",  # 仅桌面 UI 层触发
)


# 规格声明字段的**唯一读取口**：只认字面量实参（常量 / 元组 / frozenset），
# 非字面量取值被忽略——让"把值算出来"的写法在门禁侧显形（门禁要能看见声明，而不是执行它）。
def spec_declarations() -> dict[str, dict]:
    """从 `event_spec.py` 提取每个事件的声明字段（**AST 读源，不 import 被检对象**）。

    **为什么改读规格（2026-10-03 步 B D6 后半段）**：D4 完整形态后，e2e 的 `EVENTS`
    已由事件规格派生（源码里不再有字面量清单）——继续解析契约既无可读字面量、又
    恒等于规格（同源比较恒真）。故本维度以**规格声明**为源：契约只是它的投影。
    """
    src = EVENT_SPEC_SRC.read_text(encoding="utf-8")
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
    """AST 读规格里的两个值域闭集：`LEVEL_ORDER`（严重度升序）与 `AGGREGATION_VALUES`。

    **T-41/1 拆分后的双源口径**：42 条声明迁到 `event_spec_data.py`，而这两个**闭集常量仍留在
    `event_spec.py`**（属"数据类/工厂"一侧）⇒ 本函数必须读**主模块**；若误读数据模块，
    闭集为空元组，会让所有事件被判"levels/aggregation 越界"（实测踩到：审计一度报 `e2e 0/42`）。
    """
    tree = ast.parse(EVENT_SPEC_MAIN_SRC.read_text(encoding="utf-8"))
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

    # ── 声明式可验证性（2026-10-06 · P6/P7 甲案）────────────────────────────
    # **设计口径（用户裁定）**：防漂移门禁必须是"声明式"（注册时必填字段）而非"过程式"
    # （每次跑一遍全量插桩）。`verify` 无默认值 ⇒ 漏填在 import 期即 TypeError（第一道）；
    # 此处为第二道：取值落**闭集**、非 `e2e` 必带**机器可读枚举理由**（避免自由文本漂移），
    # 且 `e2e` 不得带理由（防止用理由掩盖真实分类）。
    # **不要求 42/42 运行时覆盖**：极难触发的环境相关事件（凭证轮换/库损坏类告警）显式声明即可。
    verify = meta.get("verify")
    reason = meta.get("verify_reason")
    if verify not in VERIFY_VALUES:
        problems.append(f"verify 越界 -> {verify!r}（闭集 {VERIFY_VALUES}）")
    elif verify == "e2e":
        if reason:
            problems.append(f"verify=e2e 不应带理由 -> {reason!r}")
    else:
        if not isinstance(reason, str) or not reason:
            problems.append(f"verify={verify} 必须带 verify_reason（机器可读枚举码）")
        elif reason not in VERIFY_REASON_CODES:
            problems.append(f"verify_reason 越界 -> {reason!r}（闭集 {VERIFY_REASON_CODES}）")
    return problems
