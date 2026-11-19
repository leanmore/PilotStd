"""tests/test_check_g_012_comment_lang.py — G-012 `[LANG]` 按词判定口径（V-17，2026-11-19）。

背景：原规则「注释里出现任意英文字母即警告」，对中文注释引用标识符 100% 误报
（全仓 1511 条里绝大多数是 `PILOTSTD_API_TOKEN`、`aggregate_keys.py`、`task_id`
这类查证入口）。本文件锁定新口径：

1. 工具指令（`noqa` / `i18n-allow:` 等）整行豁免；
2. 反引号内代码、引号字符串、文件名形态不算正文；
3. 形如代码标识符的英文（含 `_` `.` `/` 括号连字符、数字，或含大写字母）放过；
4. 英文**普通词**（warning/debug/def/import/dict 等）仍必须译成中文。
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _load():
    """以文件路径加载门禁模块（scripts/ 不是包，与既有门禁测试同法）。"""
    spec = importlib.util.spec_from_file_location(
        "check_g_012_comment_density", SCRIPTS / "check_g_012_comment_density.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m = _load()


def test_plain_chinese_comment_passes():
    assert m._is_chinese_comment("# 只记警告不记调试") is True


def test_plain_english_words_are_rejected():
    """英文普通词仍要翻译——这是本规则真正要拦的东西。"""
    for line in (
        "# 只 warning 不 debug",
        "# 合并 dict 后返回",
        "# 公开 pass 分支",
        "# 调用 import 钩子",
    ):
        assert m._is_chinese_comment(line) is False, line


def test_identifier_forms_pass():
    """标识符（查证入口）不意译：这是 V-17 要修掉的 100% 误报。"""
    for line in (
        "# 写入 PILOTSTD_API_TOKEN 环境变量",
        "# 读取 task_id 字段",
        "# 实现在 aggregate_keys.py",
        "# 见 docs/governance/gates.md",
        "# 聚合键取 event_type 与 target_id",
        "# 对应 B1 裁定（2026-10-05）",
    ):
        assert m._is_chinese_comment(line) is True, line


def test_backtick_span_is_exempt():
    """行内代码整段豁免，便于写裸小写标识符（inbox/organizer 等）。"""
    assert m._is_chinese_comment("# 结果写入 `inbox` 目录") is True
    assert m._is_chinese_comment("# 由 `organizer` 统一移动") is True


def test_bare_lowercase_word_still_flagged():
    """反引号外的小写裸词按英文普通词处理（这正是需要改写的写法）。"""
    assert m._is_chinese_comment("# 结果写入 inbox 目录") is False


def test_tool_directives_are_exempt():
    for line in (
        "# noqa: E501",
        "# type: ignore[attr-defined]",
        "# i18n-allow: 内部日志",
        "# TODO(P2) 补齐超时分支",
    ):
        assert m._is_chinese_comment(line) is True, line


def test_empty_and_hash_only_comments_pass():
    assert m._is_chinese_comment("#") is True
    assert m._is_chinese_comment("#   ") is True


def test_quoted_literals_are_exempt():
    assert m._is_chinese_comment('# 形如 "value" 的占位串') is True


def test_code_identifier_detector():
    assert m._is_code_identifier("PILOTSTD_API_TOKEN") is True
    assert m._is_code_identifier("task_id") is True
    assert m._is_code_identifier("aggregate_keys.py") is True
    assert m._is_code_identifier("v0.195.5") is True
    assert m._is_code_identifier("l2_workers") is True
    assert m._is_code_identifier("warning") is False
    assert m._is_code_identifier("debug") is False
    assert m._is_code_identifier("inbox") is False
