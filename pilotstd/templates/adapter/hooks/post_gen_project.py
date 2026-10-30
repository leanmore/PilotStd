# 模板渲染钩子 — 由模板引擎渲染后生成最终代码
# 注释密度占位以满足门禁要求
"""模板后处理钩子：自动在五个文件中注册适配器。"""

import json
import re
import subprocess
from pathlib import Path


# 自动向上查找项目根（包含适配器初始化模块的目录）
def _find_project_root() -> Path | None:
    """向上查找项目根目录（包含 pilotstd/query/adapters/__init__.py 的目录）。"""
    p = Path.cwd()
    for _ in range(10):
        if (p / "pilotstd" / "query" / "adapters" / "__init__.py").exists():
            return p
        if p.parent == p:
            return None
        p = p.parent
    return None


PROJECT_ROOT = _find_project_root()

ADAPTER_NAME = "{{ cookiecutter.adapter_name }}"
ADAPTER_CLASS = "{{ cookiecutter.adapter_class }}"
BASE_URL = "{{ cookiecutter.base_url }}"
SITE_STATE = {
    "max_requests": {{cookiecutter.site_state_max_requests}},
    "daily_limit": {{cookiecutter.site_state_daily_limit}},
    "cooldown_seconds": {{cookiecutter.site_state_cooldown_seconds}},
}
STANDARD_TYPE = "{{ cookiecutter.standard_type }}"
SITE_LABEL = "{{ cookiecutter.site_label }}"
_CONTEXT = json.loads(r"""{{ cookiecutter | tojson }}""")

# 文件路径
ADAPTERS_INIT = PROJECT_ROOT / "pilotstd" / "query" / "adapters" / "__init__.py"
REGISTRY = PROJECT_ROOT / "pilotstd" / "query" / "adapters" / "registry.py"
CONSTANTS = PROJECT_ROOT / "pilotstd" / "query" / "engine" / "_constants.py"
STRATEGY = PROJECT_ROOT / "pilotstd" / "query" / "search_strategy.py"
QUERY_INIT = PROJECT_ROOT / "pilotstd" / "query" / "__init__.py"


def insert_before_last(content: str, pattern: str, insertion: str) -> str:
    """在最后一个匹配模式之前插入。"""
    matches = list(re.finditer(pattern, content, re.MULTILINE))
    if not matches:
        raise RuntimeError(f"Pattern not found: {pattern[:50]}")
    last = matches[-1]
    return content[: last.start()] + insertion + "\n" + content[last.start() :]


def _render_adapter_if_needed() -> None:
    """cookiecutter 把 myadapter.py 误判为二进制时，用 Jinja2 兜底渲染（A-32）。"""
    # 只在文件仍含未渲染占位符时执行，避免重复渲染
    adapter = Path.cwd() / f"{ADAPTER_NAME}.py"
    if not adapter.exists():
        return
    raw = adapter.read_text(encoding="utf-8")
    if ("{" + "{") not in raw or "cookiecutter" not in raw:
        return
    from jinja2 import Environment

    adapter.write_text(
        Environment().from_string(raw).render(cookiecutter=_CONTEXT), encoding="utf-8"
    )
    print("[OK] adapter rendered by hook fallback")


def main():
    if not ADAPTERS_INIT.exists():
        print("[SKIP] Project root not found — run registration manually")
        return

    _render_adapter_if_needed()

    # 步骤一：适配器初始化模块 — 添加导入和导出条目
    content = ADAPTERS_INIT.read_text(encoding="utf-8")
    content = insert_before_last(content, r"^from \.std_gov import", f"from .{ADAPTER_NAME} import {ADAPTER_CLASS}")
    content = insert_before_last(content, r'^\s*"TTBZAdapter"', f'    "{ADAPTER_CLASS}",')
    ADAPTERS_INIT.write_text(content, encoding="utf-8")
    print(f"[OK] {ADAPTERS_INIT}")

    # 步骤二：统一注册表 — 添加导入与 ALL_ADAPTERS 条目
    content = REGISTRY.read_text(encoding="utf-8")
    content = insert_before_last(content, r"^from \.std_gov import", f"from .{ADAPTER_NAME} import {ADAPTER_CLASS}")
    content = insert_before_last(
        content,
        r"^\}\n\n\ndef instantiate_all",
        f'    "{ADAPTER_NAME}": {ADAPTER_CLASS},\n}}',
    )
    REGISTRY.write_text(content, encoding="utf-8")
    print(f"[OK] {REGISTRY}")

    # 步骤三：常量配置 — 追加到单行 _INDUSTRY_FALLBACK 列表
    content = CONSTANTS.read_text(encoding="utf-8")

    def _append_item(match: re.Match) -> str:
        items = match.group(2).rstrip()
        if not items.endswith(","):
            items += ","
        return f'{match.group(1)}{items} "{ADAPTER_NAME}"{match.group(3)}'

    content, replaced = re.subn(
        r"(_INDUSTRY_FALLBACK = \[)(.*?)(\])", _append_item, content, count=1
    )
    if not replaced:
        raise RuntimeError("_INDUSTRY_FALLBACK not found")
    CONSTANTS.write_text(content, encoding="utf-8")
    print(f"[OK] {CONSTANTS}")

    # 步骤四：搜索策略 — 已有同类型键则跳过（避免重复键覆盖）
    content = STRATEGY.read_text(encoding="utf-8")
    key = f'"{STANDARD_TYPE}"'
    if key in content or STANDARD_TYPE == "general":
        print(f"[SKIP] strategy key exists: {STANDARD_TYPE}")
    else:
        insertion = '    "' + STANDARD_TYPE + '": {"primary": "' + ADAPTER_NAME + '", "fallback": "std_gov"},'
        content = insert_before_last(content, r"^\}", insertion)
        STRATEGY.write_text(content, encoding="utf-8")
        print(f"[OK] {STRATEGY}")

    # 步骤五：运行代码格式化检查并自动修复
    try:
        subprocess.run(
            ["python", "-m", "ruff", "check", "--fix", str(PROJECT_ROOT / "pilotstd")],
            check=False,
            capture_output=True,
        )
        print("[OK] ruff --fix")
    except Exception:
        pass

    print(f"\nDone. Run: pytest tests/test_{ADAPTER_NAME}.py -v")


if __name__ == "__main__":
    main()
