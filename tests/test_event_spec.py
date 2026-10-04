# tests/test_event_spec.py
"""`event_spec` 契约测试——事件声明的自洽性与跨层一致性（步 B 第一子步骤）。

设计依据：docs/plans/notification-system-design/06-spec-and-phasing.md §一。
本文件的断言**不重复 spec 的派生结果**（那会恒真），而是锚定三类外部事实：
① spec 自身的结构约束；② spec 与**字面量基线**的比对；③ spec 与**既有消费方**
（映射表 / 默认配置 / 端到端契约 / 语言包 / 前端清单 / 磁盘文件）的比对。

另有两条**口径红线**用例：字段值里不得出现中文（展示文案一律走 i18n 键），
以及本轮"未接入任何消费方"的范围事实。
"""

import ast
import dataclasses
import json
import os
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pilotstd.core.config.defaults import FACTORY_DEFAULTS  # noqa: E402
from pilotstd.core.notification.event_spec import (  # noqa: E402
    AGGREGATION_VALUES,
    EVENT_SPEC_KEYS,
    EVENT_SPECS,
    LEVEL_ORDER,
    EventSpec,
    builder_callable,
    spec_for,
)
from pilotstd.core.notification.events import ALL_EVENT_KEYS  # noqa: E402
from pilotstd.core.notification.mapping import (  # noqa: E402
    CONTENT_TYPES,
    EVENT_MAPPINGS,
    NOTIFY_EVENTS,
    TASK_KINDS,
)

ROOT = Path(__file__).resolve().parent.parent
SPEC_FILE = ROOT / "pilotstd" / "core" / "notification" / "event_spec.py"
EVENTS_FILE = ROOT / "pilotstd" / "core" / "notification" / "events.py"
E2E_FILE = ROOT / "tests" / "test_notification_e2e.py"
VUE_FILE = ROOT / "web" / "src" / "components" / "NotificationConfig.vue"
I18N_DIR = ROOT / "pilotstd" / "i18n"
LANGS = ("zh_CN", "zh_TW", "en")
_E2E_MODULE = None  # e2e 契约模块缓存（见 _e2e_module）

# 字面量基线（独立于 spec，用于检出 spec 内容的静默变更）
EXPECTED_FIELDS = (
    "key",
    "notify_event",
    "content_type",
    "task_kind",
    "builder_ref",
    "i18n_category",
    "default_channels",
    "levels",
    "module_key",
    "trigger_file",
    "payload_keys",
    "security",
    "branch_by",
    "subscribable",
    "aggregation",
)
EXPECTED_EVENT_COUNT = 41
EXPECTED_MODULE_KEYS = {
    "notification.module.validity",
    "notification.module.interaction",
    "notification.module.scan",
    "notification.module.query",
    "notification.module.download",
    "notification.module.normalize",
    "notification.module.archive",
    "notification.module.expire",
    "notification.module.announce",
    "notification.module.system",
    "notification.module.favorite",
    "notification.module.security",
}
# 与门禁 G-045 的安全事件判定同口径：前缀 security_ + 例外集（凭证变更）
EXPECTED_SECURITY_KEYS = {
    "notification_credential_changed",
    "security_password_changed",
    "security_token_refreshed",
    "security_login_failed",
}
# 中日韩统一表意文字（含扩展 A 与兼容区）——与 G-047 门禁同口径
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def _spec_source() -> str:
    """读取 spec 源文件文本（门禁以文本 + AST 读取，测试同口径）。"""
    return SPEC_FILE.read_text(encoding="utf-8")


def _spec_calls() -> list[ast.Call]:
    """从 spec 源文件里取出全部 `EventSpec(...)` 调用节点。"""
    tree = ast.parse(_spec_source())
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "EventSpec"
    ]


def _keyword(call: ast.Call, name: str) -> ast.expr:
    """取某个关键字实参节点；缺失即失败（不静默跳过）。"""
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    raise AssertionError(f"EventSpec 声明缺少字段 {name}")


def _static_value(node: ast.expr) -> object:
    """把静态字面量节点还原为运行期值；非字面量节点直接失败。"""
    if isinstance(node, ast.Call):
        # 仅允许 frozenset({...}) / frozenset() 这一种构造（载荷键的集合形态）
        assert isinstance(node.func, ast.Name) and node.func.id == "frozenset", "出现非字面量构造"
        if not node.args:
            return frozenset()
        return frozenset(ast.literal_eval(node.args[0]))
    return ast.literal_eval(node)


def _docstring_lines(tree: ast.AST) -> set[int]:
    """docstring 占据的行号集合（其内容不参与"不得写中文"判定）。"""
    lines: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
            if isinstance(first.value.value, str):
                start = first.value.lineno
                lines.update(range(start, (first.value.end_lineno or start) + 1))
    return lines


def _e2e_events() -> dict[str, dict]:
    """运行期读取端到端契约的事件清单（不复制契约数据）。

    D4 完整形态（2026-10-03）后 `EVENTS` 由事件规格派生，源码里已不是字面量清单，
    故改为按文件路径导入该模块、读其 `EVENTS`——这样断言面对的是**契约的实际运行期取值**。
    """
    module = _e2e_module()
    return {e["name"]: e for e in module.EVENTS}


def _e2e_module():
    """按路径导入 e2e 契约模块（只执行一次，结果缓存）。"""
    global _E2E_MODULE
    if _E2E_MODULE is None:
        import importlib.util

        spec = importlib.util.spec_from_file_location("_e2e_contract_module", E2E_FILE)
        assert spec and spec.loader, "无法加载端到端契约模块"
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _E2E_MODULE = module
    return _E2E_MODULE


def _frontend_literal_event_keys() -> set[str]:
    """前端源码里**字面量**出现的事件键（D5 后应为空——用于防"硬编码回填"）。"""
    keys = set(ALL_EVENT_KEYS)
    found: set[str] = set()
    for line in VUE_FILE.read_text(encoding="utf-8").splitlines():
        for token in line.replace("'", '"').split('"')[1::2]:
            if token in keys:
                found.add(token)
    return found


def _frontend_visible_event_keys() -> set[str]:
    """前端**渲染**的可勾选事件键：D5 起由后端接口派生（前端零硬编码）。

    改前口径＝解析组件里的字面量键；D5 把该清单搬到 `GET /api/notification/spec`
    （`subscribable=True` 的事件），故此处取**端点实现**的返回值。
    """
    from docker.api.notification_config import get_notification_spec

    return set(get_notification_spec()["events"])


def _packs() -> dict[str, dict[str, str]]:
    """加载三语语言包。"""
    return {lang: json.loads((I18N_DIR / f"{lang}.json").read_text(encoding="utf-8")) for lang in LANGS}


class TestSpecSelfConsistency(unittest.TestCase):
    """spec 自身的结构约束（唯一来源内部必须自洽）。"""

    def test_keys_match_event_registry(self):
        """规格键集必须与事件注册表完全一致，且无重复、无遗漏。"""
        self.assertEqual(len(EVENT_SPECS), EXPECTED_EVENT_COUNT)
        self.assertEqual(len(set(EVENT_SPEC_KEYS)), EXPECTED_EVENT_COUNT, "事件键不得重复")
        self.assertEqual(set(EVENT_SPEC_KEYS), set(ALL_EVENT_KEYS))

    def test_declares_exactly_fifteen_fields(self):
        """每条声明必须恰好有 15 个字段（互斥说明已按裁决移出规格）。"""
        names = tuple(f.name for f in dataclasses.fields(EventSpec))
        self.assertEqual(names, EXPECTED_FIELDS)
        self.assertNotIn("mutual", names, "互斥说明是设计文档内容，不进规格")

    def test_every_field_is_populated(self):
        """15 个字段必须全部有值；除分支判据外不得为 None（无缺字段）。"""
        for spec in EVENT_SPECS:
            for field in dataclasses.fields(EventSpec):
                value = getattr(spec, field.name)
                if field.name == "branch_by":
                    continue
                self.assertIsNotNone(value, f"{spec.key}.{field.name} 为空")

    def test_aggregation_is_ascii_enum(self):
        """聚合策略必须是 ASCII 枚举（系统内部状态标识，不进 i18n）。"""
        self.assertEqual(AGGREGATION_VALUES, ("aggregate", "bypass"))
        for spec in EVENT_SPECS:
            self.assertIn(spec.aggregation, AGGREGATION_VALUES, spec.key)
        counts = {
            value: sum(1 for s in EVENT_SPECS if s.aggregation == value) for value in AGGREGATION_VALUES
        }
        self.assertEqual(counts, {"aggregate": 38, "bypass": 3})

    def test_levels_are_ordered_subsequences(self):
        """级别集合必须非空、无重复，且按严重度升序（序列化约定的前提）。"""
        rank = {name: i for i, name in enumerate(LEVEL_ORDER)}
        for spec in EVENT_SPECS:
            self.assertTrue(spec.levels, f"{spec.key} 级别为空")
            self.assertEqual(len(spec.levels), len(set(spec.levels)), f"{spec.key} 级别重复")
            for name in spec.levels:
                self.assertIn(name, rank, f"{spec.key} 级别越界: {name}")
            ranks = [rank[name] for name in spec.levels]
            self.assertEqual(ranks, sorted(ranks), f"{spec.key} 级别未按严重度升序")

    def test_builder_ref_points_into_builder_modules(self):
        """构建器指针必须是 `模块全名:函数名`，且落在既有构建器模块内。"""
        for spec in EVENT_SPECS:
            module, sep, func = spec.builder_ref.partition(":")
            self.assertEqual(sep, ":", spec.key)
            self.assertTrue(module.startswith("pilotstd.core.notification._builders_"), spec.key)
            self.assertTrue(func.startswith("_build_"), spec.key)

    def test_spec_for_unknown_key_raises(self):
        """未登记的键必须显式失败（不得回退为默认规格）。"""
        with self.assertRaises(KeyError):
            spec_for("no_such_event")
        self.assertEqual(spec_for(EVENT_SPEC_KEYS[0]).key, EVENT_SPEC_KEYS[0])


class TestFieldValuesAreMachineReadable(unittest.TestCase):
    """字段值一律机器可读（i18n 键 / ASCII 枚举），不得内嵌展示文案。"""

    def test_no_chinese_literal_outside_docstrings(self):
        """声明的字符串字面量不得含中文（与 G-047 门禁同口径，防止回潮）。

        注释与 docstring 不受此限（G-012 反而强制它们用中文）。
        """
        tree = ast.parse(_spec_source())
        doc_lines = _docstring_lines(tree)
        offenders = [
            (node.lineno, node.value)
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.lineno not in doc_lines
            and CJK_RE.search(node.value)
        ]
        self.assertEqual(offenders, [], "字段值里出现中文（应改为 i18n 键或 ASCII 枚举）")

    def test_module_key_is_i18n_key_present_in_three_packs(self):
        """模块名必须是 `notification.module.*` 键，且三语包中都有对应实体键。"""
        packs = _packs()
        got = {spec.module_key for spec in EVENT_SPECS}
        self.assertEqual(got, EXPECTED_MODULE_KEYS)
        for spec in EVENT_SPECS:
            self.assertTrue(spec.module_key.startswith("notification.module."), spec.key)
        for lang, pack in packs.items():
            missing = sorted(k for k in EXPECTED_MODULE_KEYS if k not in pack)
            self.assertEqual(missing, [], f"{lang} 缺少模块名键")
            for key in EXPECTED_MODULE_KEYS:
                self.assertTrue(pack[key].strip(), f"{lang}.{key} 文案为空")


class TestSpecStaticLiteralAST(unittest.TestCase):
    """门禁以 `ast.parse` 读取本模块——声明必须全部是静态字面量。"""

    def test_source_is_ast_parseable(self):
        """源文件必须可被 AST 解析（不执行、不 import 即可读取）。"""
        tree = ast.parse(_spec_source())
        self.assertIsInstance(tree, ast.Module)

    def test_every_entry_has_fifteen_keywords_and_literal_values(self):
        """41 条声明各带 15 个关键字实参，且取值只能是字面量/元组/集合字面量。"""
        calls = _spec_calls()
        self.assertEqual(len(calls), EXPECTED_EVENT_COUNT)
        for call in calls:
            self.assertEqual(len(call.keywords), 15, f"关键字实参数量异常: {ast.dump(call)[:60]}")
            self.assertEqual({kw.arg for kw in call.keywords}, set(EXPECTED_FIELDS))
            for kw in call.keywords:
                if isinstance(kw.value, ast.Call):
                    # 唯一允许的构造：载荷键的集合形态 frozenset({...}) / frozenset()
                    self.assertEqual(getattr(kw.value.func, "id", ""), "frozenset", f"{kw.arg} 出现计算")
                    self.assertFalse(kw.value.keywords, f"{kw.arg} 出现关键字实参")
                    for arg in kw.value.args:
                        self.assertIsInstance(arg, ast.Set, f"{kw.arg} 的元素不是字面量")
                    continue
                self.assertIsInstance(kw.value, (ast.Constant, ast.Tuple, ast.Set), f"{kw.arg} 不是字面量")
                if isinstance(kw.value, ast.Tuple | ast.Set):
                    for elt in kw.value.elts:
                        self.assertIsInstance(elt, ast.Constant, f"{kw.arg} 元素不是字面量")

    def test_ast_values_equal_runtime_values(self):
        """AST 提取的键与标量元数据必须与运行期对象逐一相等（门禁可用性证明）。"""
        runtime = {s.key: s for s in EVENT_SPECS}
        scalars = (
            "notify_event", "content_type", "task_kind", "builder_ref", "i18n_category",
            "default_channels", "levels", "module_key", "trigger_file", "security",
            "subscribable", "aggregation",
        )
        for call in _spec_calls():
            key = _static_value(_keyword(call, "key"))
            self.assertIn(key, runtime, f"AST 中出现未登记事件 {key}")
            spec = runtime[str(key)]
            for name in scalars:
                self.assertEqual(_static_value(_keyword(call, name)), getattr(spec, name), f"{key}.{name}")
            self.assertEqual(_static_value(_keyword(call, "payload_keys")), spec.payload_keys, key)
            self.assertIsNone(_static_value(_keyword(call, "branch_by")), f"{key}.branch_by")


class TestCrossLayerConsistency(unittest.TestCase):
    """spec 与既有消费方的比对（spec 被改动而与外部事实不符即 FAIL）。"""

    def test_mapping_table_matches_spec(self):
        """映射表的事件集合与三个投影字段必须逐条等于规格。"""
        self.assertEqual(set(EVENT_MAPPINGS), set(EVENT_SPEC_KEYS))
        for spec in EVENT_SPECS:
            mapping = EVENT_MAPPINGS[spec.key]
            self.assertEqual(mapping.notify_event, spec.notify_event, spec.key)
            self.assertEqual(mapping.content_type, spec.content_type, spec.key)
            self.assertEqual(mapping.task_kind, spec.task_kind, spec.key)
            self.assertIn(spec.notify_event, NOTIFY_EVENTS, spec.key)
            self.assertIn(spec.content_type, CONTENT_TYPES, spec.key)
            self.assertTrue(spec.task_kind in TASK_KINDS or spec.task_kind == "", spec.key)

    def test_default_channels_derive_factory_rules(self):
        """默认渠道非空的事件集合必须等于出厂配置的订阅规则键集，取值亦须一致。"""
        rules = {k.split(".")[-1]: v for k, v in FACTORY_DEFAULTS.items() if k.startswith("notification.rules.")}
        declared = {s.key: list(s.default_channels) for s in EVENT_SPECS if s.default_channels}
        self.assertEqual(set(rules), set(declared), "出厂订阅规则的键集会漂移")
        self.assertEqual(rules, declared)

    def test_builder_resolves_and_matches_e2e_metadata(self):
        """`builder` 必须能解析为可调用对象，且反射结果等于契约里的文件名与函数名。"""
        e2e = _e2e_events()
        for spec in EVENT_SPECS:
            builder = builder_callable(spec)
            self.assertTrue(callable(builder), spec.key)
            self.assertEqual(builder.__module__.replace(".", "/") + ".py", e2e[spec.key]["builder_file"])
            self.assertEqual(builder.__name__, e2e[spec.key]["builder_method"])
            self.assertEqual(builder_callable(spec).__name__, spec.builder_ref.partition(":")[2])

    def test_e2e_metadata_matches_spec(self):
        """模块键 / 触发文件 / 载荷键 / 级别 / 聚合策略必须逐条等于契约。

        口径（2026-10-03 裁决）：契约的 `module` 字段存 i18n 键、`aggregation` 存
        ASCII 枚举，故两侧可直接比对；`mutual` 字段已随步 B D4 从契约删除，两侧都不登记。
        """
        e2e = _e2e_events()
        self.assertEqual(set(e2e), set(EVENT_SPEC_KEYS))
        for spec in EVENT_SPECS:
            entry = e2e[spec.key]
            self.assertEqual(entry["module"], spec.module_key, spec.key)
            self.assertEqual(entry["trigger_file"], spec.trigger_file, spec.key)
            self.assertEqual(entry["builder_keys"], set(spec.payload_keys), spec.key)
            self.assertEqual(entry["level"], "/".join(spec.levels), spec.key)
            self.assertEqual(entry["aggregation"], spec.aggregation, spec.key)

    def test_trigger_files_exist_on_disk(self):
        """触发文件必须真实存在（否则"有触发点"是假绿）。"""
        for spec in EVENT_SPECS:
            self.assertTrue((ROOT / spec.trigger_file).is_file(), f"{spec.key}: {spec.trigger_file}")

    def test_i18n_category_exists_in_three_packs(self):
        """文案前缀必须在三语语言包里都有实体键（不可机械推导，故须显式登记）。"""
        packs = _packs()
        for spec in EVENT_SPECS:
            for lang, pack in packs.items():
                hits = [k for k in pack if k.startswith(spec.i18n_category + ".")]
                self.assertTrue(hits, f"{spec.key} 的文案前缀 {spec.i18n_category} 在 {lang} 中无键")

    def test_security_flag_matches_gate_rule(self):
        """安全标志必须等于门禁的判定结果（前缀 + 例外集口径）。"""
        got = {s.key for s in EVENT_SPECS if s.security}
        self.assertEqual(got, EXPECTED_SECURITY_KEYS)
        for spec in EVENT_SPECS:
            expected = spec.key.startswith("security_") or spec.key == "notification_credential_changed"
            self.assertEqual(spec.security, expected, spec.key)

    def test_subscribable_matches_frontend_list(self):
        """是否可勾选必须等于前端渲染集合（D5 后由后端端点派生），且前端不得回填字面量。"""
        visible = _frontend_visible_event_keys()
        declared = {s.key for s in EVENT_SPECS if s.subscribable}
        self.assertEqual(declared, visible)
        # D5 回归护栏：组件源码里不得再出现事件键字面量（否则"前端零硬编码"失效）
        literals = _frontend_literal_event_keys()
        self.assertEqual(literals, set(), f"前端不应再硬编码事件键：{sorted(literals)[:5]}")
        self.assertTrue({s.key for s in EVENT_SPECS if s.default_channels} - visible, "两字段应不同轴")


class TestScopeOfThisSubStep(unittest.TestCase):
    """接入面必须与计划一致：只允许已落地的派生消费方 import 事件规格。"""

    def test_events_module_stays_dependency_free(self):
        """事件注册表不得出现内部依赖；规格模块只允许 import 标准库与事件注册表。"""
        events_tree = ast.parse(EVENTS_FILE.read_text(encoding="utf-8"))
        for node in ast.walk(events_tree):
            self.assertFalse(isinstance(node, ast.ImportFrom) and node.level > 0, "事件注册表出现内部 import")
        spec_tree = ast.parse(_spec_source())
        relative = {
            node.module
            for node in ast.walk(spec_tree)
            if isinstance(node, ast.ImportFrom) and node.level > 0
        }
        self.assertEqual(relative, {"events"})

    def test_only_landed_derivation_consumers_import_spec(self):
        """**接入白名单**：三处生产派生 + 一处契约派生。

        - 生产：`mapping.py`（D1）、`config/defaults.py`（D3）、`manager.py`（D2）
        - 契约：`tests/test_notification_e2e.py`（D4 完整形态——EVENTS 元数据由规格派生）

        任何**未在计划内**的模块 import 事件规格都在此拦截。
        """
        allowed = {
            "pilotstd/core/notification/mapping.py",
            "pilotstd/core/config/defaults.py",
            "pilotstd/core/notification/manager.py",
            "tests/test_notification_e2e.py",
            # D5：可订阅事件清单改由后端端点下发（前端零硬编码）⇒ 端点与其测试是合法消费方
            "docker/api/notification_config.py",
            "tests/test_notification_api.py",
            # C：用户时刻清单（第二 SSOT）与事件规格的**双向闭包**需要事件键集合 ⇒
            # 本用例是闭包断言方（只读事件键，不派生文案/渠道），属计划内的契约消费方
            "tests/test_user_moments.py",
        }
        self_relative = SPEC_FILE.relative_to(ROOT).as_posix()
        this_file = Path(__file__).resolve().relative_to(ROOT).as_posix()
        offenders = []
        for root_name in ("pilotstd", "docker", "scripts", "tests"):
            for path in (ROOT / root_name).rglob("*.py"):
                rel = path.relative_to(ROOT).as_posix()
                if rel in (self_relative, this_file, *allowed) or "__pycache__" in path.parts:
                    continue
                try:
                    tree = ast.parse(path.read_text(encoding="utf-8"))
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom) and (node.module or "").endswith("event_spec"):
                        offenders.append(rel)
                    if isinstance(node, ast.Import) and any(a.name.endswith("event_spec") for a in node.names):
                        offenders.append(rel)
        self.assertEqual(sorted(set(offenders)), [], f"出现计划外的规格消费方: {sorted(set(offenders))}")
        landed = allowed & {
            path.relative_to(ROOT).as_posix() for path in ROOT.rglob("*.py") if path.is_file()
        }
        self.assertEqual(landed, allowed, "白名单里的消费方文件必须真实存在（防白名单失效）")


if __name__ == "__main__":
    unittest.main()
