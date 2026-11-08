# tests/test_scripts_fail_loud.py — U34 E-fix-scripts 批 1：读不到/可选依赖失败必须留痕
"""锁定 6 处「读文件失败 → 安全值」与 1 处「可选依赖失败 → 空集合」的修复。

覆盖：
- `_sql_schema_parser`、`check_i18n_hardcoded_python` 读失败 → `[WARN]` + 仍返回安全值；
- `check_docs_drift` 可选依赖 import 失败 → `[WARN]` + 仍返回 facts。

批 2（git 失败 exit 2 / continue / G-013 内容区分）见 `test_scripts_fail_loud_batch2.py`。
"""

import builtins
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def _load(name: str, filename: str):
    """以文件路径加载脚本模块（scripts/ 不是包）。"""
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_sql_schema_parser_warns_on_read_failure(capsys) -> None:
    """读不到文件时返回 []，但 stderr 必须有 [WARN]（否则 schema 门禁静默漏文件）。"""
    mod = _load("_sql_schema_parser_t", "_sql_schema_parser.py")
    result = mod._find_sql_strings(Path("no_such_file_xyz.py"))
    assert result == []
    err = capsys.readouterr().err
    assert "[WARN]" in err and "no_such_file_xyz.py" in err


def test_i18n_python_warns_on_read_failure(capsys) -> None:
    """i18n 门禁读不到文件 → [] + [WARN]。"""
    mod = _load("check_i18n_hardcoded_python_t", "check_i18n_hardcoded_python.py")
    result = mod.find_hardcoded(Path("no_such_file_xyz.py"))
    assert result == []
    assert "[WARN]" in capsys.readouterr().err


def test_docs_drift_warns_when_optional_import_fails(monkeypatch, capsys) -> None:
    """配置键来源 import 失败 → 仍返回 facts，但必须有 [WARN]。"""
    mod = _load("check_docs_drift_t", "check_docs_drift.py")
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "pilotstd.core.config.scope":
            raise ImportError("simulated missing dependency")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    facts = mod.load_facts()
    assert isinstance(facts, dict)
    assert "[WARN]" in capsys.readouterr().err
