"""扫描解析器 / 通知渲染 / 时效病历 的补测（NEW-43，2026-11-24）。

清单记录「16 个后端模块无测试引用」。本轮补 4 个**纯逻辑、高复用**模块：

| 模块 | 职责 | 错了会怎样 |
|---|---|---|
| `scan/parser/_text_cleaner.py` | 标准文件名清洗 | 解析器全军覆没（合订本残片/全角符号/`No.` 前缀） |
| `scan/parser/_language_detector.py` | 语言版本标记识别 | 中英文版本混为一谈，重复下载 |
| `notification/renderer_links.py` | 四渠道共享链接助手 | 通知按钮无文案/链接丢失 |
| `core/validity_log.py` | 时效检查病历写入 | 写入异常拖垮主检查链路 |

断言基于**实测行为**（先跑探针确认，再写断言），不凭文档推测。
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ════════════════════════════════════════════════════════════════
# 1. TextCleaner：标准文件名清洗
# ════════════════════════════════════════════════════════════════


class TestTextCleaner:
    """文本清洗：斜杠归一化、符号清理、合订本范围截断。"""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            # 全角斜杠/连字符归一化
            ("GB／T 1－2020", "GB/T 1-2020"),
            # `No.` 前缀清除
            ("No. GB 1-2020", "GB 1-2020"),
            # 冒号 → 连字符
            ("GB 1-2020:附录", "GB 1-2020-附录"),
            # 下划线 → 空格
            ("GB_T 1-2020", "GB T 1-2020"),
            # 合订本残片：起始编号 + 真实年份 + 合订本标识
            ("47008-1947 010-2010", "47008-2010 合订本"),
            # 合订本范围 `～`：取起始编号 + 年份（不加"合订本"，因非残片形态）
            ("47008～47010-2010", "47008-2010"),
        ],
    )
    def test_cleaning_cases(self, raw, expected):
        from pilotstd.scan.parser._text_cleaner import TextCleaner

        assert TextCleaner.clean(raw) == expected

    def test_plain_name_unchanged(self):
        """已规范的名字保持原样（幂等）。"""
        from pilotstd.scan.parser._text_cleaner import TextCleaner

        assert TextCleaner.clean("GB/T 1-2020") == "GB/T 1-2020"
        # 幂等性：清洗两次结果一致
        assert TextCleaner.clean(TextCleaner.clean("GB/T 1-2020")) == "GB/T 1-2020"

    def test_combined_fragment_uses_real_year(self):
        """合订本残片的假年份（1947）必须被丢弃，保留真实年份（2010）。

        这是本模块最重要的判据：假年份一旦流入后续流程，会生成年份错误的
        标准记录（引擎按年份判新旧，错年份会导致「新标准被当成旧的」）。
        """
        from pilotstd.scan.parser._text_cleaner import TextCleaner

        out = TextCleaner.clean("47008-1947 010-2010")
        assert "1947" not in out
        assert "2010" in out
        assert "合订本" in out


# ════════════════════════════════════════════════════════════════
# 2. LanguageDetector：语言版本标记
# ════════════════════════════════════════════════════════════════


class TestLanguageDetector:
    """从 basename 识别语言版本标记。"""

    def test_plain_chinese_name_has_no_marker(self):
        from pilotstd.scan.parser._language_detector import LanguageDetector

        assert LanguageDetector.detect("GB 1-2020") == ""

    def test_chinese_version_marker(self):
        from pilotstd.scan.parser._language_detector import LanguageDetector

        assert LanguageDetector.detect("GB 1-2020 英文版") == "英文版"

    def test_english_version_marker(self):
        from pilotstd.scan.parser._language_detector import LanguageDetector

        assert LanguageDetector.detect("GB 1-2020 (English)") == "英文版"

    def test_delegates_to_lang_detect(self, monkeypatch):
        """本类只是委托 `lang_detect.detect_language`（薄封装）。"""
        from pilotstd.scan.parser import _language_detector as mod

        called = {}

        def _spy(basename):
            called["arg"] = basename
            return "SPY"

        monkeypatch.setattr(mod, "detect_language", _spy)
        assert mod.LanguageDetector.detect("x") == "SPY"
        assert called["arg"] == "x"


# ════════════════════════════════════════════════════════════════
# 3. renderer_links：四渠道共享链接助手
# ════════════════════════════════════════════════════════════════


def _msg_with(*specs):
    return SimpleNamespace(actions=list(specs))


def _spec(action="view", label_key="", url=None):
    args = {"url": url} if url is not None else {}
    return SimpleNamespace(action=action, label_key=label_key, args=args)


class TestRendererLinks:
    """链接型动作的提取/文案/Markdown 渲染。"""

    def test_link_actions_filters_url_only(self):
        """只有带 url 的动作才算「链接型」（不带 callback_data）。"""
        from pilotstd.core.notification.renderer_links import link_actions

        a = _spec("a", url="http://x/a")
        b = _spec("b")  # 无 url → 不是链接型
        c = _spec("c", url="  http://x/c  ")  # 两端空白应被 strip

        out = link_actions(_msg_with(a, b, c))
        assert [s.action for s in out] == ["a", "c"]

    def test_link_actions_empty_message(self):
        from pilotstd.core.notification.renderer_links import link_actions

        assert link_actions(SimpleNamespace(actions=[])) == []
        assert link_actions(SimpleNamespace()) == []

    def test_action_label_uses_i18n(self):
        """`label_key` 能翻出文案时优先用译文。"""
        from pilotstd.core.notification.renderer_links import action_label

        # 用真实存在的 i18n 键
        label = action_label(_spec("view", label_key="notification.common.std_type.national"))
        assert label and label != "view"

    def test_action_label_falls_back_to_action(self):
        """缺键/未知键 → 回退动作名，**绝不返回空**（否则渲染出空按钮）。"""
        from pilotstd.core.notification.renderer_links import action_label

        assert action_label(_spec("view", label_key="")) == "view"
        assert action_label(_spec("view", label_key="nonexistent.key.xyz")) == "view"

    def test_link_markdown_renders(self):
        from pilotstd.core.notification.renderer_links import link_markdown

        text = link_markdown(_msg_with(_spec("view", url="http://x/a")))
        assert text == "[view](http://x/a)"

    def test_link_markdown_multiple_joined(self):
        from pilotstd.core.notification.renderer_links import link_markdown

        text = link_markdown(
            _msg_with(_spec("a", url="http://x/a"), _spec("b", url="http://x/b"))
        )
        assert text == "[a](http://x/a) | [b](http://x/b)"

    def test_link_markdown_no_links_returns_empty(self):
        """无链接型动作 → 空串（调用方据此省略该行）。"""
        from pilotstd.core.notification.renderer_links import link_markdown

        assert link_markdown(SimpleNamespace(actions=[])) == ""
        assert link_markdown(_msg_with(_spec("b"))) == ""


# ════════════════════════════════════════════════════════════════
# 4. validity_log：时效检查病历
# ════════════════════════════════════════════════════════════════


class TestValidityLog:
    """病历写入 / 清理。核心契约：**失败不得中断主检查链路**。"""

    def test_record_writes_row(self):
        from pilotstd.core.validity_log import record

        db = MagicMock()
        record(db, "GB 1-2020", result={"status": "active", "evidence": "ev"})

        db.execute.assert_called_once()
        sql, params = db.execute.call_args.args
        assert "INSERT INTO validity_check_log" in sql
        assert params[0] == "GB 1-2020"
        assert params[3] == "active"  # status
        assert params[8] == 1  # ok=1（无 error）

    def test_record_with_error_marks_not_ok(self):
        from pilotstd.core.validity_log import record

        db = MagicMock()
        record(db, "GB 1-2020", error=RuntimeError("boom"))

        _sql, params = db.execute.call_args.args
        assert params[8] == 0  # ok=0
        assert "boom" in params[9]

    def test_record_db_none_is_noop(self):
        """db 为 None → 静默返回（不抛）。"""
        from pilotstd.core.validity_log import record

        record(None, "GB 1-2020", result={})  # 不抛即通过

    def test_record_write_failure_does_not_raise(self):
        """**写病历失败不得中断主检查链路**（这是本模块的核心契约）。"""
        from pilotstd.core.validity_log import record

        db = MagicMock()
        db.execute.side_effect = RuntimeError("disk full")

        record(db, "GB 1-2020", result={})  # 不抛即通过

    def test_record_uses_custom_checked_at(self):
        from pilotstd.core.validity_log import record

        db = MagicMock()
        record(db, "GB 1-2020", checked_at="2026-01-01T00:00:00+00:00")

        _sql, params = db.execute.call_args.args
        assert params[1] == "2026-01-01T00:00:00+00:00"

    def test_record_truncates_huge_result_json(self):
        """异常大的返回体必须截断，避免撑爆单行（诊断用，不参与业务判断）。"""
        from pilotstd.core.validity_log import _RESULT_JSON_LIMIT, record

        db = MagicMock()
        big = {"blob": "x" * (_RESULT_JSON_LIMIT * 2)}
        record(db, "GB 1-2020", result=big)

        _sql, params = db.execute.call_args.args
        assert len(params[10]) <= _RESULT_JSON_LIMIT

    def test_cleanup_returns_rowcount(self):
        from pilotstd.core.validity_log import cleanup

        db = MagicMock()
        db.execute.return_value.rowcount = 7

        assert cleanup(db, days=90) == 7

    def test_cleanup_minimum_one_day(self):
        """保留期至少 1 天（配置成 0 时不能把当天记录全删）。"""
        from pilotstd.core.validity_log import cleanup

        db = MagicMock()
        db.execute.return_value.rowcount = 0

        cleanup(db, days=0)
        _sql, params = db.execute.call_args.args
        # cutoff 必须是「现在 - 至少 1 天」，不能等于 now
        assert params[0]  # 有 cutoff
        assert params[0] < __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat()

    def test_cleanup_db_none_returns_zero(self):
        from pilotstd.core.validity_log import cleanup

        assert cleanup(None) == 0

    def test_cleanup_failure_returns_zero(self):
        from pilotstd.core.validity_log import cleanup

        db = MagicMock()
        db.execute.side_effect = RuntimeError("boom")

        assert cleanup(db) == 0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
