# tests/test_adapter_post_gen_hook.py
"""post_gen_project 钩子的最小回归：在「假项目根」里跑一遍，断言五处注册都落盘。

背景（台账 L381）：真实 cookiecutter CLI 路径未纳入 CI，模板本体已由
`tests/unit/test_adapter_template_generation.py` 覆盖；本文件补钩子这一段。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from jinja2 import Environment, StrictUndefined

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / "pilotstd" / "templates" / "adapter" / "hooks" / "post_gen_project.py"
ADAPTER = "myadapter"
CLASS = "MyAdapter"


def _ctx() -> dict:
    """cookiecutter 上下文（固定为测试适配器，避免依赖交互输入）。"""
    data = json.loads((REPO / "pilotstd" / "templates" / "adapter" / "cookiecutter.json").read_text(encoding="utf-8"))
    data.pop("__prompts__", None)
    data.update(adapter_name=ADAPTER, adapter_class=CLASS)
    return data


def _rendered_hook() -> str:
    template = HOOK.read_text(encoding="utf-8")
    return Environment(undefined=StrictUndefined).from_string(template).render(cookiecutter=_ctx())


def _fake_root(tmp_path: Path) -> Path:
    """造一个含五处锚点的假项目根（钩子按这些锚点插入注册代码）。"""
    files = {
        "pilotstd/query/adapters/__init__.py": (
            'from .std_gov import StdGovAdapter\n\n__all__ = [\n    "TTBZAdapter",\n]\n'
        ),
        "pilotstd/query/site_config.py": "SITES = [\n]\n",
        "pilotstd/query/engine/_constants.py": 'ORDER = ("csres",)\n',
        "pilotstd/query/search_strategy.py": "ROUTES = {\n}\n",
        "pilotstd/query/__init__.py": "def _get_ttbz_adapter() -> Type[Any]:\n    return TTBZAdapter\n",
    }
    for rel, body in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return tmp_path


def test_hook_renders_without_leftover_placeholder():
    """钩子必须是完整可渲染的 Python（残留 `{{ … }}` 会静默写进生成物）。"""
    rendered = _rendered_hook()
    assert "{{" not in rendered and "{%" not in rendered
    compile(rendered, str(HOOK), "exec")


def test_hook_registers_adapter_in_five_files(tmp_path: Path):
    """跑一遍钩子：五个文件都应出现注册痕迹，且不得残留未渲染占位符。"""
    root = _fake_root(tmp_path)
    script = root / "_hook_rendered.py"
    script.write_text(_rendered_hook(), encoding="utf-8")

    proc = subprocess.run([sys.executable, str(script)], cwd=root, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr

    checks = {
        "pilotstd/query/adapters/__init__.py": [f"from .{ADAPTER} import {CLASS}", f'"{CLASS}",'],
        "pilotstd/query/site_config.py": [f'S(name="{ADAPTER}"'],
        "pilotstd/query/engine/_constants.py": [f'"{ADAPTER}",'],
        "pilotstd/query/search_strategy.py": [f'"primary": "{ADAPTER}"'],
        "pilotstd/query/__init__.py": [f"def _get_{ADAPTER}_adapter"],
    }
    for rel, needles in checks.items():
        text = (root / rel).read_text(encoding="utf-8")
        for needle in needles:
            assert needle in text, f"{rel} 缺少 {needle!r}"
        assert "cookiecutter" not in text, f"{rel} 残留未渲染占位符"
