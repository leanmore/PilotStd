# tests/test_audit_notification_chain.py
"""L-08 判定逻辑判别测试：A-1 / A-2 / A-3 的"能抓坏形态、不误报好形态"。

## 背景（修复前的实测缺陷）

- **A-1 `_return_empty_text_risk` 是恒真式**：`return (not has_body_kwarg) or empty_return`。
  40 个构建器**无一填写 `body`**（正文载体是 `blocks`）→ 40/40 全误报；且完全没看
  `blocks` 与 `title`，而 `manager.py` 的硬约束是"blocks / body / title 至少一项非空"。
- **A-2 `_missing_null_guards` 过粗**：只认 4 种窄形态，漏掉 `data.get(f, DEFAULT)`、
  正向真值 `if data.get(f):`、`or` 兜底、类型强转、作为可空 dataclass 字段传入 →
  115 个字段标记中 86 个实际有守卫（过粗率 74.8%）。
- **A-3 不解析 `EVENT_*` 常量名**：构建器侧与调用点侧都只认字面量 → 配对断裂、
  `--module` 过滤漏项。

## 判别力原则

每个"检测器"用例都成对给出**好形态**（必须不报）与**坏形态**（必须报）。仅有"坏形态被报"
不足以证明检测器有效——**恒真式也能通过那种断言**（这正是 A-1 的原始缺陷）。
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import audit_notification_chain_scan as S  # noqa: E402


def _fn(source: str) -> ast.FunctionDef:
    """把一段函数源码解析为 FunctionDef 节点。"""
    node = ast.parse(source).body[0]
    assert isinstance(node, ast.FunctionDef)
    return node


# ── A-1：empty_text_risk ──────────────────────────────────────────────────

class TestEmptyTextRisk:
    """A-1：只有 blocks / body / title **三者皆空**才算风险。"""

    def test_blocks_only_is_not_risk(self):
        """★ 好形态（生产实际写法）：只填 blocks —— 修复前此形态被误报。"""
        node = _fn('''
def _b(data: dict):
    return NotificationMessage(
        title=t("x.title"),
        blocks=[TextBlock(text="hi")],
    )
''')
        assert S._return_empty_text_risk(node) is False

    def test_body_only_is_not_risk(self):
        node = _fn('''
def _b(data: dict):
    return NotificationMessage(title="t", body="some text")
''')
        assert S._return_empty_text_risk(node) is False

    def test_title_only_is_not_risk(self):
        node = _fn('''
def _b(data: dict):
    return NotificationMessage(title="t")
''')
        assert S._return_empty_text_risk(node) is False

    def test_all_three_empty_is_risk(self):
        """★ 坏形态：三者皆空 → 必须报（这是 manager.py 明确会 raise 的情形）。"""
        node = _fn('''
def _b(data: dict):
    return NotificationMessage(title="", blocks=[])
''')
        assert S._return_empty_text_risk(node) is True

    def test_empty_literals_count_as_empty(self):
        node = _fn('''
def _b(data: dict):
    return NotificationMessage(title="t", body="", blocks=[])
''')
        assert S._return_empty_text_risk(node) is False  # 有 title

    def test_nonliteral_values_count_as_nonempty(self):
        """变量/调用结果视为非空（静态无法求值 → 取保守方向，避免再次恒真）。"""
        node = _fn('''
def _b(data: dict):
    return NotificationMessage(title=build_title(data), blocks=make_blocks(data))
''')
        assert S._return_empty_text_risk(node) is False


class TestHasNonemptyMessageKwarg:
    """A-1 的底层助手：空字面量不算"填了"。"""

    @pytest.mark.parametrize("value,expected", [
        ('"t"', True), ('build()', True), ('[TextBlock()]', True),
        ('""', False), ('[]', False), ('{}', False), ('None', False),
    ])
    def test_literal_classification(self, value: str, expected: bool):
        node = _fn(f'def _b(data):\n    return NotificationMessage(title={value})\n')
        assert S._has_nonempty_message_kwarg(node, "title") is expected

    def test_missing_kwarg_is_false(self):
        node = _fn('def _b(data):\n    return NotificationMessage(title="t")\n')
        assert S._has_nonempty_message_kwarg(node, "body") is False


# ── A-2：missing_null_guard ───────────────────────────────────────────────

class TestMissingNullGuards:
    """A-2：六种守卫形态都不得报；只有"无保护进入 .format()"才报。"""

    def _missing(self, body: str, fields: list[str] | None = None) -> list[str]:
        node = _fn("def _b(data: dict):\n" + body)
        used = S._used_fields(node)
        if fields is not None:
            assert used == set(fields), f"_used_fields 提取不符：{used}"
        return S._missing_null_guards(node, used)

    def test_default_value_is_guard(self):
        assert self._missing('    n = data.get("count", 0)\n    return n\n', ["count"]) == []

    def test_positive_truthiness_is_guard(self):
        """★ 原实现只匹配 `ast.Not`，漏掉正向真值判断 → 误报。"""
        assert self._missing(
            '    if data.get("url"):\n        return data["url"]\n    return None\n', ["url"]
        ) == []

    def test_negated_truthiness_is_guard(self):
        assert self._missing(
            '    if not data.get("url"):\n        return None\n    return 1\n', ["url"]
        ) == []

    def test_or_fallback_is_guard(self):
        assert self._missing(
            '    details = [str(d) for d in (data.get("details") or [])][:5]\n    return details\n',
            ["details"],
        ) == []

    def test_type_coercion_is_guard(self):
        assert self._missing('    ok = bool(data.get("ok"))\n    return ok\n', ["ok"]) == []

    def test_message_dataclass_field_is_guard(self):
        """★ 作为可空 dataclass 字段传入 —— None 是合法值，不是缺陷。"""
        assert self._missing(
            '    return NotificationMessage(title="t", standard_number=data.get("standard_number"))\n',
            ["standard_number"],
        ) == []

    def test_format_kwarg_is_guard(self):
        assert self._missing(
            '    return t("k").format(f=data.get("f", ""))\n', ["f"]
        ) == []

    def test_unguarded_format_is_reported(self):
        """★ 坏形态：无任何兜底却进入 .format() —— `None` 会被渲染成字面量 "None"。"""
        node = _fn('''
def _b(data: dict):
    return t("k").format(f=data["f"])
''')
        used = S._used_fields(node)
        assert S._missing_null_guards(node, used) == ["f"]

    def test_subscript_fields_are_collected(self):
        """★ 原 `_used_fields` 只采集 data.get(...)，漏掉下标读取。"""
        node = _fn('def _b(data):\n    return data["a"] + data["b"]\n')
        assert S._used_fields(node) == {"a", "b"}


class TestFieldOfGuardedValue:
    """A-2 的底层助手：识别"赋值即守卫"的各种包裹形态。"""

    @pytest.mark.parametrize("code,expected", [
        ('x = data.get("f") or []', "f"),
        ('x = [str(d) for d in (data.get("f") or [])][:5]', "f"),
        ('x = bool(data.get("f"))', "f"),
        ('x = str(data["f"])', "f"),
        ('x = data.get("f", 0)', "f"),
        ('x = data.get("f")', None),          # 无兜底、无强转 → 不算已守卫
        ('x = data["f"]', None),
    ])
    def test_forms(self, code: str, expected: str | None):
        value = ast.parse(code).body[0].value  # type: ignore[attr-defined]
        assert S._field_of_guarded_value(value) == expected


# ── A-3：EVENT_* 常量解析 ─────────────────────────────────────────────────

class TestEventConstResolution:
    """A-3：构建器与调用点都须解析 `EVENT_*` 常量名；不在符号表中的名字标动态。"""

    def test_const_map_from_events_file(self):
        const_map = S.load_event_const_map()
        assert const_map.get("EVENT_ARCHIVE_COMPLETE") == "archive_complete"
        assert const_map.get("EVENT_SECURITY_LOGIN_FAILED") == "security_login_failed"

    def test_builder_event_type_from_const(self):
        """★ 修复前：`event_type=EVENT_X` 返回 None（配对断裂）。"""
        node = _fn('''
def _build_x_message(data: dict):
    return NotificationMessage(title="t", event_type=EVENT_ARCHIVE_COMPLETE)
''')
        assert S._extract_event_type_from_func(node) == "archive_complete"

    def test_builder_event_type_from_literal(self):
        node = _fn('''
def _build_x_message(data: dict):
    return NotificationMessage(title="t", event_type="archive_complete")
''')
        assert S._extract_event_type_from_func(node) == "archive_complete"

    def test_unknown_name_is_not_fabricated(self):
        """★ 防过度解析：不在符号表中的名字必须返回 None，不得臆造。"""
        node = _fn('''
def _build_x_message(data: dict):
    return NotificationMessage(title="t", event_type=NOT_A_KNOWN_CONST)
''')
        assert S._extract_event_type_from_func(node) is None

    def test_call_site_const_resolved(self):
        """★ 修复前：调用点第一实参为常量名时标 `<const:EVENT_X>` 而不解析。"""
        arg = ast.parse("EVENT_ARCHIVE_COMPLETE", mode="eval").body
        assert S._resolve_event_arg(arg, frozenset()) == "archive_complete"

    def test_call_site_literal_resolved(self):
        arg = ast.parse('"normalize_complete"', mode="eval").body
        assert S._resolve_event_arg(arg, frozenset()) == "normalize_complete"

    def test_call_site_param_marked_dynamic(self):
        """★ 形参无法静态确定唯一事件 → 标 `<dynamic>`，不臆造也不留 `<const:...>`。"""
        arg = ast.parse("event_type", mode="eval").body
        assert S._resolve_event_arg(arg, frozenset({"event_type"})) == "<dynamic>"


# ── 端到端：仓库当前应为 0 问题 ───────────────────────────────────────────

class TestRepositoryBaseline:
    """修复后仓库问题数必须为 0（否则 CI 接入即红）。"""

    def test_no_problems_in_repo(self):
        from audit_notification_chain import _collect_problems  # noqa: PLC0415

        builders = S.extract_builders()
        exceptions = S.detect_swallowed_exceptions("notification")
        problems = _collect_problems(builders, exceptions)
        assert problems == [], f"仓库仍有 {len(problems)} 项发现：{[p['message'] for p in problems[:5]]}"

    def test_events_and_builders_paired(self):
        """每个事件都应有对应构建器（A-3 修复后配对不应断裂）。"""
        events = {e["key"] for e in S.extract_events(S.EVENTS_FILE)}
        builders = {b["event_type"] for b in S.extract_builders() if b.get("event_type")}
        missing = sorted(events - builders)
        assert missing == [], f"以下事件无对应构建器：{missing}"

    def test_call_sites_have_no_unresolved_const_markers(self):
        """★ A-3 验收：调用点不得残留 `<const:...>` 标记。"""
        sites = S.extract_call_sites()
        bad = [s for s in sites if isinstance(s["event_type"], str) and s["event_type"].startswith("<const:")]
        assert bad == [], f"仍有未解析常量：{[(s['file'], s['lineno'], s['event_type']) for s in bad]}"
