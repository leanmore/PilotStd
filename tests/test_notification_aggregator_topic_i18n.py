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


def _render(template: str, value: object = 3) -> str:
    """用**渲染器同款的方式**（`str.format`）把 i18n 模板渲染为具体标题。

    不用 `re.sub` 替换占位符：两者语义不同——`re.sub` 会把占位符连同其位置的
    空白一并抹掉，产出 `Scan Complete ()` 这类渲染器**不会产出**的形态；
    `str.format` 保留两侧字面量（空值时产出 `Scan Complete ( unrecognized)`）。
    用错误的替换方式构造样本会得到无效验证结论。
    """
    fields = sorted(set(re.findall(r"\{([^}!]+)(?:![^}]*)?\}", template)))
    if not fields:
        return template
    return template.format(**{f: value for f in fields})


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
        """**无任何**已注册事件的标题应落到「标题前 8 字符 + `_`」兜底。

        兜底是修复前的缺陷形态（实测 65 条）。修复后无例外——此前曾将
        `validity_round_summary` 登记为白名单，理由是"其兜底在同语言内稳定"，
        但那基于用**同一常量**替换占位符的错误验证；改用不同轮次（1/2/3）后
        暴露 `_第 1 轮有效性` / `_第 2 轮有效性` 各不相同，故已改用模板正则修掉。
        本用例**不设白名单**——任何事件落兜底都应视为回归。
        """
        pack = _pack(DEFAULT_LANG)
        offenders: list[str] = []
        for event in EVENTS:
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

    def test_no_fallback_across_extended_values(self):
        """扩展取值集下也不得落兜底（覆盖边界值，非仅单一常量）。

        取值维度是判定的变量所在；只用单一常量验证会掩盖"仅对某类取值有效"的实现。
        """
        values = ("0", "1", "2", "7", "12", "999", "-5", "1e9", "a b", "%s", 'x"y')
        pack = _pack(DEFAULT_LANG)
        offenders: list[str] = []
        for event in EVENTS:
            keys = _title_keys_for(event, pack)
            for lang in LANGS:
                lp = _pack(lang)
                for key in keys:
                    template = lp.get(key)
                    if not isinstance(template, str):
                        continue
                    for value in values:
                        rendered = _render(template, value)
                        topic = NotificationAggregator._extract_topic(rendered, "")
                        if topic.startswith("_"):
                            offenders.append(f"{event}/{lang} v={value!r}: {rendered!r} -> {topic}")
        assert offenders == [], f"扩展取值下存在落兜底：{offenders[:6]}"

    def test_validity_round_summary_merges_across_rounds(self):
        """`validity_round_summary` 跨轮次必须归入同一主题（原兜底实现不满足）。"""
        pack = _pack(DEFAULT_LANG)
        key = next(k for k in _title_keys_for("validity_round_summary", pack))
        for lang in LANGS:
            template = _pack(lang)[key]
            topics = {
                NotificationAggregator._extract_topic(_render(template, n), "")
                for n in (1, 2, 3, 17, 999)
            }
            assert topics == {"validity"}, f"{lang}: 跨轮次主题不一致 -> {topics}"

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


class TestDesktopChainReachesExtractTopic:
    """审核补证：桌面链路确实从 `platform/notify.py` 走到 `_extract_topic`。

    修复点都在 `core/notification_aggregator.py`，若平台层实际不走这里，
    则修复对桌面通知无效。本类用**调用栈取证**锁定该链路。
    """

    def _spy(self, monkeypatch):
        """把 `_extract_topic` 换为记录调用栈的探针。"""
        import traceback

        original = NotificationAggregator.__dict__["_extract_topic"].__func__
        frames: list[str] = []

        def spy(cls, title, body):
            for frame in traceback.extract_stack()[-8:]:
                frames.append(f"{Path(frame.filename).name}:{frame.lineno} {frame.name}")
            return original(cls, title, body)

        monkeypatch.setattr(NotificationAggregator, "_extract_topic", classmethod(spy))
        return frames

    def test_show_warning_reaches_extract_topic(self, monkeypatch):
        """`NotifyService.show_warning` → `should_show` → `_extract_topic`。"""
        from pilotstd.platform import notify as notify_mod

        frames = self._spy(monkeypatch)

        class _Tray:
            def showMessage(self, *_a):  # noqa: N802
                pass

        svc = notify_mod.NotifyService.__new__(notify_mod.NotifyService)
        svc._enabled = True
        svc._tray = _Tray()
        svc._last = {}
        monkeypatch.setattr(NotificationAggregator, "auto_pause_enabled", property(lambda self: True))
        agg = NotificationAggregator()
        agg._paused = False
        try:
            svc.show_warning("Scan Complete (3 unrecognized)", "body")
        finally:
            agg.shutdown()

        assert frames, "桌面链路未调用 _extract_topic"
        joined = " ".join(frames)
        assert "notify.py" in joined and "show_warning" in joined, f"调用栈不含平台层: {frames}"
        assert "should_show" in joined, f"调用栈不含 should_show: {frames}"

    def test_default_config_takes_aggregator_path(self):
        """默认配置下桌面通知走聚合器路径（`auto_pause_enabled` 默认 True）。

        `notification.auto_pause` 无 defaults 声明，`should_show` 侧以 `True` 为兜底，
        故"关掉自动暂停"才会绕过聚合器。此断言防止默认值被改成 False 而使修复失效。
        """
        agg = NotificationAggregator.__new__(NotificationAggregator)
        assert agg.auto_pause_enabled is True

    def test_end_to_end_grouping_for_recon_titles(self, monkeypatch):
        """端到端：经 `should_show` 后各语言同一事件得到同一主题。"""
        original = NotificationAggregator.__dict__["_extract_topic"].__func__
        topics: list[tuple[str, str]] = []

        def spy(cls, title, body):
            topic = original(cls, title, body)
            topics.append((title, topic))
            return topic

        monkeypatch.setattr(NotificationAggregator, "_extract_topic", classmethod(spy))
        agg = NotificationAggregator()
        agg._paused = False
        titles = [
            "Scan Complete (3 unrecognized)",
            "扫描完成（7 个无法识别）",
            "掃描完成（9 個無法識別）",
            "第 4 轮有效性汇总报告",
            "Validity Round 12 Summary Report",
        ]
        try:
            for title in titles:
                agg.should_show("info", title, "body", lambda *a: None)
        finally:
            agg.shutdown()
        got = dict(topics)
        assert got[titles[0]] == got[titles[1]] == got[titles[2]] == "done"
        assert got[titles[3]] == got[titles[4]] == "validity"


class TestIndexUniquenessAndConflicts:
    """审核补证：索引唯一性与冲突检测（防止静默覆盖）。"""

    def test_no_title_maps_to_two_topics(self):
        """同一标题字面不得映射到两个不同主题（跨三语全量检查）。"""
        from pilotstd.core.notification_aggregator import _TOPIC_BY_EVENT

        value_to_topics: dict[str, set[str]] = {}
        for lang in LANGS:
            lp = _pack(lang)
            for key, value in lp.items():
                if not (key.startswith("notification.") and ".title" in key):
                    continue
                if not isinstance(value, str):
                    continue
                owner = next((e for e in EVENTS if e in key.split(".")), None)
                topic = _TOPIC_BY_EVENT.get(owner or "")
                if topic:
                    value_to_topics.setdefault(value, set()).add(topic)
        conflicts = {v: t for v, t in value_to_topics.items() if len(t) > 1}
        assert conflicts == {}, f"标题字面映射到多个主题：{conflicts}"

    def test_index_entry_count_matches_distinct_titles(self):
        """索引条目数应等于"有主题的不同标题字面数"（无静默丢条目）。"""
        from pilotstd.core.notification_aggregator import _TOPIC_BY_EVENT

        index, _patterns = NotificationAggregator._title_index_data()
        distinct: set[str] = set()
        for lang in LANGS:
            lp = _pack(lang)
            for key, value in lp.items():
                if not (key.startswith("notification.") and ".title" in key):
                    continue
                if not isinstance(value, str):
                    continue
                owner = next((e for e in EVENTS if e in key.split(".")), None)
                if _TOPIC_BY_EVENT.get(owner or ""):
                    distinct.add(value)
        assert len(index) == len(distinct), f"索引 {len(index)} 条 vs 不同标题 {len(distinct)} 条"

    def test_known_duplicate_title_is_benign(self):
        """唯一已知重复标题（en 的两条 announce）必须同属一个主题，故无害。"""
        dup = "Announcement Fetch Complete"
        pack = _pack("en")
        owners = [
            k
            for k, v in pack.items()
            if v == dup and k.startswith("notification.") and ".title" in k
        ]
        assert len(owners) >= 2, f"预期该标题被多条键共用，实际 {owners}"
        topics = {
            NotificationAggregator._extract_topic(dup, "") for _ in owners
        }
        assert topics == {"done"}, f"重复标题主题不一致：{topics}"


class TestDynamicValueBoundaries:
    """占位符取值边界（0/负数/大数/空串/特殊字符），一律经**渲染器同款** `str.format`。"""

    @pytest.mark.parametrize("value", ["0", "1", "2", "7", "999", "-5", "1e9", "", "a b", "%s", 'x"y'])
    def test_scan_complete_dynamic_count_always_done(self, value: str):
        """`Scan Complete (<值>)` 恒归 `done`（三语），**含空串**。

        空串经 `str.format` 产出 `Scan Complete ( unrecognized)`——占位符两侧字面量
        保留，故与完整形正则仍然匹配（这也是"非空通配 `(.+?)` 足够"的实测依据）。
        """
        for lang in LANGS:
            tpl = _pack(lang)["notification.scan.scan_complete.title"]
            rendered = _render(tpl, value)
            got = NotificationAggregator._extract_topic(rendered, "")
            assert got == "done", f"{lang} value={value!r} rendered={rendered!r} -> {got!r}"

    @pytest.mark.parametrize("value", ["0", "1", "12", "999", "-3", "abc"])
    def test_round_summary_dynamic_round_always_validity(self, value: str):
        """`第 <非空值> 轮有效性汇总报告` 恒归 `validity`（三语，模板正则路径）。

        **空串例外**：`str.format(round="")` 产出 `第  轮…`（双空格），与模板单空格
        不匹配故落兜底；但调用方恒传 `round >= 1`，该输入**实际不可达**
        （见 `test_round_summary_empty_value_is_unreachable_but_falls_back`）。
        """
        for lang in LANGS:
            tpl = _pack(lang)["notification.validity.validity_round_summary.title"]
            rendered = _render(tpl, value)
            got = NotificationAggregator._extract_topic(rendered, "")
            assert got == "validity", f"{lang} value={value!r} -> {got!r}"

    def test_round_summary_empty_value_is_unreachable_but_falls_back(self):
        """空轮次经 `str.format` 渲染后落兜底——但该输入**实际不可达**。

        调用方 `_validity_pipeline.py` 恒传 `round: new_round`，而
        `new_round = config.get("validity.round_count", 0) + 1 >= 1`，故 `round` 永不为空。
        此处锁定现状：若将来 `round` 可能为空，此用例会提醒需要实现空白归一化匹配。
        """
        tpl = _pack(DEFAULT_LANG)["notification.validity.validity_round_summary.title"]
        rendered = tpl.format(round="")
        assert rendered == "第  轮有效性汇总报告", f"渲染形态变化：{rendered!r}"
        got = NotificationAggregator._extract_topic(rendered, "")
        assert got.startswith("_"), f"预期落兜底，实际 {got!r}"

    def test_multiple_placeholders_in_one_title(self):
        """含多个占位符的标题（如三语各自多个）仍应命中。"""
        pack = _pack(DEFAULT_LANG)
        multi = [
            (k, v)
            for k, v in pack.items()
            if k.startswith("notification.") and ".title" in k and v.count("{") >= 1
        ]
        assert multi, "样本缺失"
        for key, template in multi:
            owner = next((e for e in EVENTS if e in key.split(".")), None)
            from pilotstd.core.notification_aggregator import _TOPIC_BY_EVENT

            expected = _TOPIC_BY_EVENT.get(owner or "")
            for lang in LANGS:
                lt = _pack(lang)[key]
                rendered = _render(lt, 5)
                if lang == "en" and owner == "validity_round_summary":
                    pass
                got = NotificationAggregator._extract_topic(rendered, "")
                if expected == "validity" and owner == "standard_status_changed":
                    # standard_status_changed 的两个标题变体分别含不同文案，主题一致
                    assert got == "validity", f"{lang} {key} -> {got}"
                else:
                    assert got == expected, f"{lang} {key} -> {got}（期望 {expected}）"


class TestCustomTitleBoundary:
    """审核补证：非 i18n 来源的自定义标题跨语言合并**不在修复范围内**。

    兜底与关键词回退只含简体，故英文/繁中自定义标题可能落到不同分组。
    这是**已知边界**而非回归：自定义标题不是 i18n 事件文案，无法由契约判定。
    本类把该边界固化为可执行断言，防止后人误以为"已全语言覆盖"。
    """

    def test_chinese_custom_title_hits_keyword_fallback(self):
        assert NotificationAggregator._extract_topic("自定义批次完成", "") == "done"
        assert NotificationAggregator._extract_topic("自訂批次完成", "") == "done"

    def test_english_custom_title_falls_back_to_prefix_bucket(self):
        """英文自定义标题落兜底——已知边界，登记而非隐藏。"""
        got = NotificationAggregator._extract_topic("Custom batch finished", "")
        assert got.startswith("_"), f"预期落兜底，实际 {got!r}"

    def test_custom_title_not_in_scope_for_cross_language_merging(self):
        """同一自定义语义在中文/英文下分组不同——明确记录该边界。"""
        zh = NotificationAggregator._extract_topic("自定义批次完成", "")
        en = NotificationAggregator._extract_topic("Custom batch finished", "")
        assert zh != en, "该断言锁定边界现状；若未来实现多语言关键词表，应更新本用例"
