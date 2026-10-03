#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通知系统覆盖度审计（G-045 基线工具）。

为"新增事件"提供准入基线：39 个已注册事件在 **i18n / 端到端测试 / 审计留痕** 三个维度
的覆盖状态，全部数据来自实际扫描（AST + JSON），不做推断。

判定标准：
  - **i18n**：该事件构建器调用的全部 `t()` 键在 zh_CN/zh_TW/en 三语中齐备（阻断项）；
  - **e2e**：事件出现在 `tests/test_notification_e2e.py` 的 EVENTS 列表（阻断项），
    且其 `trigger_file` **物理存在**（防止元数据指向已改名/删除的文件——实测曾出现
    三处指向不存在的 `_query_exec.py`）；
  - **审计**：安全类事件（`security_*` / `notification_credential_changed`）的触发文件
    必须调用 `write_audit`（阻断项）；业务类事件标注 `N/A 业务事件无安全语义`。
  - **术语**：构建器键在 `docs/governance/glossary.json` 中登记（跟踪项，不阻断）。

用法：
  python scripts/audit_notification_coverage.py            # 打印矩阵 + 汇总
  python scripts/audit_notification_coverage.py --matrix    # 只输出 Markdown 矩阵
  python scripts/audit_notification_coverage.py --strict    # 跟踪项缺失也算失败
退出码：0 = 无阻断缺口；1 = 存在阻断缺口。
"""

from __future__ import annotations

import ast
import io
import json
import sys
from pathlib import Path

from _gate_coverage_summary import print_coverage_summary
from _notification_spec_audit import B_RULE_COUNT, audit_spec_derivations

if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
NOTIF = ROOT / "pilotstd" / "core" / "notification"
I18N = ROOT / "pilotstd" / "i18n"
GLOSSARY = ROOT / "docs" / "governance" / "glossary.json"
E2E_TEST = ROOT / "tests" / "test_notification_e2e.py"
LANGS = ("zh_CN", "zh_TW", "en")

# 安全类事件：必须有审计留痕（S1 凭证生命周期 / 认证失败）。
# 判定用前缀而非白名单——新增 security_* 事件自动纳入强制审计，避免"新事件漏登记"。
SECURITY_EVENT_PREFIXES = ("security_",)
# 例外：凭证变更事件的语义属安全类，但命名在 notification_* 族（第 2 批遗留命名）。
SECURITY_EVENTS_EXTRA = frozenset({"notification_credential_changed"})


def load_packs() -> dict[str, dict[str, str]]:
    """加载三语语言包，返回 {语言: {键: 值}}。"""
    return {
        lang: json.loads((I18N / f"{lang}.json").read_text(encoding="utf-8")) for lang in LANGS
    }


def events_from_registry() -> list[str]:
    """从 events.py 的 ALL_EVENTS 提取事件键（AnnAssign + 常量名解析）。"""
    tree = ast.parse((NOTIF / "events.py").read_text(encoding="utf-8"))
    consts: dict[str, object] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.startswith("EVENT_"):
                    consts[target.id] = node.value.value
    values: list[ast.expr] = []
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "ALL_EVENTS":
            if isinstance(node.value, ast.List):
                values = list(node.value.elts)
        elif isinstance(node, ast.Assign) and any(
            getattr(t, "id", "") == "ALL_EVENTS" for t in node.targets
        ):
            if isinstance(node.value, ast.List):
                values = list(node.value.elts)
    keys: list[str] = []
    for elt in values:
        if not (isinstance(elt, ast.Call) and elt.args):
            continue
        arg = elt.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            keys.append(arg.value)
        elif isinstance(arg, ast.Name):
            resolved = consts.get(arg.id)
            keys.append(resolved if isinstance(resolved, str) else f"<未解析:{arg.id}>")
    return keys


def builder_t_keys() -> dict[str, set[str]]:
    """构建器函数名 → 其内部 t() 字面量键集合。

    只看字面量键（`t("notification.x")`）：变量键（`t(title_key)`）无法静态求值，
    其取值由分支决定——这类键需人工核对，属本工具的已知盲区（不虚报为已覆盖）。
    """
    result: dict[str, set[str]] = {}
    for path in sorted(NOTIF.glob("_builders_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) or not node.name.startswith("_build_"):
                continue
            found: set[str] = set()
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id == "t":
                    if sub.args and isinstance(sub.args[0], ast.Constant) and isinstance(sub.args[0].value, str):
                        found.add(sub.args[0].value)
            result[node.name] = found
    return result


def manager_event_builders() -> dict[str, str]:
    """从**事件规格**（`event_spec.py`）提取 事件 → 构建器函数名。

    该映射是"事件是否可用"的权威判据：事件注册进 ALL_EVENTS 但没有映射时，
    `send_event` 会走兜底构建器，用户收到的是原始事件名而非可读文案。

    **读取源（2026-10-03 步 B D6）**：原读 `manager._init_event_builders` 的字面量
    字典；D2 之后该注册表由规格派生、源码里不再有字面量键值对，故改读**事件规格
    声明**——`builder_ref` 是 `模块全名:函数名` 的静态字面量，取冒号后段即函数名。
    **仍坚持"门禁不 import 被检对象"**：全程只用 `ast.parse` 读源文件。
    """
    src = (NOTIF / "event_spec.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    pairs: dict[str, str] = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "EventSpec"):
            continue
        key: object = None
        ref: object = None
        for kw in node.keywords:
            if kw.arg == "key" and isinstance(kw.value, ast.Constant):
                key = kw.value.value
            elif kw.arg == "builder_ref" and isinstance(kw.value, ast.Constant):
                ref = kw.value.value
        if isinstance(key, str) and isinstance(ref, str) and ":" in ref:
            pairs[key] = ref.rsplit(":", 1)[1]
    return pairs


def e2e_events() -> dict[str, dict]:
    """解析 e2e EVENTS 列表（括号配平 + literal_eval）。

    不用正则取 `"name": "..."`：EVENTS 的每个条目含嵌套的 `builder_keys` 集合，
    正则难以界定条目边界；括号配平能精确定位列表字面量，再交给 literal_eval
    做一次可信解析（该列表语法上是纯字面量，故 literal_eval 安全）。
    """
    src = E2E_TEST.read_text(encoding="utf-8")
    marker = "EVENTS: list[dict[str, Any]] = "
    start = src.index(marker) + len(marker)
    depth = 0
    # 逐字符配平方括号：遇到 '[' 深度 +1，']' 深度 -1；归零处即列表结尾
    for i in range(start, len(src)):
        if src[i] == "[":
            depth += 1
        elif src[i] == "]":
            depth -= 1
            if depth == 0:
                entries = ast.literal_eval(src[start : i + 1])
                return {e["name"]: e for e in entries}
    return {}


def glossary_keys() -> set[str]:
    """术语表中所有被登记的 i18n 键（各条目的 keys 并集）。"""
    data = json.loads(GLOSSARY.read_text(encoding="utf-8"))
    keys: set[str] = set()
    for term in data.get("terms", []):
        keys.update(term.get("keys", []))
    return keys


def is_security_event(event: str) -> bool:
    """判定事件是否属安全类（决定审计维度是"强制"还是 N/A）。

    用前缀 + 例外集而非硬编码全量清单：新增 `security_*` 事件自动纳入强制审计，
    避免"加了事件却忘了登记审计要求"这一最典型的漏检形态。
    """
    return event.startswith(SECURITY_EVENT_PREFIXES) or event in SECURITY_EVENTS_EXTRA


def _audit_one_event(
    event: str,
    packs: dict[str, dict[str, str]],
    mapping: dict[str, str],
    t_keys: dict[str, set[str]],
    e2e: dict[str, dict],
    glossary: set[str],
) -> tuple[dict[str, object], list[str], list[str]]:
    """审计单个事件，返回 (矩阵行, 该事件的阻断缺口, 该事件的跟踪项)。"""
    blocking: list[str] = []
    tracked: list[str] = []

    builder = mapping.get(event)
    keys = t_keys.get(builder, set()) if builder else set()

    # 维度 1（i18n）：构建器用到的每个键都必须在三语中存在。
    # 任缺一语即阻断——繁体/英文缺键会让对应语言用户直接看到 i18n 键名。
    miss = sorted(k for k in keys if any(k not in packs[lang] for lang in LANGS))
    i18n_ok = builder is not None and not miss
    if not i18n_ok:
        blocking.append(f"{event}: i18n 键缺失 {miss[:3] if miss else '构建器未注册'}")

    # 维度 2（e2e）：事件须进 EVENTS 列表，且 trigger_file 必须真实存在。
    # 只检查"是否在列表里"不够——实测曾有三处 trigger_file 指向已删除的文件，
    # 那种情况下"有触发点"的断言是假绿。
    meta = e2e.get(event)
    trigger = str(meta.get("trigger_file", "")) if meta else ""
    trigger_exists = bool(trigger) and (ROOT / trigger).exists()
    e2e_ok = meta is not None and trigger_exists
    if meta is None:
        blocking.append(f"{event}: 未出现在 e2e EVENTS 列表")
    elif not trigger_exists:
        blocking.append(f"{event}: trigger_file 不存在 -> {trigger}")

    # 维度 3（审计）：安全事件必须在其触发文件里写审计；业务事件标注 N/A
    if is_security_event(event):
        audit_ok = trigger_exists and "write_audit(" in (ROOT / trigger).read_text(encoding="utf-8")
        audit_cell = "✅" if audit_ok else "❌"
        if not audit_ok:
            blocking.append(f"{event}: 安全事件但触发路径无 write_audit（{trigger or '未知'}）")
    else:
        audit_cell = "N/A"

    # 维度 4（术语登记）：跟踪项，不阻断——术语表是受控词汇表而非全量字典
    unregistered = sorted(k for k in keys if k not in glossary)
    term_ok = bool(keys) and not unregistered
    if not term_ok:
        tracked.append(f"{event}: {len(unregistered)} 个文案键未登记术语表")

    row: dict[str, object] = {
        "event": event,
        "i18n": "✅" if i18n_ok else "❌",
        "term": "✅" if term_ok else "⚠️",
        "e2e": "✅" if e2e_ok else "❌",
        "audit": audit_cell,
        "builder": builder or "—",
        "note": "" if i18n_ok else f"缺键 {miss[:2]}",
    }
    return row, blocking, tracked


def _print_matrix(rows: list[dict[str, object]]) -> None:
    """打印 Markdown 矩阵（供写入 notification_coverage.md）。"""
    print("| 事件 | i18n | 术语 | e2e | 审计 | 构建器 |")
    print("|------|------|------|-----|------|--------|")
    for r in rows:
        print(f"| `{r['event']}` | {r['i18n']} | {r['term']} | {r['e2e']} | {r['audit']} | `{r['builder']}` |")


def print_coverage(
    rows: list[dict[str, object]],
    blocking: list[str],
    tracked: list[str],
    b_states: dict[str, str] | None = None,
) -> None:
    """打印 G-045 覆盖摘要（L-23）。

    PASS 只说明**已检查的维度**通过；必须声明**未校验的字段**与**未登记的事件**，
    否则会被误读为"EVENTS 元数据全部可信"。

    **A 类（事件覆盖度）与 B 类（渠道派生一致性）分开计数**：两者检查对象不同
    （41 事件 vs 4 渠道），合并成一个数字会让"总计/通过"不可解释。

    独立成函数：`main()` 须守住 G-010 的逻辑行上限。
    """
    states = b_states or {}
    n_i18n = sum(1 for r in rows if r["i18n"] == "✅")
    n_e2e = sum(1 for r in rows if r["e2e"] == "✅")
    n_term = sum(1 for r in rows if r["term"] == "✅")
    sec_rows = [r for r in rows if is_security_event(str(r["event"]))]
    n_sec = sum(1 for r in sec_rows if r["audit"] == "✅")
    b_labels = [k for k in states if k.startswith("B") and not k.startswith("B4 扫描")]
    n_b_block = sum(1 for k in b_labels if states[k].startswith("❌"))
    print_coverage_summary(
        scope="{} 的 ALL_EVENTS（{} 个）+ {} 的 EVENTS 元数据 + channel_spec 的 4 渠道（B 类 {} 项）".format(
            NOTIF.name + "/events.py", len(rows), E2E_TEST.relative_to(ROOT).as_posix(), B_RULE_COUNT
        ),
        checked=len(rows) + B_RULE_COUNT,
        passed=n_i18n + (B_RULE_COUNT - n_b_block),
        blocked=len(blocking),
        exempted=len(tracked),
        # 跟踪项是**有名有姓的事件列表**（`<事件>: N 个文案键未登记术语表`），
        # 只给计数看不出"哪些事件未登记"，仍属 PASS 掩盖空洞。段标题用
        # "跟踪项明细"以区别于 G-043 的"豁免路由"语义。
        exemptions=tracked,
        exemptions_label="跟踪项明细",
        max_item_len=120,  # 条目含事件名 + 中文说明，40 字符会截断到不可辨识
        notes=(
            "i18n 三语键齐备 -> {}/{} 事件（A 类，阻断维度）".format(n_i18n, len(rows)),
            "e2e 覆盖 + trigger_file 存在 -> {}/{} 事件（A 类，阻断维度）".format(n_e2e, len(rows)),
            "安全事件 write_audit -> {}/{} 事件（A 类，阻断维度，仅安全类）".format(n_sec, len(sec_rows)),
            "术语表登记 -> {}/{} 事件（A 类，跟踪项，不阻断）".format(n_term, len(rows)),
            *[f"{label} -> {states[label]}（B 类，阻断维度）" for label in b_labels],
        ),
        uncovered=(
            "**EVENTS 的 level/module/aggregation/builder_keys 未校验**"
            "（level 为 `a/b` 集合约定，表示构建器按分支取值的集合）；"
            "`desktop_toast` 无独立构建器与 i18n 键（标题继承自上游事件，如 "
            "`_(\"download_results_title\")`），未登记进 ALL_EVENTS——已采纳方案 B 显式声明"
            "未覆盖，方案 A 触发条件见 docs/governance/notification_coverage.md；"
            "**B4 为全阻断**（前端硬编码渠道键的棘轮，基线已随 C3 归零："
            "任何新增硬编码当场红灯；存量 26 行已于 C3 清理完毕），"
            "清理记录见同文档「B 类」节"
        ),
    )


def main(argv: list[str]) -> int:
    """审计入口：构建矩阵、输出汇总，按阻断缺口决定退出码。"""
    matrix_only = "--matrix" in argv
    strict = "--strict" in argv

    packs = load_packs()
    events = events_from_registry()
    mapping = manager_event_builders()
    t_keys = builder_t_keys()
    e2e = e2e_events()
    glossary = glossary_keys()

    rows: list[dict[str, object]] = []
    blocking: list[str] = []
    tracked: list[str] = []
    for event in events:
        row, ev_blocking, ev_tracked = _audit_one_event(event, packs, mapping, t_keys, e2e, glossary)
        rows.append(row)
        blocking.extend(ev_blocking)
        tracked.extend(ev_tracked)

    if matrix_only:
        _print_matrix(rows)
        return 0

    # B 类：渠道声明与实现/前端的跨层一致性（设计见 07-impl-design-A.md §八）。
    # A 类条目统一加 `[覆盖度]` 前缀，与 B 类在输出里可区分（两类检查对象不同）。
    b_blocking, b_warnings, b_states = audit_spec_derivations(ROOT)
    blocking = [f"[覆盖度] {item}" for item in blocking] + b_blocking

    print("=" * 96)
    print(f"通知系统覆盖度审计：{len(events)} 个事件 + 4 个渠道声明（A/B 两类）")
    print("=" * 96)
    print(f"{'事件':<34}{'i18n':<7}{'术语':<7}{'e2e':<6}{'审计':<7}构建器")
    print("-" * 96)
    for r in rows:
        print(
            f"{r['event']:<34}{r['i18n']:<7}{r['term']:<7}{r['e2e']:<6}{r['audit']:<7}{r['builder']}"
        )
    print("-" * 96)
    n_i18n_ok = sum(1 for r in rows if r["i18n"] == "✅")
    n_e2e_ok = sum(1 for r in rows if r["e2e"] == "✅")
    n_term_ok = sum(1 for r in rows if r["term"] == "✅")
    sec_rows = [r for r in rows if is_security_event(str(r["event"]))]
    n_sec_ok = sum(1 for r in sec_rows if r["audit"] == "✅")
    print(f"i18n {n_i18n_ok}/{len(rows)} | e2e {n_e2e_ok}/{len(rows)} | 术语 {n_term_ok}/{len(rows)} "
          f"| 安全事件审计 {n_sec_ok}/{len(sec_rows)}")
    print()
    print(f"渠道派生一致性（B 类，{B_RULE_COUNT} 项，阻断维度）：")
    for label, state in b_states.items():
        if label.startswith("B4 扫描"):
            continue
        print(f"  {label:<22}{state}")
    for warning in b_warnings:
        print(f"  ⚠️  {warning}")
    print()
    if blocking:
        print(f"❌ 阻断缺口 {len(blocking)} 项：")
        for item in blocking:
            print(f"   - {item}")
    else:
        print("✅ 无阻断缺口（覆盖度：i18n 齐备、e2e 覆盖且触发文件存在、安全事件有审计；"
              "派生一致性：声明与实现/后端/前端三层一致）")
    print_coverage(rows, blocking, tracked, b_states)
    if blocking or (strict and tracked):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
