#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""G-043 敏感端点审计接线门禁。

背景（第 2 批安全审计闭环，docs/plans/batch2-security-audit-design.md）：
全库仅 4 处 `write_audit`，而使用 `@require_role` 的端点有 61 处；凭证变更、
改密、令牌轮换、用户增删等敏感操作「放行不写审计」无任何门禁拦截。

判定规则（**函数级 AST 判定**，L-01 升级后）：
- 以 AST 关联 `@router.<method>("/path")` 装饰器与**其所装饰的函数**；
- 敏感路由（`SENSITIVE_ROUTES`）→ 要求**该函数自身**可达 `write_audit`
  （直接调用，或调用 `AUDIT_WRAPPERS` 中登记的审计封装函数）；
- 其余状态变更路由必须在 `EXEMPT_ROUTES` 中**显式登记**（每条带理由）。

为何需要 `AUDIT_WRAPPERS` 注册表（而非"函数体内找 write_audit"）：
实测 4 个敏感端点中 3 个的审计经**同模块辅助函数**实现——`update_config()` →
`_persist_config_and_audit()`、`api_change_password()` → `_audit_password_change()`、
`login()` → `_notify_login_failure()`。只看函数体必然对这 3 处产生**假 FAIL**；
而"展开同模块全部辅助函数"又会因 `trigger_cleanup()` → `get_stats()` 这类**非审计**
调用产生**假 PASS**。故采用**显式注册表**：精确、可自校验。

**本方案是折中，不是消除依赖**：G-043 的人工维护数据由「2 张路由表」变为
「2 张路由表 + 1 张审计封装注册表」。注册表规模应受控（当前 3 条，超过 6 条时
应重新评估是否转为完整调用图分析）。

已知局限（有意保留、避免过度实现）：
- 只做 **L1（函数可达 `write_audit`）**，不做 L2（每个出口均有审计）。
  L2 为**接线约定**，见 docs/governance/notification_coverage.md；"产生状态变更的出口"
  无法纯静态判定（需理解语义），故不进门禁。出口覆盖由测试断言承担。
- 静态判定不区分可达性：`if False: write_audit(...)` 也会被判为已接线。

用法：
  python scripts/check_sensitive_endpoint_audit.py            # 门禁（CI）
  python scripts/check_sensitive_endpoint_audit.py --list     # 列出敏感路由与接线状态
  python scripts/check_sensitive_endpoint_audit.py --compare  # 同跑函数级与模块级并打印差异
退出码：0 = 通过；1 = 存在未接线的敏感端点。
"""

from __future__ import annotations

import ast
import io
import sys
from pathlib import Path

from _gate_coverage_summary import print_coverage_summary

# Windows 控制台默认编码无法输出中文
if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# 扫描目录：docker/api/ 为主；docker/auth.py（登录/登出路由）不在该目录下，
# 第 8 批补入 docker/ 根目录的 auth.py 以覆盖 POST /api/login。
API_DIRS = (PROJECT_ROOT / "docker" / "api",)
AUTH_MODULE = PROJECT_ROOT / "docker" / "auth.py"
API_DIR = API_DIRS[0]  # 兼容既有引用

# 敏感端点判定标准（S1 凭证生命周期 / S2 权限与身份边界 / S3 不可逆批量销毁）
SENSITIVE_ROUTES: dict[str, str] = {
    "PUT /api/notification/config": "S1 通知渠道凭证变更（含先通知旧渠道的顺序要求）",
    "PUT /api/users/password": "S1 账号密码变更（自助）",
    "POST /api/settings/token/refresh": "S1 静态 API 令牌轮换",
    # 第 8 批纳入：登录失败是暴力破解的唯一可观测信号。该路由定义在 docker/auth.py
    # （不在 docker/api/ 下），故同时扩展了扫描目录——否则本清单会"静默失效"
    # （路由查不到 → 门禁报"清单过期"）。
    "POST /api/login": "S1 认证凭证校验失败（阈值告警 + LOGIN_FAILED 审计）",
}

# 显式登记的待接入清单：每条必须带理由。禁止无理由豁免（P-104 门禁不绕过）。
#
# L-01 接线完成后**已清空**：原 6 项 P1/P2 端点（用户增删/自助注册/日志批删/缓存清理/
# 手动备份）均已接入审计，`POST /query` 因函数体内直接有 write_audit 一并移出。
# 故当前**无任何豁免**——新增状态变更敏感端点必须接线，不得豁免。
EXEMPT_ROUTES: dict[str, str] = {}

# 审计封装注册表：函数名 → 说明。每条 = 一个"内部（直接）调用 write_audit"的辅助函数。
#
# 维护规则（双向约束）：
#   1. 声明了就必须真的调用 write_audit —— 由 validate_wrappers() 机检，
#      防"封装被改写后审计消失"（本方案唯一的自维护风险点）。
#   2. 不声明就不认可 —— 故不会因"同模块任意辅助函数"产生假 PASS。
AUDIT_WRAPPERS: dict[str, str] = {
    "write_audit": "pilotstd/core/audit.py:26 — 审计写入本体",
    "_persist_config_and_audit": "docker/api/notification.py — 凭证变更落库 + 审计",
    "_audit_password_change": "docker/api/users.py — 改密审计（成功/失败共用）",
    "_notify_login_failure": "docker/auth.py — 登录失败告警 + LOGIN_FAILED 审计",
    "_audit_and_respond": "docker/api/admin_db.py — 查询审计 + 统一响应",
    # L-01 接线新增：用户增删的审计封装（add_user / delete_user 的 1 成功 + 7 失败出口共用）
    "_audit_user_management": "docker/api/users.py — 用户增删审计（成功/失败共用）",
    # L-01 接线新增：自助注册审计（register 的 1 成功 + 6 失败出口共用；未认证路径，
    # 显式传 user_id，成功时为新建用户 id、失败为 None）
    "_audit_registration": "docker/api/auth_register.py — 自助注册审计（成功/失败共用）",
    # L-01 接线新增：日志批删审计（clear_logs 的 3 成功 + 1 失败出口共用）
    "_audit_log_purge": "docker/api/logs.py — 日志批删审计（成功/失败共用）",
}

# 状态变更路由的 HTTP 方法（AST 装饰器属性）
_STATE_CHANGE_METHODS = frozenset({"post", "put", "delete", "patch"})

# AST 缓存：同一文件在"路由扫描"与"注册表校验"两处都会被读取
_AST_CACHE: dict[Path, ast.Module | None] = {}


def load_ast(path: Path) -> ast.Module | None:
    """读取并解析文件为 AST（带缓存）。语法错误返回 None（不阻断，交由调用方跳过）。"""
    if path not in _AST_CACHE:
        try:
            _AST_CACHE[path] = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            _AST_CACHE[path] = None
    return _AST_CACHE[path]


def route_key_of(decorator: ast.expr) -> str | None:
    """从 `@router.post("/x")` 形态的装饰器提取路由键 'POST /x'；非路由装饰器返回 None。"""
    if not isinstance(decorator, ast.Call):
        return None
    func = decorator.func
    if not isinstance(func, ast.Attribute) or func.attr.lower() not in _STATE_CHANGE_METHODS:
        return None
    if not decorator.args:
        return None
    first = decorator.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return "{} {}".format(func.attr.upper(), first.value)
    return None


def scan_module_routes(path: Path) -> dict[str, tuple[int, ast.FunctionDef]]:
    """返回 {路由键: (装饰器行号, 被装饰函数节点)}。

    用 AST 而非逐行正则：正则无法把装饰器与**函数体**关联，而函数级判定必须拿到函数节点。
    """
    tree = load_ast(path)
    if tree is None:
        return {}
    found: dict[str, tuple[int, ast.FunctionDef]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            key = route_key_of(decorator)
            if key is not None:
                found.setdefault(key, (node.lineno, node))
    return found


def func_reaches_audit(node: ast.FunctionDef) -> bool:
    """函数（含嵌套作用域）内是否调用 `write_audit` 或已登记的审计封装。

    覆盖三种形态（均经实测确认存在）：
      1. 直接调用 write_audit()            —— settings.py 的 refresh_token()
      2. 调用注册的审计封装                 —— notification.py 的 _persist_config_and_audit()
      3. 函数内局部 import 后调用           —— auth.py 的 _notify_login_failure()
    用 ast.walk 覆盖 if/try 等嵌套分支，故"分支内审计"也能识别。
    """
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
            if name in AUDIT_WRAPPERS:
                return True
    return False


def module_has_write_audit(path: Path) -> bool:
    """模块内是否存在 write_audit 调用（**模块级**判定，仅供 --compare 对照）。

    用于打印迁移期差异：模块级通过但函数级失败 = 该端点靠同文件其它端点"连带通过"。
    """
    tree = load_ast(path)
    if tree is None:
        return False
    for child in ast.walk(tree):
        if isinstance(child, ast.Call):
            func = child.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
            if name == "write_audit":
                return True
    return False


def validate_wrappers() -> list[str]:
    """注册表自体校验：每条 `AUDIT_WRAPPERS` 必须真的（直接）调用 `write_audit`。

    防"审计封装被改写后审计消失而门禁仍报通过"——这是本方案唯一的自维护风险点。
    只做**直接**调用检查（不递归），避免环导致无限展开。
    """
    problems: list[str] = []
    for name, desc in sorted(AUDIT_WRAPPERS.items()):
        if name == "write_audit":  # 本体，无需自证
            continue
        found = False
        for path in _scan_targets():
            tree = load_ast(path)
            if tree is None:
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
                    for child in ast.walk(node):
                        if isinstance(child, ast.Call):
                            func = child.func
                            cname = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
                            if cname == "write_audit":
                                found = True
                                break
                if found:
                    break
        if not found:
            problems.append("审计封装 {} 未（直接）调用 write_audit — 注册表已漂移（{}）".format(name, desc))
    return problems


def _scan_targets() -> list[Path]:
    """全部扫描目标文件（docker/api/**/*.py + docker/auth.py）。"""
    targets = [p for d in API_DIRS if d.is_dir() for p in sorted(d.rglob("*.py"))]
    if AUTH_MODULE.exists():
        targets.append(AUTH_MODULE)
    return [p for p in targets if p.name != "__init__.py"]


def collect_routes() -> tuple[dict[str, tuple[str, int, ast.FunctionDef, bool]], dict[str, bool]]:
    """扫描全部目标文件。

    返回 (routes, module_level)，其中：
      routes[路由键] = (相对路径, 行号, 函数节点, 该函数是否可达 write_audit)
      module_level[相对路径] = 该模块内是否存在 write_audit（模块级判定，供 --compare）
    """
    routes: dict[str, tuple[str, int, ast.FunctionDef, bool]] = {}
    module_level: dict[str, bool] = {}
    for path in _scan_targets():
        rel = str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
        found = scan_module_routes(path)
        if found:
            module_level[rel] = module_has_write_audit(path)
        for key, (lineno, node) in found.items():
            routes.setdefault(key, (rel, lineno, node, func_reaches_audit(node)))
    return routes, module_level


def print_coverage(scan_targets: list[Path], routes: dict[str, tuple[str, int, ast.FunctionDef, bool]]) -> None:
    """打印 G-043 覆盖摘要（L-23）。

    独立成函数：`main()` 须守住 G-010 的逻辑行上限。数据取自既有清单与扫描结果，
    不新增收集逻辑。
    """
    scope = "、".join(
        str(d.relative_to(PROJECT_ROOT)).replace("\\", "/") + "/**/*.py" for d in API_DIRS if d.is_dir()
    )
    if AUTH_MODULE.exists():
        scope += "、" + str(AUTH_MODULE.relative_to(PROJECT_ROOT)).replace("\\", "/")
    print_coverage_summary(
        scope="{}（AST 扫描 @router 装饰器；实扫 {} 个文件）".format(scope, len(scan_targets)),
        checked=len(SENSITIVE_ROUTES) + len(EXEMPT_ROUTES),
        passed=len(SENSITIVE_ROUTES),
        blocked=0,
        exempted=len(EXEMPT_ROUTES),
        exemptions=["{} — {}".format(route, reason) for route, reason in sorted(EXEMPT_ROUTES.items())],
        notes=(
            "需函数可达 write_audit 的路由 -> {} 项（SENSITIVE_ROUTES）".format(len(SENSITIVE_ROUTES)),
            "显式豁免的路由 -> {} 项（EXEMPT_ROUTES，逐条见下）".format(len(EXEMPT_ROUTES)),
            "审计封装注册表 -> {} 条（AUDIT_WRAPPERS，已验证各自直接调用 write_audit）".format(
                len(AUDIT_WRAPPERS)
            ),
        ),
        uncovered=(
            "判定为**函数级 L1（函数可达 write_audit）**：不做 L2 出口覆盖——"
            "『产生状态变更的出口』无法纯静态判定（需理解语义），故 L2 为**接线约定**"
            "（见 docs/governance/notification_coverage.md），由测试断言承担而非门禁。"
            "静态判定不区分可达性（if False: write_audit(...) 亦判为已接线）。"
            "上述 {} 项豁免端点仍未接入审计".format(len(EXEMPT_ROUTES))
        ),
    )


def print_compare(routes: dict[str, tuple[str, int, ast.FunctionDef, bool]], module_level: dict[str, bool]) -> None:
    """打印函数级与模块级判定的差异（迁移期诊断，不改变退出码）。

    差异归因（详见方案）：
      - 模块级通过 / 函数级失败，且函数调用了未注册辅助函数 → **判定更严格**，补注册表
      - 模块级通过 / 函数级失败，且函数无任何 write_audit 路径 → **真遗漏**，补审计
      - 模块级失败 / 函数级通过 → 不应出现（函数级更严），判定实现有误
    """
    print()
    print("[函数级 vs 模块级 判定差异]（诊断用，不影响退出码）")
    diffs = 0
    for route, reason in sorted(SENSITIVE_ROUTES.items()):
        entry = routes.get(route)
        if entry is None:
            continue
        rel, lineno, _node, func_ok = entry
        module_ok = module_level.get(rel, False)
        if module_ok != func_ok:
            diffs += 1
            kind = "判定更严格/真遗漏" if (module_ok and not func_ok) else "判定实现可疑"
            print(
                "  [差异] {}  ({}:{})  模块级={} 函数级={}  -> {}".format(
                    route, rel, lineno, module_ok, func_ok, kind
                )
            )
    if diffs == 0:
        print("  无差异：两套判定结论一致。")
    else:
        print("  共 {} 处差异，须逐条按上表归因（不得默认视为遗漏）。".format(diffs))


def main(argv: list[str]) -> int:
    list_only = "--list" in argv
    compare = "--compare" in argv
    if not API_DIR.is_dir():
        print("::error::API 目录不存在: {}".format(API_DIR))
        return 1

    scan_targets = _scan_targets()
    routes, module_level = collect_routes()

    # 注册表自校验：漂移必须先于路由判定报告（否则"封装失效"会被当成"路由未接线"）
    wrapper_problems = validate_wrappers()

    failures: list[str] = []
    stale_exempt: list[str] = []

    for route, reason in sorted(SENSITIVE_ROUTES.items()):
        entry = routes.get(route)
        if entry is None:
            # 路由被改名/删除：门禁不得静默失效，必须报错提示同步本清单
            failures.append("敏感路由未找到（清单过期？）: {} — {}".format(route, reason))
            continue
        rel, lineno, _node, func_ok = entry
        if not func_ok:
            failures.append(
                "{}（{}:{}）该函数不可达 write_audit — {}".format(route, rel, lineno, reason)
            )

    for route, reason in sorted(EXEMPT_ROUTES.items()):
        entry = routes.get(route)
        if entry is None:
            stale_exempt.append("豁免清单中的路由不存在: {} — {}".format(route, reason))
            continue
        rel, _lineno, _node, func_ok = entry
        if func_ok:
            stale_exempt.append("已接线，可移出豁免清单: {} ({})".format(route, rel))

    if list_only:
        print("敏感路由（需函数可达 write_audit）:")
        for route, reason in sorted(SENSITIVE_ROUTES.items()):
            entry = routes.get(route)
            state = "OK" if entry and entry[3] else "MISSING"
            print("  [{}] {:<38} {} — {}".format(state, route, entry[0] if entry else "?", reason))
        print("豁免路由（待接入）:")
        for route, reason in sorted(EXEMPT_ROUTES.items()):
            print("  [EXEMPT] {:<34} {}".format(route, reason))
        print("审计封装注册表:")
        for name, desc in sorted(AUDIT_WRAPPERS.items()):
            print("  [WRAPPER] {:<32} {}".format(name, desc))
        return 0

    if compare:
        print_compare(routes, module_level)

    if wrapper_problems:
        print("{} 项审计封装注册表漂移:".format(len(wrapper_problems)))
        for item in wrapper_problems:
            print("  [G-043] FAIL: {}".format(item))

    for note in stale_exempt:
        print("⚠️  {}".format(note))
    if failures or wrapper_problems:
        if failures:
            print("{} 项敏感端点审计接线缺失:".format(len(failures)))
            for item in failures:
                print("  [G-043] FAIL: {}".format(item))
        print("FAIL: 请为上述端点补 write_audit（或登记其审计封装进 AUDIT_WRAPPERS），"
              "或显式登记进 EXEMPT_ROUTES（须带理由）。")
        return 1
    print("✅ G-043 通过：{} 个敏感端点的函数均可达 write_audit".format(len(SENSITIVE_ROUTES)))
    print_coverage(scan_targets, routes)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
