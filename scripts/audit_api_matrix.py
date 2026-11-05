#!/usr/bin/env python3
"""API × 前端调用 × 权限矩阵审计工具（阶段 1，只读）。

抽取：
  - `docker/auth.py` + `docker/api/*.py` 的全部路由（方法/路径/是否 admin/是否按用户过滤/是否公开白名单）；
  - `web/src/**` 的 `http.<method>(...)` 调用；
  - `web/src/router.ts` 的路由 `meta.permission` 守卫。

输出（Markdown + JSON）：
  1. 写操作缺少显式 `@require_role("admin")` 的后端路由（中间件仍会拦，属“纵深防御缺口”）；
  2. 前端调用 admin-only 路由的位置，并标注所在页面是否配置了 `meta.permission`；
  3. 前端调用不存在/方法不匹配的接口；
  4. 未配置权限守卫的前端页面清单。

用法：
  python scripts/audit_api_matrix.py --md C:/Temp/api_matrix.md --json C:/Temp/api_matrix.json
  python scripts/audit_api_matrix.py --strict   # 有 UNMATCHED 时退出码 1
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

# 仓库根目录：脚本位于 scripts/ 下，向上取一级即可定位 docker/ 与 web/。
ROOT = Path(__file__).resolve().parent.parent
ROUTER_FILES = [ROOT / "docker" / "auth.py", *sorted((ROOT / "docker" / "api").glob("*.py"))]
WEB_SRC = ROOT / "web" / "src"
MIDDLEWARE = ROOT / "docker" / "auth_middleware.py"
AUTH_STATE = ROOT / "docker" / "auth_state.py"
VUE_ROUTER = WEB_SRC / "router.ts"

# 写方法集合：只有这些方法参与“是否要求 admin”的判定；GET/HEAD 不在审计范围。
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
HTTP_METHODS = {"get", "post", "put", "delete", "patch"}
PARAM_RE = re.compile(r"\{[^}]+\}")
TS_PARAM_RE = re.compile(r"\$\{[^}]+\}")
CALL_RE = re.compile(r"http\.(get|post|put|delete|patch)\(\s*[`'\"]([^`'\"]+)[`'\"]")
ROUTE_BLOCK_RE = re.compile(r"\{\s*path:\s*'([^']+)'([\s\S]{0,700}?)(?=\n\s*\{\s*path:|\n\])")
VIEW_RE = re.compile(r"import\('\./views/([^']+)\.vue'\)")


@dataclass
class Route:
    """后端路由：方法集合、源码路径、是否 admin、是否按用户过滤、是否公开。"""

    methods: set[str] = field(default_factory=set)
    path: str = ""
    file: str = ""
    func: str = ""
    admin: bool = False
    user_scoped: bool = False
    role: str = ""
    public: bool = False

    @property
    def normalized(self) -> str:
        return normalize_backend(self.path)


@dataclass
class Call:
    """前端调用：HTTP 方法、调用路径、所在文件与行号。"""

    method: str = ""
    path: str = ""
    file: str = ""
    line: int = 0

    @property
    def normalized(self) -> str:
        return normalize_frontend(self.path)


# 后端路径：保留源码写法（例如 /query 就是 /query），不能统一补 /api 前缀。
def normalize_backend(path: str) -> str:
    """后端路径按源码原样归一（`/query` 就是 `/query`，不能补 `/api`）。"""
    text = path.split("?", 1)[0].strip()
    text = PARAM_RE.sub("{p}", text)
    return text.rstrip("/") or "/"


# 前端调用：axios 实例 baseURL 为 /api，路径要先补前缀再与后端比对。
def normalize_frontend(path: str) -> str:
    """前端 `http` 的 baseURL 是 `/api`，调用路径需要补前缀后再比对。"""
    text = path.split("?", 1)[0].strip()
    text = TS_PARAM_RE.sub("{p}", text)
    text = PARAM_RE.sub("{p}", text)
    if not text.startswith("/api/") and text not in {"/api"}:
        text = "/api" + (text if text.startswith("/") else "/" + text)
    return text.rstrip("/") or "/api"


# 尾部通配：FastAPI 的 {key:path} 是“尾部通配”，匹配时要按目录前缀而不是全等。
def is_path_wildcard(path: str) -> bool:
    return "{key:path}" in path or "{" in path and ":path" in path


def _literal(node: ast.AST):
    """提取字面量常量；兼容 `frozenset({...})` / `set()` / 元组等门禁写法。"""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id in {"frozenset", "set", "tuple", "list"} and node.args:
            return _literal(node.args[0])
        return None
    if isinstance(node, ast.Set):
        return {_literal(item) for item in node.elts}
    if isinstance(node, (ast.Tuple, ast.List)):
        return tuple(_literal(item) for item in node.elts)
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return None


def _name(node: ast.AST) -> str:
    """取装饰器/调用表达式的末级名字（如 require_role、Depends）。"""
    if isinstance(node, ast.Call):
        node = node.func
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


# 路由前缀：用 APIRouter(prefix=...)，解析路由时必须把前缀拼回去。
def _router_prefix(tree: ast.Module) -> str:
    """读取模块级 router = APIRouter(prefix=...) 的前缀。"""
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if "router" not in targets or not isinstance(node.value, ast.Call):
                continue
            for kw in node.value.keywords:
                value = _literal(kw.value)
                if kw.arg == "prefix" and isinstance(value, str):
                    return value
    return ""


# 公开白名单（登录/健康/回调等）不参与“缺少 admin 装饰器”的统计。
def _public_prefixes() -> tuple[str, ...]:
    """读取公开白名单前缀，公开路由不参与“缺少 admin 装饰器”统计。"""
    try:
        tree = ast.parse(AUTH_STATE.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return ()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = (
                [t.id for t in node.targets if isinstance(t, ast.Name)]
                if isinstance(node, ast.Assign)
                else [node.target.id]
            )
            if "AUTH_WHITELIST" not in targets:
                continue
            value = _literal(node.value)
            if isinstance(value, (list, tuple)):
                prefixes = []
                for item in value:
                    if isinstance(item, (list, tuple)) and item and isinstance(item[0], str):
                        prefixes.append(item[0])
                return tuple(prefixes)
    return ()


# 逐文件 AST 解析：装饰器决定方法与角色，函数签名决定是否按用户过滤。
def parse_backend(public_prefixes: tuple[str, ...]) -> list[Route]:
    """逐文件解析后端路由：装饰器定方法/角色，函数签名定是否按用户过滤。"""
    routes: list[Route] = []
    for file in ROUTER_FILES:
        try:
            tree = ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
        except (SyntaxError, OSError):
            continue
        prefix = _router_prefix(tree)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            methods: set[str] = set()
            path = ""
            admin = False
            role = ""
            for dec in node.decorator_list:
                if not isinstance(dec, ast.Call):
                    continue
                name = _name(dec)
                if name in HTTP_METHODS and dec.args:
                    value = _literal(dec.args[0])
                    if isinstance(value, str):
                        methods.add(name.upper())
                        path = value
                elif name == "require_role" and dec.args:
                    value = _literal(dec.args[0])
                    if isinstance(dec.args[0], ast.Name) and dec.args[0].id == "ADMIN_ROLE":
                        value = "admin"
                    if isinstance(value, str):
                        role = value
                        admin = value == "admin"
            if not methods or not path:
                continue
            full = (prefix.rstrip("/") + "/" + path.lstrip("/")) if prefix else path
            normalized = normalize_backend(full)
            user_scoped = False
            for arg in list(node.args.args) + list(node.args.kwonlyargs):
                default = None
                if arg in node.args.args:
                    idx = node.args.args.index(arg) - (len(node.args.args) - len(node.args.defaults))
                    if idx >= 0:
                        default = node.args.defaults[idx]
                elif arg in node.args.kwonlyargs:
                    idx = node.args.kwonlyargs.index(arg)
                    if idx < len(node.args.kw_defaults):
                        default = node.args.kw_defaults[idx]
                if isinstance(default, ast.Call) and _name(default) == "Depends" and default.args:
                    if _name(default.args[0]) in {"get_current_user_id", "_get_user_id"}:
                        user_scoped = True
            routes.append(
                Route(
                    methods=methods,
                    path=full,
                    file=str(file.relative_to(ROOT)),
                    func=node.name,
                    admin=admin,
                    user_scoped=user_scoped,
                    role=role,
                    public=any(normalized.startswith(normalize_backend(p)) for p in public_prefixes),
                )
            )
    return routes


# 中间件白名单：从源码常量读取，避免 import 触发鉴权模块的副作用。
def parse_user_write_allowlist() -> tuple[set[str], tuple[str, ...]]:
    """从中间件源码常量读取普通用户可写白名单（避免 import 副作用）。"""
    exact: set[str] = set()
    prefixes: tuple[str, ...] = ()
    try:
        tree = ast.parse(MIDDLEWARE.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return exact, prefixes
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if "_USER_WRITE_ALLOWED_EXACT" not in names and "_USER_WRITE_ALLOWED_PREFIX" not in names:
            continue
        items = _strings(node.value)
        if "_USER_WRITE_ALLOWED_EXACT" in names:
            exact = set(items)
        else:
            prefixes = tuple(items)
    return exact, prefixes


def _strings(node: ast.AST) -> list[str]:
    """从 Set/List/Tuple/frozenset(...) 里提取字符串元素。"""
    value = _literal(node)
    if isinstance(value, str):
        return [value]
    if isinstance(value, (set, frozenset, tuple, list)):
        return [str(v) for v in value if isinstance(v, str)]
    return []


def allowed_user_write(path: str, exact: set[str], prefixes: tuple[str, ...]) -> bool:
    return path in exact or path.startswith(prefixes)


# 前端调用：用正则抓 `http.<method>(` 的首个字符串参数；覆盖模板字符串。
def parse_frontend() -> list[Call]:
    """扫描前端源码中的 http 调用（方法 + 路径 + 行号）。"""
    calls: list[Call] = []
    for file in sorted(WEB_SRC.rglob("*")):
        if file.suffix not in {".ts", ".vue"}:
            continue
        try:
            lines = file.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, 1):
            for match in CALL_RE.finditer(line):
                calls.append(Call(method=match.group(1).upper(), path=match.group(2),
                                  file=str(file.relative_to(ROOT)), line=lineno))
    return calls


# 页面守卫：解析 router.ts 的 meta.permission，判断页面是否对普通用户可见。
def parse_view_guards() -> dict[str, bool]:
    """返回 {ViewName: 是否配置了 meta.permission}。"""
    guards: dict[str, bool] = {}
    try:
        text = VUE_ROUTER.read_text(encoding="utf-8")
    except OSError:
        return guards
    for match in ROUTE_BLOCK_RE.finditer(text):
        block = match.group(0)
        view = VIEW_RE.search(block)
        if not view:
            continue
        guards[view.group(1)] = "permission" in block
    return guards


# 矩阵比对：先按归一化路径找候选，再校验方法；通配路由退化为前缀匹配。
def build_report(routes, calls, exact, prefixes, guards) -> dict:
    """构建审计矩阵：匹配调用、识别 admin-only 调用、死调用与未守卫页面。"""
    by_path: dict[str, list[Route]] = {}
    for route in routes:
        by_path.setdefault(route.normalized, []).append(route)

    unmatched, method_mismatch, admin_calls = [], [], []
    for call in calls:
        candidates = by_path.get(call.normalized, [])
        if not candidates:
            # 通配尾部（{key:path}）按前缀匹配
            candidates = [
                r
                for r in routes
                if is_path_wildcard(r.path)
                and call.normalized.startswith(r.normalized.rsplit("/", 1)[0] + "/")
            ]
        if not candidates:
            unmatched.append(_call_dict(call))
            continue
        route = next((r for r in candidates if call.method in r.methods), None)
        if route is None:
            item = _call_dict(call)
            item["backend_methods"] = sorted({m for r in candidates for m in r.methods})
            method_mismatch.append(item)
            continue
        if route.admin:
            item = _call_dict(call)
            item["route"] = route.path
            view = Path(call.file).stem
            item["view_guarded"] = guards.get(view) if call.file.endswith(".vue") and "/views/" in call.file else None
            admin_calls.append(item)

    write_without_admin = []
    for route in routes:
        if not (route.methods & WRITE_METHODS) or route.admin or route.public:
            continue
        if route.user_scoped or allowed_user_write(route.normalized, exact, prefixes):
            continue
        write_without_admin.append(_route_dict(route))

    unguarded_views = sorted([name for name, guarded in guards.items() if not guarded])
    return {
        "routes": len(routes),
        "calls": len(calls),
        "write_without_admin": sorted(write_without_admin, key=lambda r: r["path"]),
        "admin_calls": admin_calls,
        "unmatched": unmatched,
        "method_mismatch": method_mismatch,
        "unguarded_views": unguarded_views,
        "user_write_allowlist": sorted(exact),
        "user_write_prefixes": list(prefixes),
    }


def _route_dict(route: Route) -> dict:
    return {"path": route.path, "methods": sorted(route.methods), "file": route.file,
            "func": route.func, "role": route.role, "user_scoped": route.user_scoped}


def _call_dict(call: Call) -> dict:
    return {"method": call.method, "path": call.path, "file": call.file, "line": call.line}


# 输出：Markdown 供审计报告引用；JSON 供后续门禁/趋势对比。
def render_markdown(report: dict) -> str:
    """把矩阵渲染为 Markdown 报告。"""
    lines = [
        "# API × 前端调用 × 权限矩阵",
        "",
        f"- 后端路由：{report['routes']}；前端调用：{report['calls']}",
        f"- 写操作缺少显式 admin 装饰器（中间件仍拦截）：**{len(report['write_without_admin'])}**",
        f"- 前端调用 admin-only 路由：**{len(report['admin_calls'])}**",
        f"- 前端调用不存在的接口：**{len(report['unmatched'])}**；方法不匹配：**{len(report['method_mismatch'])}**",
        f"- 未配置 `meta.permission` 的 view：**{len(report['unguarded_views'])}**",
        "",
        "## 1. 写操作缺少显式 admin 装饰器",
        "",
        "> 说明：AuthMiddleware 已对“非白名单写操作”统一要求 admin，本表是纵深防御缺口；",
        "> 直接调用路由函数（测试/内部）或未来中间件被绕过时才会真正越权。",
        "",
        "| 路径 | 方法 | 文件:函数 | 按用户过滤 |",
        "|---|---|---|---|",
    ]
    for item in report["write_without_admin"]:
        lines.append(f"| `{item['path']}` | {','.join(item['methods'])} | {item['file']}:{item['func']} | "
                     f"{'是' if item['user_scoped'] else '否'} |")
    lines += [
        "",
        "## 2. 前端调用 admin-only 路由",
        "",
        "| 调用 | 方法 | 位置 | 页面有 permission 守卫 |",
        "|---|---|---|---|",
    ]
    for item in report["admin_calls"]:
        guard = {True: "是", False: "**否**", None: "组件内（未知）"}[item.get("view_guarded")]
        lines.append(f"| `{item['path']}` | {item['method']} | {item['file']}:{item['line']} | {guard} |")
    lines += ["", "## 3. 前端调用不存在的接口", "", "| 调用 | 方法 | 位置 |", "|---|---|---|"]
    for item in report["unmatched"]:
        lines.append(f"| `{item['path']}` | {item['method']} | {item['file']}:{item['line']} |")
    lines += ["", "## 4. 未配置权限守卫的 view", "", "、".join(report["unguarded_views"]) or "（无）", ""]
    return "\n".join(lines) + "\n"


# 命令行入口：--strict 时只要有死调用就返回 1，便于后续接入 CI。
def main(argv: list[str] | None = None) -> int:
    """命令行入口：输出矩阵，--strict 时死调用返回非零。"""
    parser = argparse.ArgumentParser(description="API × 前端 × 权限矩阵审计")
    parser.add_argument("--md")
    parser.add_argument("--json", dest="json_path")
    parser.add_argument("--strict", action="store_true", help="存在死调用时退出 1")
    parser.add_argument("--check", action="store_true", help="门禁模式：写端点缺 admin 或前端死调用即退出 1")
    args = parser.parse_args(argv)

    routes = parse_backend(_public_prefixes())
    calls = parse_frontend()
    exact, prefixes = parse_user_write_allowlist()
    report = build_report(routes, calls, exact, prefixes, parse_view_guards())

    if args.md:
        Path(args.md).write_text(render_markdown(report), encoding="utf-8")
    if args.json_path:
        Path(args.json_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"routes={report['routes']} calls={report['calls']} "
          f"write_without_admin={len(report['write_without_admin'])} "
          f"admin_calls={len(report['admin_calls'])} unmatched={len(report['unmatched'])} "
          f"method_mismatch={len(report['method_mismatch'])} "
          f"unguarded_views={len(report['unguarded_views'])}")
    for item in report["unmatched"]:
        print(f"  UNMATCHED {item['method']} {item['path']} @ {item['file']}:{item['line']}")
    for item in report["write_without_admin"]:
        print(f"  WRITE_NO_ADMIN {item['path']} {item['methods']} {item['file']}:{item['func']}")
    if args.strict and report["unmatched"]:
        return 1
    if args.check:
        problems = report["unmatched"] + report["write_without_admin"]
        if problems:
            print(f"CHECK FAILED: {len(problems)} problems (unmatched/write_without_admin)")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
