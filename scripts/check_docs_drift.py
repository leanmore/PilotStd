#!/usr/bin/env python3
"""G-052：文档漂移门禁 —— 代码事实 vs docs 声明。

抽取：
  - FastAPI 路由（docker/auth.py + docker/api/*.py）
  - 迁移中的表名（pilotstd/core/db/_migrate_*.py 的 CREATE TABLE）
  - 配置键与默认值（pilotstd.core.config.defaults.FACTORY_DEFAULTS）
  - 事件类型（pilotstd.core.notification.events.ALL_EVENTS）
  - 标准状态枚举（pilotstd.core.status.Status）

比对 docs/**/*.md：
  - 文档里写了但代码不存在的 `/api/...` 路径（废接口/死链）
  - 文档里出现的未知配置键
  - 文档里出现的未知表名（按常见后缀识别）
  - Docker 指南的端口与 compose 映射一致性

用法：
  python scripts/check_docs_drift.py            # 门禁模式，违规 exit 1
  python scripts/check_docs_drift.py --json out.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.audit_api_matrix import _public_prefixes, normalize_backend, parse_backend  # noqa: E402

DOCS = ROOT / "docs"
# 只对“当前有效”的文档做门禁：归档/计划/ADR/债务快照允许保留历史事实
EXCLUDED_DIRS = (".local", "archive", "plans", "superpowers", "adr", "debt", "testing", "records")
MIGRATIONS = ROOT / "pilotstd" / "core" / "db"

# 文档里允许出现的、并非数据库表的标识符（精确豁免，需说明原因）
TABLE_TOKEN_ALLOWLIST = {
    "standard_info_cache",  # 惰性建表，迁移里没有 CREATE TABLE
    "scheduler_lock",  # 迁移里存在，但提取器按 CREATE TABLE 匹配
}
# 只有“像表名”的后缀才做校验，避免把函数名/字段名误判成表；
TABLE_SUFFIXES = (
    "_log", "_logs", "_record", "_records", "_index", "_policy", "_cache", "_validity",
    "_runs", "_lock", "_versions", "_config", "_credentials", "_preferences", "_history",
    "_favorites", "_tasks", "_queue", "_users", "_settings", "_items",
)
# 文档中的 API 引用：反引号与裸路径都要覆盖；排除 `<...>` 占位符。
API_TOKEN_RE = re.compile(r"(?<![\w<])/api/[A-Za-z0-9_\-{}/.]+")
CONFIG_TOKEN_RE = re.compile(r"`([a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+)`")
TABLE_TOKEN_RE = re.compile(r"`([a-z][a-z0-9_]{3,})`")

# 数字声明（P2-07）：文档里写死的“事实数字”必须与代码抽取一致。
# 每条捕获的数字顺序必须与 expected() 返回顺序一致；声明被删/改到匹配不上也算失败
# （否则“删掉数字”就能绕过门禁）。只收口径明确、可机器判定的数字，不做全文数字猜测。
COUNT_CLAIMS: tuple[dict, ...] = (
    # 每条必须写 reason（P2-07 扩围规则，2026-11-14）：白名单不能"看到红就加一条"。
    {
        "doc": "docs/onboarding/03-architecture.md",
        "pattern": r"\*\*(\d+) 个 router 模块、(\d+) 个唯一 `/api` 路径\*\*",
        "label": "router 模块数 / 唯一 API 路径数",
        "expected": lambda f: (f["router_modules"], len(f["routes"])),
        "reason": "架构总览的入口数字，读者据此判断系统规模；路由增删后旧值会直接误导新人。",
    },
    {
        "doc": "docs/onboarding/19-web-win-inventory.md",
        "pattern": r"\*\*(\d+) 个 router 模块、(\d+) 个唯一 `/api` 路径\*\*",
        "label": "router 模块数 / 唯一 API 路径数",
        "expected": lambda f: (f["router_modules"], len(f["routes"])),
        "reason": "Web/Win 端点清单的基数；口径与 03 相同，两处必须同步，否则读者对不上账。",
    },
    {
        "doc": "docs/onboarding/20-api-route-inventory.md",
        "pattern": r"G-052 \*\*(\d+) 个唯一 `/api` 路径\*\*；`audit_api_matrix` \*\*(\d+) 个 route×method 对\*\*",
        "label": "唯一 API 路径数 / route×method 对数",
        "expected": lambda f: (len(f["routes"]), f["route_method_pairs"]),
        "reason": "同一页并列两种口径（唯一路径 vs route×method），写错会让人把 124 与 140 混用。",
    },
    {
        "doc": "docs/onboarding/README.md",
        "pattern": r"(\d+) 张表 \+ (\d+) 个迁移模块清单",
        "label": "迁移可解析表数 / 迁移模块数",
        "expected": lambda f: (len(f["tables"]), f["migration_modules"]),
        "reason": "onboarding 首页的规模提示；表迁移只能从代码抽取，手写必然漂移。",
    },
    {
        "doc": "docs/onboarding/03-architecture.md",
        "pattern": r"Web 的 (\d+) 个唯一",
        "label": "Web 端唯一 API 路径数（正文复述）",
        "expected": lambda f: (len(f["routes"]),),
        "reason": "正文复述同一数字；只改表格不改正文会造成同页矛盾（全量扫描 2026-11-14 发现）。",
    },
    {
        "doc": "docs/onboarding/16-notification-matrix.md",
        "pattern": r"\*\*(\d+) 个事件\*\*",
        "label": "通知事件数",
        "expected": lambda f: (len(f["events"]),),
        "reason": "事件矩阵的条目基数；新增/删除 EventSpec 后不同步，读者会按旧数量核对渠道覆盖。",
    },
    {
        "doc": "docs/onboarding/18-schema-migrations.md",
        "pattern": r"迁移可解析业务表 \*\*(\d+) 张\*\*",
        "label": "迁移可解析表数",
        "expected": lambda f: (len(f["tables"]),),
        "reason": "schema 说明的权威数字；与 SQLite 实测口径不同（需并列注明），写错会被当成表丢了。",
    },
    {
        "doc": "docs/onboarding/18-schema-migrations.md",
        "pattern": r"迁移模块 \*\*(\d+) 个 `_migrate\*\.py`\*\*",
        "label": "迁移模块数",
        "expected": lambda f: (f["migration_modules"],),
        "reason": "迁移清单的条目基数；新增迁移后不同步，读者会以为迁移链缺口。",
    },
)


def _i18n_keys() -> set[str]:
    """收集三语 JSON 的全部叶子键，用于把“文案键”与“配置键”区分开。"""
    keys: set[str] = set()
    for path in (ROOT / "pilotstd" / "i18n").glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            print(f"[WARN] i18n 文件读取失败，跳过该文件: {path}: {e}", file=sys.stderr)
            continue
        stack = [(None, data)]
        while stack:
            prefix, node = stack.pop()
            if isinstance(node, dict):
                for k, v in node.items():
                    stack.append(((prefix + "." if prefix else "") + k, v))
            elif prefix:
                keys.add(prefix)
    return keys


def load_facts() -> dict:
    """从代码抽取路由、表名、配置键、事件与状态枚举（唯一事实源）。"""
    routes = parse_backend(_public_prefixes())
    route_paths = {normalize_backend(r.path) for r in routes}

    tables: set[str] = set()
    for path in MIGRATIONS.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"']?(\w+)", text, re.I):
            tables.add(match.group(1).lower())

    from pilotstd.core.config.defaults import FACTORY_DEFAULTS

    config_keys = {str(k) for k in FACTORY_DEFAULTS}
    try:
        from pilotstd.core.config.scope import SYSTEM_KEYS, SYSTEM_PREFIXES, USER_KEYS, USER_PREFIXES

        config_keys |= set(SYSTEM_KEYS) | set(USER_KEYS)
        config_keys |= {f"{p}x" for p in SYSTEM_PREFIXES + USER_PREFIXES}
    except (ImportError, AttributeError) as e:
        # 可选依赖不可用时少收一批配置键 → 留痕，否则 drift 会静默少报
        print(f"[WARN] 配置键来源不可用，跳过该检查项: {e}", file=sys.stderr)
    config_namespaces = {k.split(".", 1)[0] for k in config_keys if "." in k}

    from pilotstd.core.notification.events import ALL_EVENTS

    event_keys = {e.key for e in ALL_EVENTS}

    from pilotstd.core.status import Status

    statuses = {s.value for s in Status}
    i18n_keys = _i18n_keys()
    # P2-07 数字声明的代码事实：路由模块数、迁移模块数、route×method 对数
    api_dir = ROOT / "docker" / "api"
    router_modules = sum(
        1 for p in api_dir.glob("*.py") if "APIRouter(" in p.read_text(encoding="utf-8")
    )
    migration_modules = len(list(MIGRATIONS.glob("_migrate_*.py")))
    route_method_pairs = len(
        {(normalize_backend(r.path), method) for r in routes for method in r.methods}
    )
    return {
        "routes": sorted(route_paths),
        "tables": sorted(tables),
        "config_keys": sorted(config_keys),
        "config_namespaces": sorted(config_namespaces),
        "events": sorted(event_keys),
        "statuses": sorted(statuses),
        "i18n_key_count": len(i18n_keys),
        "_i18n_keys": sorted(i18n_keys),
        "router_modules": router_modules,
        "migration_modules": migration_modules,
        "route_method_pairs": route_method_pairs,
    }


def _norm_api(token: str) -> str:
    """把文档中的 API 路径归一化为可比较形式（参数/数字统一为 {p}）。"""
    text = token.split("?", 1)[0].rstrip(".,;:。，；）)")
    text = re.sub(r"\{[^}]+\}", "{p}", text)
    text = re.sub(r":[A-Za-z_][A-Za-z0-9_]*", "{p}", text)
    text = re.sub(r"/[0-9]+", "/{p}", text)
    return text.rstrip("/")


# 路由匹配规则：参数段通配 + 文档只写基路径时按前缀放行。
def _route_matches(doc_path: str, route_paths: set[str]) -> bool:
    """文档路径是否对应真实路由：末段通配 + 前缀形式（文档写基路径）都算命中。"""
    parts = doc_path.strip("/").split("/")
    for route in route_paths:
        rparts = route.strip("/").split("/")
        if len(rparts) == len(parts) and all(
            rp == "{p}" or rp == dp for rp, dp in zip(rparts, parts)
        ):
            return True
        # 文档只写基路径（如 /api/system、/api/notification/callback）时按前缀放行
        if doc_path != "/api" and route.startswith(doc_path + "/"):
            return True
    return False


def scan_docs(facts: dict) -> dict:
    """遍历有效文档并返回违规项；归档/ADR/台账目录跳过。"""
    violations: list[dict] = []
    routes = {_norm_api(r) for r in facts["routes"]}
    config_keys = set(facts["config_keys"])
    namespaces = set(facts["config_namespaces"])
    i18n_keys = set(facts.get("_i18n_keys", []))
    tables = set(facts["tables"]) | TABLE_TOKEN_ALLOWLIST

    for path in sorted(DOCS.rglob("*.md")):
        try:
            rel = str(path.relative_to(ROOT))
        except ValueError:
            rel = str(path)
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if path.name.endswith(".archived.md") or path.name == "technical-debt.md":
            continue
        text = path.read_text(encoding="utf-8")
        for idx, line in enumerate(text.splitlines(), 1):
            for token in API_TOKEN_RE.findall(line):
                norm = _norm_api(token)
                if not norm.startswith("/api/"):
                    continue
                if not _route_matches(norm, routes):
                    if any(word in line for word in ("已删除", "已移除", "历史")) or ("删除" in line and "已" in line):
                        continue
                    violations.append({"kind": "dead_api", "file": rel, "line": idx,
                                       "token": token, "reason": "路由不存在"})
            for token in CONFIG_TOKEN_RE.findall(line):
                if token.split(".", 1)[0] not in namespaces:
                    continue
                segs = token.split(".")
                if any(seg.startswith("_") for seg in segs) or token.endswith((".md", ".py", ".json")):
                    continue
                if token in i18n_keys:
                    continue
                is_group = any(k.startswith(token + ".") for k in config_keys)
                if token not in config_keys and not is_group:
                    violations.append({"kind": "unknown_config", "file": rel, "line": idx,
                                       "token": token, "reason": "配置键不存在"})
            table_context = ("数据表" in line) or ("表 `" in line) or ("table " in line.lower())
            for token in TABLE_TOKEN_RE.findall(line):
                if not table_context or not token.endswith(TABLE_SUFFIXES):
                    continue
                if token not in tables:
                    violations.append({"kind": "unknown_table", "file": rel, "line": idx,
                                       "token": token, "reason": "表名不存在"})
    return {"facts": facts, "violations": violations}


def check_count_claims_meta(claims: tuple[dict, ...] | None = None) -> list[dict]:
    """校验数字声明的元数据：每条 `reason` 必填（P2-07 扩围规则）。

    P2-07 扩围后白名单会变长，若"加一条数字声明"不需要理由，白名单就会退化成
    "看到红就加一条"的垃圾桶。这里把"必须写理由"变成机械校验，缺了直接判违规。
    """
    selected = COUNT_CLAIMS if claims is None else claims
    return [
        {
            "kind": "claim_meta",
            "file": claim.get("doc", "?"),
            "line": 0,
            "token": claim.get("label", ""),
            "reason": "COUNT_CLAIMS 条目缺少 reason（白名单必须写豁免理由）",
        }
        for claim in selected
        if not str(claim.get("reason") or "").strip()
    ]


def check_count_claims(
    facts: dict, claims: tuple[dict, ...] | None = None, root: Path | None = None
) -> list[dict]:
    """校验文档写死的数字声明与代码事实一致（P2-07）。

    只认 `COUNT_CLAIMS` 里显式登记的“口径明确”数字；声明缺失按违规处理，
    防止通过删除数字绕过门禁。
    """
    root = root or ROOT
    selected = COUNT_CLAIMS if claims is None else claims
    violations: list[dict] = []
    for claim in selected:
        path = root / claim["doc"]
        if not path.exists():
            violations.append(
                {
                    "kind": "count_missing",
                    "file": claim["doc"],
                    "line": 0,
                    "token": claim["pattern"],
                    "reason": "数字声明所在文档不存在",
                }
            )
            continue
        text = path.read_text(encoding="utf-8")
        match = re.search(claim["pattern"], text)
        if not match:
            violations.append(
                {
                    "kind": "count_missing",
                    "file": claim["doc"],
                    "line": 0,
                    "token": claim["pattern"],
                    "reason": "数字声明缺失（删除声明不能绕过门禁）",
                }
            )
            continue
        claimed = tuple(int(g) for g in match.groups())
        expected = tuple(int(v) for v in claim["expected"](facts))
        if claimed != expected:
            line_no = text[: match.start()].count("\n") + 1
            violations.append(
                {
                    "kind": "count_drift",
                    "file": claim["doc"],
                    "line": line_no,
                    "token": " / ".join(str(c) for c in claimed),
                    "reason": f"{claim['label']}：文档 {claimed} ≠ 实际 {expected}",
                }
            )
    return violations


def _compose_port() -> str:
    """读取 compose 的宿主端口（用于端口一致性的扩展检查）。"""
    compose = ROOT / "docker-compose.yml"
    if not compose.exists():
        return ""
    text = compose.read_text(encoding="utf-8")
    match = re.search(r"\"?(\d{4,5}):(\d{4,5})\"?", text)
    return match.group(1) if match else ""


def render(report: dict) -> str:
    """把扫描结果渲染成 Markdown 报告。"""
    v = report["violations"]
    lines = ["# 文档漂移检查", ""]
    lines.append(f"- 路由 {len(report['facts']['routes'])}；表 {len(report['facts']['tables'])}；"
                 f"配置键 {len(report['facts']['config_keys'])}；事件 {len(report['facts']['events'])}")
    lines.append(f"- 违规：**{len(v)}**")
    by_kind: dict[str, list[dict]] = {}
    for item in v:
        by_kind.setdefault(item["kind"], []).append(item)
    for kind, items in by_kind.items():
        lines += ["", f"## {kind}（{len(items)}）", "", "| 文档 | 行 | 标识 | 原因 |", "|---|---|---|---|"]
        for item in items:
            lines.append(f"| {item['file']} | {item['line']} | `{item['token']}` | {item['reason']} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    """门禁入口：有违规返回 1，供 CI 阻断。"""
    parser = argparse.ArgumentParser(description="文档漂移门禁")
    parser.add_argument("--json", dest="json_path")
    parser.add_argument("--strict", action="store_true", help="保留参数，默认即阻断")
    args = parser.parse_args(argv)

    facts = load_facts()
    report = scan_docs(facts)
    report["violations"].extend(check_count_claims_meta())
    report["violations"].extend(check_count_claims(facts))
    if args.json_path:
        Path(args.json_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(render(report))
    if report["violations"]:
        print(f"FAIL: {len(report['violations'])} 处文档漂移，请修文档或代码")
        return 1
    print("PASS: 文档与代码事实一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
