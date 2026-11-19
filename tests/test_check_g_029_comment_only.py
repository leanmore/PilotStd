"""tests/test_check_g_029_comment_only.py — G-029 的「仅注释变更」识别（2026-11-19）。

背景：G-029 要求 UI 模块变更必须同步 GUI 测试。但**纯注释/docstring 变更**不改变代码语义，
不应强制补测试（否则只能产物化一份无意义测试）。判定用 AST 归一化（docstring 文本换占位符）
比对基线：注释不进 AST，故两侧 dump 相同即“只改注释”。

安全默认：基线取不到（新增文件/git 不可用/读失败）或任一侧语法错误 → 一律按真变更处理。
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SCRIPT = SCRIPTS / "check_g_029_test_coverage.py"


def _load():
    """以文件路径加载门禁模块（scripts/ 不是包，与既有门禁测试同法）。"""
    spec = importlib.util.spec_from_file_location("check_g_029_test_coverage", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m = _load()


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=str(repo), check=True, capture_output=True, text=True
    )


@pytest.fixture()
def repo(tmp_path):
    """两个提交的临时仓库：第一次提交基线，第二次由用例决定改什么。"""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    return tmp_path


def _commit(repo: Path, name: str, content: str) -> None:
    (repo / name).write_text(content, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-qm", "c")


BASE = '''"""基线文档字符串。"""


def f():
    """函数文档。"""
    return 1
'''


def test_comment_only_change_is_detected(repo):
    _commit(repo, "a.py", BASE)
    changed = BASE.replace('"""基线文档字符串。"""', '"""基线文档字符串（改）。"""')
    _commit(repo, "a.py", changed + "\n# 新增一行注释\n")
    assert m.is_comment_only("a.py", "HEAD~1..HEAD", root=repo) is True


def test_code_change_is_not_comment_only(repo):
    _commit(repo, "a.py", BASE)
    _commit(repo, "a.py", BASE.replace("return 1", "return 2"))
    assert m.is_comment_only("a.py", "HEAD~1..HEAD", root=repo) is False


def test_new_file_is_treated_as_real_change(repo):
    _commit(repo, "a.py", BASE)
    _commit(repo, "b.py", "x = 1\n")
    assert m.is_comment_only("b.py", "HEAD~1..HEAD", root=repo) is False


def test_missing_base_ref_is_treated_as_real_change(repo):
    _commit(repo, "a.py", BASE)
    assert m.is_comment_only("a.py", "..HEAD", root=repo) is False


def test_normalized_ast_ignores_docstring_text_but_not_code():
    a = m._normalized_ast('def f():\n    """甲。"""\n    return 1\n')
    b = m._normalized_ast('def f():\n    """乙。"""\n    return 1\n')
    c = m._normalized_ast('def f():\n    """甲。"""\n    return 2\n')
    assert a == b
    assert a != c
    assert m._normalized_ast("def f(:\n") is None
