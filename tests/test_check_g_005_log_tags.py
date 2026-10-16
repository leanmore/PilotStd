"""tests/test_check_g_005_log_tags.py — G-005 日志标签门禁的受控测试。

覆盖两处自身缺陷修复（2026-10-16）：
1. **模板子树排除**：`pilotstd/templates/**`（cookiecutter 模板，含 Jinja 占位符）整棵排除，
   与 `pyproject.toml` 的 `extend-exclude = ["whitelist.py", "pilotstd/templates/**"]` 同口径；
2. **SyntaxError 兜底**：无法解析的文件作为**该文件的违规项**上报（而不是崩掉整个门禁）。

另含门禁基本语义（干净文件通过 / 裸 `print()` 判违规）与真实树整体退出码。
"""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check_g_005_log_tags.py"


def _load_module():
    """以文件路径加载门禁脚本模块（scripts/ 不是包）。"""
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("check_g_005_log_tags", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gate():
    """加载后的门禁模块。"""
    return _load_module()


def test_templates_subtree_is_excluded(gate) -> None:
    """模板目录下的 .py（Jinja 占位符）必须整体排除出检查清单。"""
    templates_dir = gate.SRC_DIR / "templates"
    # 前置断言：模板目录里确实有 .py——否则"排除成功"是空集假绿
    raw = sorted(templates_dir.rglob("*.py"))
    assert raw, f"夹具失效：{templates_dir} 下没有 .py 文件"

    files = gate._find_py_files(gate.SRC_DIR)
    assert files, "检查清单不应为空"
    assert not [f for f in files if f.is_relative_to(templates_dir)], (
        f"pilotstd/templates/ 未被排除：{[str(f) for f in files if f.is_relative_to(templates_dir)]}"
    )


def test_exclusion_matches_pyproject_extend_exclude(gate) -> None:
    """排除口径与 pyproject.toml 的 ruff `extend-exclude` 同源（防两处漂移）。"""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'extend-exclude = ["whitelist.py", "pilotstd/templates/**"]' in pyproject
    assert gate.EXCLUDED_PATH_PREFIXES == (gate.SRC_DIR / "templates",)


def test_template_file_would_be_syntax_error(gate) -> None:
    """证明排除是**必要**的：模板文件直接解析必然 SyntaxError。"""
    template = (
        gate.SRC_DIR
        / "templates"
        / "adapter"
        / "{{ cookiecutter.adapter_name }}"
        / "{{ cookiecutter.adapter_name }}.py"
    )
    if not template.exists():  # 模板结构变更时跳过而非误报
        pytest.skip("模板夹具结构已变，跳过")
    source = template.read_text(encoding="utf-8")
    with pytest.raises(SyntaxError):
        gate.ast.parse(source)


def test_syntax_error_is_reported_not_raised(gate, tmp_path: Path) -> None:
    """无法解析的文件 ⇒ 返回该文件的违规项，不抛异常（门禁不崩）。"""
    bad = tmp_path / "bad_jinja.py"
    bad.write_text("class Test{{ cookiecutter.adapter_class }}:\n    pass\n", encoding="utf-8")
    errors = gate.check_file(bad)
    assert len(errors) == 1, errors
    assert "无法解析" in errors[0]
    assert "SyntaxError" in errors[0]
    assert "bad_jinja.py" in errors[0]


def test_clean_file_passes(gate, tmp_path: Path) -> None:
    """普通文件（logging.getLogger）无违规。"""
    good = tmp_path / "good.py"
    good.write_text("import logging\n\nlogger = logging.getLogger(__name__)\n", encoding="utf-8")
    assert gate.check_file(good) == []


def test_bare_print_is_flagged(gate, tmp_path: Path) -> None:
    """裸 print() 判违规（门禁基本语义未变）。"""
    bad = tmp_path / "printer.py"
    bad.write_text("def f():\n    print('x')\n", encoding="utf-8")
    errors = gate.check_file(bad)
    assert len(errors) == 1, errors
    assert "禁止使用 print()" in errors[0]


def test_main_returns_zero_when_tree_is_clean(gate, monkeypatch, tmp_path: Path, capsys) -> None:
    """受控树整体退出码 = 0（用临时根替换 SRC_DIR，不依赖真实树的既有违规）。"""
    (tmp_path / "clean.py").write_text("import logging\n\nlogger = logging.getLogger(__name__)\n", encoding="utf-8")
    monkeypatch.setattr(gate, "SRC_DIR", tmp_path)
    assert gate.main() == 0
    out = capsys.readouterr().out
    assert "[G-005] PASS" in out
    assert "pilotstd/templates/ 已排除" in out


def test_main_reports_unparsable_file_without_crashing(gate, monkeypatch, tmp_path: Path, capsys) -> None:
    """受控树含 Jinja 式坏文件 ⇒ FAIL(1)，且**指出问题文件**（不再抛 traceback）。"""
    (tmp_path / "bad_jinja.py").write_text("class X{{ cookiecutter.x }}:\n    pass\n", encoding="utf-8")
    monkeypatch.setattr(gate, "SRC_DIR", tmp_path)
    assert gate.main() == 1
    out = capsys.readouterr().out
    assert "bad_jinja.py" in out
    assert "无法解析" in out


# ── 2026-10-16：ui.md 记载的"有意保留 stderr 输出"豁免（③） ──


def test_exceptions_are_named_files_and_exist(gate) -> None:
    """豁免必须是"具名文件 + 真实存在"——防止退化成按目录整体放行。

    依据 `docs/architecture/modules/ui.md`「日志与诊断」节：这两处在 2026-09-26 清理调试输出时
    **特意保留**（Qt 消息唯一出口，文档记"改成 logging 有重入风险"；自检工具按设计输出 stderr）。
    """
    expected = {
        gate.SRC_DIR / "ui" / "core" / "_self_check.py",
        gate.SRC_DIR / "ui" / "main_window" / "parts" / "_run_main.py",
    }
    assert gate.EXCLUDED_ALLOWED_STDERR == expected, "豁免清单被改动：须同步 ui.md 该节并说明理由"
    for path in expected:
        assert path.exists(), f"豁免路径已不存在（应同步删除豁免）：{path}"


def test_exception_is_file_scoped_not_directory_scoped(gate, tmp_path: Path) -> None:
    """同名/同目录的**其它**文件出现 `print(stderr)` 仍判违规——豁免不按目录放行。"""
    other = tmp_path / "_self_check.py"  # 与被豁免文件同名，但不同路径
    other.write_text("import sys\n\n\ndef f():\n    print('x', file=sys.stderr)\n", encoding="utf-8")
    errors = gate.check_file(other)
    assert len(errors) == 1, errors
    assert "禁止使用 print()" in errors[0]

    # 被豁免的那份真实文件：确有 print(stderr)，但不再判违规
    excused = gate.SRC_DIR / "ui" / "core" / "_self_check.py"
    assert "print(" in excused.read_text(encoding="utf-8"), "夹具失效：该文件应仍保留 print"
    assert gate.check_file(excused) == []


def test_allow_print_does_not_disable_log_rule(gate) -> None:
    """豁免只关掉 print 规则：被豁免文件里的模块级 `_log()` 仍必须被拦。"""
    tree = gate.ast.parse("def _log():\n    pass\n")
    ok, msg = gate._is_logger_import_ok(tree, allow_print=True)
    assert not ok, "allow_print 不应连带关掉 _log() 规则"
    assert "模块级 _log()" in msg
