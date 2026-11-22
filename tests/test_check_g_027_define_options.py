"""tests/test_check_g_027_define_options.py — G-027 的 `<script setup>` 识别（2026-11-22）。

背景：G-027 要求 `<script setup>` 形式的 Vue 组件显式声明 `defineOptions({ name })`，
防止生产构建压缩器删掉组件名（影响 devtools / keep-alive / 递归自引用）。

原实现用 `"<script setup" not in content` 做判断，**注释里出现该字样也会命中**：
`FileMonitor.vue` 是全仓唯一的 Options API SFC，头部注释提到「其余都是 `<script setup>`」，
于是被误判为 setup 形式，进而因缺少 defineOptions 而报红（假阳性）。

修复：正则只匹配行首的 `<script setup ...>` 标签（允许前置空白），注释内字样不参与判定。

本测试锁住两条：
  1. 注释里提到 `<script setup>` 的 Options API 组件 → 不检查（不误报）；
  2. 真实的 `<script setup>` 组件缺 defineOptions → 仍然报错（不放过真问题）。
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SCRIPT = SCRIPTS / "check_g_027_define_options.py"


def _load():
    """以文件路径加载门禁模块（scripts/ 不是包，与既有门禁测试同法）。"""
    spec = importlib.util.spec_from_file_location("check_g_027_define_options", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m = _load()


def _write(repo: Path, name: str, content: str) -> None:
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_comment_mentioning_script_setup_is_not_checked(tmp_path, monkeypatch):
    """注释里提到 `<script setup>` 的 Options API 组件不应被要求 defineOptions。"""
    _write(
        tmp_path,
        "web/src/components/OptionsApi.vue",
        """<!--
  说明：本仓其余组件都是 <script setup> 写法，本文件是唯一的 Options API 例外。
-->
<script lang="ts">
import { defineComponent } from 'vue'
export default defineComponent({ name: 'OptionsApi' })
</script>
<template><div /></template>
""",
    )
    monkeypatch.setattr(m, "ROOT", tmp_path)
    assert m.main() == 0


def test_real_script_setup_without_define_options_fails(tmp_path, monkeypatch):
    """真实的 `<script setup>` 组件缺 defineOptions 仍须报红（不放过真问题）。"""
    _write(
        tmp_path,
        "web/src/components/NoName.vue",
        """<script setup lang="ts">
const a = 1
</script>
<template><div>{{ a }}</div></template>
""",
    )
    monkeypatch.setattr(m, "ROOT", tmp_path)
    assert m.main() == 1


def test_real_script_setup_with_define_options_passes(tmp_path, monkeypatch):
    """合规的 `<script setup>` 组件（有 defineOptions）通过。"""
    _write(
        tmp_path,
        "web/src/components/Good.vue",
        """<script setup lang="ts">
defineOptions({ name: 'Good' })
</script>
<template><div /></template>
""",
    )
    monkeypatch.setattr(m, "ROOT", tmp_path)
    assert m.main() == 0
