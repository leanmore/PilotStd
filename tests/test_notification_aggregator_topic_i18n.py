# tests/test_notification_aggregator_topic_i18n.py
# 测试主题分组的 i18n 契约（专项修复：繁中/英文标题归组错误）
"""锁定 `_extract_topic` 的**跨语言**主题判定契约。

修复前的缺陷（实测）：
- 关键词表**只含简体中文**，故 `失败`（zh_CN）命中而 `失敗`（zh_TW）不命中；
- 全新英文标题一律不命中；
- 未命中者落到「标题前 8 字符 + `_`」兜底 → **同一事件在不同语言下归入不同分组**，
  跨语言完全不合并；实测 39 事件 × 3 语言中 **65 条**落兜底。

修复后：以 i18n 的**真实标题**为契约（47 个 `.title*` 键实测 39/39 可映射到事件），
建立「三语标题 → 主题」索引做精确匹配；未命中才退回原简体关键词表。
"""

import ast
import json
import re
from pathlib import Path

import pytest

from pilotstd.core.notification_aggregator import (
    _BUFFER_WINDOW,
    NotificationAggregator,
)

ROOT = Path(__file__).resolve().parent.parent
I18N = ROOT / "pilotstd" / "i18n"
LANGS = ("zh_CN", "zh_TW", "en")
# 与 `i18n/__init__.py` 的 DEFAULT_LANGUAGE 同源
DEFAULT_LANG = "zh_CN"


def _events_from_registry() -> list[str]:
    """从 events.py 的 ALL_EVENTS 提取事件键（AnnAssign + 常量名解析）。"""
    tree = ast.parse((ROOT / "pilotstd/core/notification/events.py").read_text(encoding="utf-8"))
    consts: dict[str, str] = {}
    values: list[ast.expr] = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.startswith("EVENT_"):
                    consts[target.id] = str(node.value.value)
        elif isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "ALL_EVENTS":
            if isinstance(node.value, ast.List):
                values = list(node.value.elts)
    out: list[str] = []
    for elt in values:
        if isinstance(elt, ast.Call) and elt.args:
            arg = elt.args[0]
            if isinstance(arg, ast.Constant):
                out.append(str(arg.value))
            elif isinstance(arg, ast.Name):
                out.append(consts.get(arg.id, ""))
    return [e for e in out if e]


def _pack(lang: str) -> dict[str, str]:
    return json.loads((I18N / f"{lang}.json").read_text(encoding="utf-8"))


def _title_keys_for(event: str, pack: dict[str, str]) -> list[str]:
    """该事件的全部标题键（含 `.title.start` 等变体）。"""
    return [
        k
        for k in pack
        if k.startswith("notification.") and ".title" in k and event in k.split(".")
    ]


def _render(template: str) -> str:
    """把 i18n 模板渲染为具体标题（占位符替换为示例值）。"""
    return re.sub(r"\{[^}]*\}", "3", template)


EVENTS = _events_from_registry()


@pytest.fixture(autouse=True)
def _reset_index():
    """每个用例前后清空标题索引缓存，避免用例间通过类级缓存串状态。"""
    NotificationAggregator._title_index_cache = None
    yield
    NotificationAggregator._title_index_cache = None


class TestTrilingualTopicConsistency:
    """核心契约：同一事件的标题在**三种语言**下必须归入同一主题。"""

    def test_every_event_maps_to_exactly_one_topic_across_languages(self):
        """39 事件 × 全部标题变体 × 3 语言 → 每个事件只产生一个主题。"""
        pack = _pack(DEFAULT_LANG)
        inconsistent: list[str] = []
        for event in EVENTS:
            keys = _title_keys_for(event, pack)
            assert keys, f"{event} 无标题键，契约测试失效"
            topics = set()
            for lang in LANGS:
                lp = _pack(lang)
                for key in keys:
                    template = lp.get(key)
                    if not isinstance(template, str):
                        continue
                    topics.add(NotificationAggregator._extract_topic(_render(template), ""))
            if len(topics) > 1:
                inconsistent.append(f"{event} -> {sorted(topics)}")
        assert inconsistent == [], f"跨语言主题不一致：{inconsistent}"

    def test_no_event_falls_back_to_prefix_bucket(self):
        """无事件应落到「标题前 8 字符 + `_`」兜底（那是修复前的 65 条缺陷形态）。

        `validity_round_summary` 是**已知例外**：其标题含裸值型占位符
        `第 {round} 轮…`（无括号可剔除），模板与渲染值无法精确匹配，故仍走兜底。
        该兜底在**各语言内**的分组仍然稳定（同语言的同轮次标题归一组），
        因而不影响实际合并效果——此处按例外白名单登记，防止掩盖新退化。
        """
        known_fallback = {"validity_round_summary"}
        pack = _pack(DEFAULT_LANG)
        offenders: list[str] = []
        for event in EVENTS:
            if event in known_fallback:
                continue
            keys = _title_keys_for(event, pack)
            for lang in LANGS:
                lp = _pack(lang)
                for key in keys:
                    template = lp.get(key)
                    if not isinstance(template, str):
                        continue
                    topic = NotificationAggregator._extract_topic(_render(template), "")
                    if topic.startswith("_"):
                        offenders.append(f"{event}/{lang}: {_render(template)!r} -> {topic}")
        assert offenders == [], f"存在落兜底的已注册事件标题：{offenders}"

    def test_known_fallback_exception_is_stable_per_language(self):
        """已知例外 `validity_round_summary`：兜底分组在**同语言内**必须稳定合并。"""
        pack = _pack(DEFAULT_LANG)
        key = next(k for k in _title_keys_for("validity_round_summary", pack))
        for lang in LANGS:
            template = _pack(lang)[key]
            topics = {
                NotificationAggregator._extract_topic(
                    re.sub(r"\{[^}]*\}", str(n), template), ""
                )
                for n in (1, 2, 3)
            }
            assert len(topics) == 1, f"{lang}: 同语言不同轮次未合并 -> {topics}"

    def test_specific_regressions_from_recon(self):
        """锁定侦察阶段实测出的具体错误归类（修复前 zh_TW/en 全错）。"""
        cases = [
            ("扫描完成（3 个无法识别）", "done"),
            ("自动扫描失败", "error"),
            ("收藏下载失败", "error"),
            ("归档完成", "done"),
            ("掃描完成（3 個無法識別）", "done"),
            ("自動掃描失敗", "error"),
            ("收藏下載失敗", "error"),
            ("歸檔完成", "done"),
            ("Scan Complete (3 unrecognized)", "done"),
            ("Auto Scan Failed", "error"),
            ("Favorite Download Failed", "error"),
            ("Archive Complete", "done"),
        ]
        for title, expected in cases:
            got = NotificationAggregator._extract_topic(title, "")
            assert got == expected, f"{title!r} -> {got!r}（期望 {expected!r}）"


class TestTitleIndexContract:
    """索引本身的契约：覆盖面、语言中立性、动态标题处理。"""

    def test_index_covers_all_events(self):
        """索引必须覆盖全部 39 个已注册事件（三语都登记）。"""
        index = NotificationAggregator._title_index_data()[0]
        assert index, "索引为空"
        pack = _pack(DEFAULT_LANG)
        missing: list[str] = []
        for event in EVENTS:
            keys = _title_keys_for(event, pack)
            for lang in LANGS:
                lp = _pack(lang)
                for key in keys:
                    template = lp.get(key)
                    if isinstance(template, str) and template not in index:
                        missing.append(f"{event}/{lang}: {key}")
        # 含占位符的模板若已被"规范化键"覆盖则不算缺失
        truly_missing = [
            m
            for m in missing
            if NotificationAggregator._strip_bracketed(m.split(": ", 1)[1]) not in index
        ]
        assert truly_missing == [], f"索引未覆盖：{truly_missing[:5]}"

    def test_index_is_language_neutral(self):
        """索引构建与"当前语言"无关：切换语言后索引内容不变。"""
        from pilotstd.i18n import get_language, set_language

        before = get_language()
        try:
            set_language("zh_CN")
            first = dict(NotificationAggregator._title_index_data()[0])
            NotificationAggregator._title_index_cache = None
            set_language("en")
            second = dict(NotificationAggregator._title_index_data()[0])
        finally:
            set_language(before)
        assert first == second, "索引内容随语言变化，跨语言合并会失效"

    def test_strip_bracketed_removes_dynamic_count(self):
        """括号剔除应移除动态计数（含嵌套括号），保留稳定文本。"""
        strip = NotificationAggregator._strip_bracketed
        assert strip("Scan Complete (3 unrecognized)") == "Scan Complete"
        assert strip("扫描完成（3 个无法识别）") == "扫描完成"
        # 无括号的标题原样保留
        assert strip("Auto Scan Failed") == "Auto Scan Failed"
        # 多空格折叠
        assert strip("A  B") == "A B"

    def test_dynamic_title_resolves_to_domain_topic(self):
        """含动态计数的标题仍应命中索引（而非落到兜底）。"""
        assert NotificationAggregator._extract_topic("Scan Complete (7 unrecognized)", "") == "done"
        assert NotificationAggregator._extract_topic("扫描完成（9 个无法识别）", "") == "done"


class TestLegacyFallbackStillWorks:
    """向后兼容：未在索引中的自定义标题仍走原简体关键词表。"""

    @pytest.mark.parametrize(
        ("title", "expected"),
        [
            ("扫描文件", "scan"),
            ("下载失败", "error"),
            ("归档文件", "archive"),
            ("查询结果", "query"),
            ("备份数据", "backup"),
            ("公告通知", "announce"),
            ("更新镜像", "update"),
            ("IP变更", "ip"),
            ("例行维护", "_例行维护"),
        ],
    )
    def test_legacy_keyword_path(self, title: str, expected: str):
        assert NotificationAggregator._extract_topic(title, "") == expected

    def test_empty_title_yields_nonempty_topic(self):
        """兜底返回值永不为空（分组键不能为空串）。"""
        assert NotificationAggregator._extract_topic("", "") == "_default"


class TestBufferWindowIntent:
    """专项确认 `_BUFFER_WINDOW = 0.3s` 的设计意图（不变更该值）。"""

    def test_buffer_window_is_unchanged(self):
        """0.3s 是桌面 toast 的合并窗口，与服务端 5.0s 分属两条链路，不得对齐。"""
        assert _BUFFER_WINDOW == 0.3

    def test_buffer_window_is_decoupled_from_server_window(self):
        """不得与服务端聚合窗口取同一值（否则桌面 toast 会被压成 5 秒一轮）。"""
        from pilotstd.core.notification.aggregate_buffer import DEFAULT_WINDOW_SECONDS

        assert _BUFFER_WINDOW != DEFAULT_WINDOW_SECONDS
        assert _BUFFER_WINDOW < DEFAULT_WINDOW_SECONDS
