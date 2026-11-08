#!/usr/bin/env python3
"""审计：OpenAPI 契约 vs 前端 TypeScript 接口字段。

比对步骤：
  1. 从 `docker.app:app` 生成 OpenAPI；
  2. 解析 `web/src/types/*.ts` 的 `export interface` 字段；
  3. 按 PAIRS 映射比较字段：API 多出的字段（前端未声明）与 TS 多出的字段（后端未返回）；
  4. 复用 API 矩阵检查前端调用是否都有后端路由。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PAIRS = {
    "StatusStatsResponse": "StatusStats",
    "QueryResponse": "QueryResponse",
    "AnnouncementDetailResponse": "AnnouncementDetail",
    "UserListResponse": "UserListResponse",
}
# 说明：嵌套对象用花括号配对解析，正则只用于定位 interface 起点。
INTERFACE_RE = re.compile(r"export\s+interface\s+(\w+)\s*\{(.*?)\}", re.S)
FIELD_RE = re.compile(r"^\s*(\w+)\??\s*:", re.M)


def _top_level_fields(body: str) -> set[str]:
    """只取接口顶层的字段名（按花括号深度跳过嵌套对象）。"""
    fields: set[str] = set()
    depth = 0
    for line in body.splitlines():
        stripped = line.strip()
        if depth == 0:
            match = re.match(r"(\w+)\??\s*:", stripped)
            if match:
                fields.add(match.group(1))
        depth += stripped.count("{") - stripped.count("}")
    return fields


def _interface_bodies(text: str):
    """按花括号配对提取 `export interface` 的完整函数体。"""
    """按花括号配对提取 interface 体（正则在嵌套对象处会提前截断）。"""
    for match in re.finditer(r"export\s+interface\s+(\w+)\s*\{", text):
        name = match.group(1)
        start = match.end() - 1
        depth = 0
        for idx in range(start, len(text)):
            if text[idx] == "{":
                depth += 1
            elif text[idx] == "}":
                depth -= 1
                if depth == 0:
                    yield name, text[start + 1: idx]
                    break


def ts_interfaces() -> dict[str, set[str]]:
    """扫描 web/src/types/*.ts，返回 {接口名: 顶层字段集合}。"""
    result: dict[str, set[str]] = {}
    for path in (ROOT / "web" / "src" / "types").glob("*.ts"):
        text = path.read_text(encoding="utf-8")
        for name, body in _interface_bodies(text):
            result[name] = _top_level_fields(body)
    return result


def resolve(schema: dict, components: dict) -> set[str]:
    """解析 `$ref` 并返回 JSON Schema 的属性名集合。"""
    if "$ref" in schema:
        name = schema["$ref"].split("/")[-1]
        schema = components.get(name, {})
    return set(schema.get("properties", {}))


# 比对入口：先比字段，再比前端调用路径，最后生成 Markdown 报告。
def main() -> int:
    from docker.app import app

    spec = app.openapi()
    components = spec.get("components", {}).get("schemas", {})
    ts = ts_interfaces()

    lines = ["# OpenAPI × 前端 TypeScript 契约差异", ""]
    mismatches = 0
    for api_name, ts_name in PAIRS.items():
        if api_name not in components or ts_name not in ts:
            lines.append(f"- `{api_name}` ↔ `{ts_name}`：**无法比对**（缺一侧定义）")
            mismatches += 1
            continue
        api_fields = resolve(components[api_name], components)
        ts_fields = {f for f in ts[ts_name]}
        only_api = sorted(api_fields - ts_fields)
        only_ts = sorted(ts_fields - api_fields)
        if only_api or only_ts:
            mismatches += 1
            lines.append(f"## `{api_name}` ↔ `{ts_name}`")
            if only_api:
                lines.append(f"- 后端有、前端未声明：{', '.join(f'`{f}`' for f in only_api)}")
            if only_ts:
                lines.append(f"- 前端有、后端未返回：{', '.join(f'`{f}`' for f in only_ts)}")
            lines.append("")
        else:
            lines.append(f"- `{api_name}` ↔ `{ts_name}`：一致（{len(api_fields)} 字段）")

    # 前端调用 vs OpenAPI 路径
    from scripts.audit_api_matrix import normalize_frontend, parse_frontend

    api_paths = {
        re.sub(r"\{[^}]+\}", "{p}", p): m
        for p, methods in spec["paths"].items()
        for m in methods
        if m in {"get", "post", "put", "delete", "patch"}
    }
    unmatched = []
    def _matches(norm: str) -> bool:
        """OpenAPI 路径段匹配：{p} 可匹配任意值（如 preferences/{key}）。"""
        parts = norm.strip("/").split("/")
        for route in api_paths:
            rparts = route.strip("/").split("/")
            if len(rparts) == len(parts) and all(
                rp == "{p}" or rp == dp for rp, dp in zip(rparts, parts)
            ):
                return True
        return False

    for call in parse_frontend():
        norm = normalize_frontend(call.path)
        norm = re.sub(r"\{[^}]+\}", "{p}", norm).rstrip("/")
        if not _matches(norm):
            unmatched.append((call.method, call.path, call.file, call.line))

    lines += ["", f"## 前端调用未在 OpenAPI 中出现的接口（{len(unmatched)}）", ""]
    for method, path, file, line in unmatched:
        lines.append(f"- `{method} {path}` @ {file}:{line}")
    if not unmatched:
        lines.append("（无）")

    report = "\n".join(lines) + "\n"
    (ROOT / "docs" / "testing" / "openapi-frontend-contract.md").write_text(report, encoding="utf-8")
    print(report)
    print(f"pairs_mismatch={mismatches} unmatched_calls={len(unmatched)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
