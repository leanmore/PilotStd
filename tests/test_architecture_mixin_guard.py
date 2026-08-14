"""架构守护：除 _WindowLifecycleMixin (Qt 硬约束) 外，禁止新增 Mixin。"""

import ast
from pathlib import Path

# 动态定位项目根目录，不依赖 CWD
PILOTSTD_ROOT = Path(__file__).resolve().parent.parent / "pilotstd"

ALLOWED_MIXINS = {"_WindowLifecycleMixin"}


def test_no_new_mixins():
    """守护规则：除 Qt 硬约束外，禁止新增任何 Mixin 类定义。"""
    mixin_classes = []

    if not PILOTSTD_ROOT.exists():
        raise RuntimeError(f"未找到源码目录: {PILOTSTD_ROOT}")

    for py_file in PILOTSTD_ROOT.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue  # 跳过 Jinja2 模板等非 Python 文件
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name.endswith("Mixin"):
                if node.name not in ALLOWED_MIXINS:
                    mixin_classes.append(
                        f"  {py_file.relative_to(PILOTSTD_ROOT)}:{node.name}"
                    )

    assert not mixin_classes, (
        "发现非法 Mixin！请使用 Composition + _DispatchContext 模式替代：\n"
        + "\n".join(mixin_classes)
        + "\n\n参考架构决策：docs/adr/ADR-001-mixin-refactor-16-to-1.md"
    )
