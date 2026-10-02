#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""G-043 敏感端点审计接线门禁。

背景（第 2 批安全审计闭环，docs/plans/batch2-security-audit-design.md）：
全库仅 4 处 `write_audit`，而使用 `@require_role` 的端点有 61 处；凭证变更、
改密、令牌轮换、用户增删等敏感操作「放行不写审计」无任何门禁拦截。

判定规则：
- 扫描 `docker/api/**/*.py` 中的状态变更路由装饰器（POST/PUT/DELETE/PATCH）；
- 路由命中 SENSITIVE_ROUTES（且不在 EXEMPT_ROUTES 中）→ 要求其所属模块内存在
  `write_audit(` 调用，否则 FAIL；
- EXEMPT_ROUTES 是**显式登记**的待接入清单，每条必须带理由（禁止无理由豁免）。
  某条一旦在该模块内出现 `write_audit`，会提示"可移出豁免"（不阻断）。

已知局限（有意保留、避免过度实现）：本门禁按**模块**粒度判定，无法区分"同文件内
另一个端点已写审计"的情形（如 admin_db.py 的 DB_QUERY 已写）。升级到函数级 AST
判定留待 P1/P2 端点真正接入时再做——届时豁免清单已清空，函数级判定才有意义。

用法：
  python scripts/check_sensitive_endpoint_audit.py            # 门禁（CI）
  python scripts/check_sensitive_endpoint_audit.py --list     # 列出敏感路由与接线状态
退出码：0 = 通过；1 = 存在未接线的敏感端点。
"""

from __future__ import annotations

import io
import re
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
    # （不在 docker/api/ 下），故同时扩展了扫描目录 SCAN_DIRS——否则本清单会"静默失效"
    # （路由查不到 → 门禁报"清单过期"）。
    "POST /api/login": "S1 认证凭证校验失败（阈值告警 + LOGIN_FAILED 审计）",
}

# 显式登记的待接入清单：每条必须带理由。禁止无理由豁免（P-104 门禁不绕过）。
EXEMPT_ROUTES: dict[str, str] = {
    "DELETE /api/users/{user_id}": "S2 待接入（第 3 批）：用户删除不可逆",
    "POST /api/users": "S2 待接入（第 3 批）：新增账号是提权前置动作",
    "POST /api/auth/register": "S2 待接入（第 3 批）：自助注册是注册误开的唯一信号",
    "DELETE /api/admin/logs": "S3 待接入（第 3 批）：破坏性批删",
    "POST /api/cache/cleanup": "S3 待接入（第 3 批）：缓存强制清理",
    "POST /api/backup/create": "待接入（第 3 批）：手动备份与定时路径口径不一致",
    "POST /query": "S3 已由 admin_db.py 的 DB_QUERY 覆盖（函数级判定升级后移出）",
}

_ROUTE_RE = re.compile(
    r"@router\.(post|put|delete|patch)\(\s*[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)
_WRITE_AUDIT_RE = re.compile(r"\bwrite_audit\s*\(")


def scan_module_routes(path: Path) -> dict[str, int]:
    """返回 {路由键: 行号}，路由键形如 'PUT /api/xxx'。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    found: dict[str, int] = {}
    for lineno, line in enumerate(text.splitlines(), 1):
        match = _ROUTE_RE.search(line)
        if match:
            found["{} {}".format(match.group(1).upper(), match.group(2))] = lineno
    return found


def module_has_write_audit(path: Path) -> bool:
    """模块内是否存在 write_audit 调用（含 import 后的使用）。"""
    try:
        return bool(_WRITE_AUDIT_RE.search(path.read_text(encoding="utf-8")))
    except OSError:
        return False


def print_coverage(scan_targets: list[Path], audit_modules: set[str]) -> None:
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
        scope="{}（路由装饰器 POST/PUT/DELETE/PATCH；实扫 {} 个文件）".format(scope, len(scan_targets)),
        checked=len(SENSITIVE_ROUTES) + len(EXEMPT_ROUTES),
        passed=len(SENSITIVE_ROUTES),
        blocked=0,
        exempted=len(EXEMPT_ROUTES),
        exemptions=["{} — {}".format(route, reason) for route, reason in sorted(EXEMPT_ROUTES.items())],
        notes=(
            "需 write_audit 的路由 -> {} 项（SENSITIVE_ROUTES）".format(len(SENSITIVE_ROUTES)),
            "显式豁免的路由 -> {} 项（EXEMPT_ROUTES，逐条见下）".format(len(EXEMPT_ROUTES)),
        ),
        uncovered=(
            "判定为**模块级**：同一文件内任一端点有 write_audit 即整模块通过，"
            "无法区分同文件内其它端点是否缺审计；函数级 AST 判定未实现。"
            "上述 {} 项豁免端点仍未接入审计".format(len(EXEMPT_ROUTES))
        ),
    )


def main(argv: list[str]) -> int:
    list_only = "--list" in argv
    if not API_DIR.is_dir():
        print("::error::API 目录不存在: {}".format(API_DIR))
        return 1

    audit_modules: set[str] = set()
    all_routes: dict[str, tuple[str, int]] = {}  # 路由键 → (相对路径, 行号)
    scan_targets = [p for d in API_DIRS if d.is_dir() for p in sorted(d.rglob("*.py"))]
    if AUTH_MODULE.exists():
        scan_targets.append(AUTH_MODULE)
    for path in scan_targets:
        if path.name == "__init__.py":
            continue
        routes = scan_module_routes(path)
        if routes and module_has_write_audit(path):
            audit_modules.add(str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"))
        for key, lineno in routes.items():
            all_routes.setdefault(key, (str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"), lineno))

    failures: list[str] = []
    stale_exempt: list[str] = []

    for route, reason in sorted(SENSITIVE_ROUTES.items()):
        if route not in all_routes:
            # 路由被改名/删除：门禁不得静默失效，必须报错提示同步本清单
            failures.append("敏感路由未找到（清单过期？）: {} — {}".format(route, reason))
            continue
        rel, lineno = all_routes[route]
        if rel not in audit_modules:
            failures.append("{}（{}:{}）缺少 write_audit 调用 — {}".format(route, rel, lineno, reason))

    for route, reason in sorted(EXEMPT_ROUTES.items()):
        entry = all_routes.get(route)
        if entry is None:
            stale_exempt.append("豁免清单中的路由不存在: {} — {}".format(route, reason))
            continue
        rel, _lineno = entry
        if rel in audit_modules:
            stale_exempt.append("已接线，可移出豁免清单: {} ({})".format(route, rel))

    if list_only:
        print("敏感路由（需 write_audit）:")
        for route, reason in sorted(SENSITIVE_ROUTES.items()):
            entry = all_routes.get(route)
            state = "OK" if entry and entry[0] in audit_modules else "MISSING"
            print("  [{}] {:<38} {} — {}".format(state, route, entry[0] if entry else "?", reason))
        print("豁免路由（待接入）:")
        for route, reason in sorted(EXEMPT_ROUTES.items()):
            print("  [EXEMPT] {:<34} {}".format(route, reason))
        return 0

    for note in stale_exempt:
        print("⚠️  {}".format(note))
    if failures:
        print("{} 项敏感端点审计接线缺失:".format(len(failures)))
        for item in failures:
            print("  [G-043] FAIL: {}".format(item))
        print("FAIL: 请为上述端点补 write_audit，或显式登记进 EXEMPT_ROUTES（须带理由）。")
        return 1
    print("✅ G-043 通过：{} 个敏感端点均已接入审计".format(len(SENSITIVE_ROUTES)))
    print_coverage(scan_targets, audit_modules)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
