# tests/test_settings_e2e_consistency.py
"""端到端配置字段一致性测试。

自动扫描前端 Vue 组件的 getp/setp 路径与后端 GET /api/settings 返回的字段，
确保键名完全匹配。CI 中断新增不同步问题。
"""

import ast
import os
import re
import unittest

# 项目根目录
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── 白名单：后端返回但前端无对应表单的字段（桌面端专属 / 只读 / store 管理）──
BACKEND_ONLY_WHITELIST = {
    "storage.mirror_skipped_dirs",  # 桌面端功能
    "storage.mirror_fallback",  # 桌面端功能
    "storage.scan_paths",  # 只读，TaskView 展示用
    "query.site_order",  # 桌面端功能
    "query.interval",  # 由 query_interval[0] 派生，前端用 query_interval
    "appearance.theme",  # Pinia store 管理
    "appearance.language",  # Pinia store 管理
    "appearance.hyphen_style",  # 桌面端功能
    "appearance.icon_theme",  # 桌面端功能
    "appearance.skip_welcome",  # 桌面端功能
    "appearance.column_visibility",  # 桌面端功能
}

# ── 前端扫描：从 Vue 文件提取 getp/setp 配置路径 ──


def _extract_vue_paths(vue_content: str) -> set[str]:
    """从 Vue 模板/脚本中提取配置路径。

    支持三种模式：
    - getp('path', ...) / setp('path', ...)  — 旧版手写表单
    - field-key="path"                       — DynamicSettingField 新版
    """
    paths: set[str] = set()
    for pattern in [
        r"getp\(['\"]([^'\"]+)['\"]",
        r"setp\(['\"]([^'\"]+)['\"]",
        r"""field-key=["']([^"']+)["']""",
    ]:
        for m in re.finditer(pattern, vue_content):
            paths.add(m.group(1))
    return paths


def _scan_frontend_keys() -> set[str]:
    """从前端源码 + 后端 Schema 收集所有配置路径。

    前端源码扫描：getp/setp（留存的手写字段）+ field-key（显式引用）
    后端 Schema：所有注册的配置键（DynamicSettingField 动态渲染的来源）
    """
    all_paths: set[str] = set()

    # 1. 设置 Tab 目录（留存的手写 getp/setp + 非 Schema Tab）
    settings_dir = os.path.join(ROOT, "web", "src", "views", "settings")
    if os.path.isdir(settings_dir):
        for fname in sorted(os.listdir(settings_dir)):
            if fname.endswith(".vue"):
                with open(os.path.join(settings_dir, fname), encoding="utf-8") as f:
                    all_paths.update(_extract_vue_paths(f.read()))

    # 2. 通用组件目录（SettingsTabAppearanceMixed 的手写 getp/setp）
    components_dir = os.path.join(ROOT, "web", "src", "components")
    for fname in ("SettingsTabAppearanceMixed.vue",):
        fpath = os.path.join(components_dir, fname)
        if os.path.isfile(fpath):
            with open(fpath, encoding="utf-8") as f:
                all_paths.update(_extract_vue_paths(f.read()))

    # 3. 父组件 SettingsView.vue（uploadBg → appearance.login_bg）
    sv_path = os.path.join(ROOT, "web", "src", "views", "SettingsView.vue")
    if os.path.isfile(sv_path):
        with open(sv_path, encoding="utf-8") as f:
            all_paths.update(_extract_vue_paths(f.read()))

    # 4. 后端 Schema 注册表——这是 DynamicSettingField 动态引用的权威来源
    all_paths.update(_scan_schema_keys())

    return all_paths


def _scan_schema_keys() -> set[str]:
    """从 settings_schema.py 的 SCHEMA 列表中提取所有注册键名。"""
    import ast

    schema_path = os.path.join(ROOT, "pilotstd", "core", "config", "settings_schema.py")
    if not os.path.isfile(schema_path):
        return set()

    with open(schema_path, encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source)

    keys: set[str] = set()
    for node in ast.walk(tree):
        # 查找 SettingDef(key="...", ...) 调用
        if isinstance(node, ast.Call):
            for kw in getattr(node, "keywords", []):
                if kw.arg == "key" and isinstance(kw.value, ast.Constant):
                    keys.add(kw.value.value)  # type: ignore[arg-type]
    return keys


# ── 后端扫描：解析 settings.py 的 GET 函数返回结构，提取叶节点路径 ──


def _get_backend_keys() -> set[str]:
    """解析 docker/api/settings.py 中 get_settings() 的返回 dict 结构。

    不导入模块（避免依赖链问题），直接 AST 解析源码。
    """
    docker_dir = os.path.join(ROOT, "docker", "api", "settings.py")
    with open(docker_dir, encoding="utf-8-sig") as f:
        source = f.read()

    tree = ast.parse(source)
    keys: set[str] = set()

    # 找到 get_settings 函数中的 return 语句
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name != "get_settings":
            continue
        # 找到 return 语句
        for stmt in ast.walk(node):
            if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Dict):
                _extract_keys_from_ast(stmt.value, keys, prefix="")

    # 去掉 version（非配置项）
    keys.discard("version")
    return keys


def _extract_keys_from_ast(node: ast.AST, keys: set[str], prefix: str) -> None:
    """递归遍历 AST Dict 节点，提取 'a.b.c' 格式的叶节点路径。"""
    if isinstance(node, ast.Dict):
        for key_node, value_node in zip(node.keys, node.values):
            if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                key_name = key_node.value
            else:
                continue
            full = f"{prefix}.{key_name}" if prefix else key_name
            if isinstance(value_node, ast.Dict):
                _extract_keys_from_ast(value_node, keys, full)
            else:
                keys.add(full)


# ── 测试用例 ──


class TestSettingsE2EConsistency(unittest.TestCase):
    """端到端配置字段一致性。"""

    frontend_keys: set[str]
    backend_keys: set[str]

    @classmethod
    def setUpClass(cls) -> None:
        cls.frontend_keys = _scan_frontend_keys()
        cls.backend_keys = _get_backend_keys()

    def test_no_frontend_only_keys(self) -> None:
        """前端引用的配置路径必须在后端 GET 中存在。

        如果此测试失败，说明前端表单有字段而后端未返回——数据静默丢失。
        """
        orphaned = self.frontend_keys - self.backend_keys
        self.assertEqual(
            set(),
            orphaned,
            f"前端引用了 {len(orphaned)} 个后端 GET 未返回的配置路径:\n"
            + "\n".join(f"  - {k}" for k in sorted(orphaned))
            + "\n请在 backend GET 中添加这些字段，或确认前端键名是否正确。",
        )

    def test_no_unexpected_backend_only_keys(self) -> None:
        """后端 GET 返回的字段如果前端无表单，必须在白名单中声明。

        如果此测试失败，说明后端返回了新字段但前端表单未覆盖——
        可能是新增特性未同步，或需加入白名单。
        """
        unexpected = self.backend_keys - self.frontend_keys - BACKEND_ONLY_WHITELIST
        self.assertEqual(
            set(),
            unexpected,
            f"后端 GET 返回了 {len(unexpected)} 个前端未覆盖的字段（不在白名单中）:\n"
            + "\n".join(f"  - {k}" for k in sorted(unexpected))
            + "\n请在前端添加对应表单控件，或将其加入 BACKEND_ONLY_WHITELIST。",
        )

    def test_e2e_roundtrip_coverage(self) -> None:
        """统计覆盖率：前端字段 / 后端字段。"""
        covered = self.frontend_keys & self.backend_keys
        total_fe = len(self.frontend_keys)
        total_be = len(self.backend_keys) - len(self.backend_keys & BACKEND_ONLY_WHITELIST)
        if total_be == 0:
            return
        rate = len(covered) / total_be * 100
        # 覆盖率不低于 90%
        self.assertGreaterEqual(
            rate,
            90.0,
            f"前端覆盖率 {rate:.1f}% 低于 90%，前端 {total_fe} 键 vs 后端 {total_be} 键",
        )


if __name__ == "__main__":
    unittest.main()
