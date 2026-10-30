"""A-31：模板 hook 的锚点回归（不跑 cookiecutter，只锁关键实现）。"""

from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "pilotstd" / "templates" / "adapter" / "hooks" / "post_gen_project.py"


def test_hook_targets_registry_and_renders_fallback():
    text = HOOK.read_text(encoding="utf-8")
    assert "registry.py" in text
    assert "_render_adapter_if_needed" in text
    assert "Environment().from_string(raw)" in text


def test_hook_drops_dead_lazy_getter():
    text = HOOK.read_text(encoding="utf-8")
    assert "def _get_{ADAPTER_NAME}_adapter" not in text
