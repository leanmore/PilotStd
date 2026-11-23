#!/usr/bin/env python3
"""部署探测：版本 / schema / 服务健康（只读）。

覆盖的验证点（对应 `docs/debt/00-global-issues.md` 的部署口径与
`docs/reference/health-check.md`）：

1. `GET /api/health` 状态码与字段：200 `ok` / 207 `degraded` / 500 `down` / 403 外网被拒；
2. **版本一致性**：`/api/system/version` 的 `version`、仓库 `VERSION`、`pilotstd.__version__`
   三者必须相同；`/api/health` 的 `version` 是镜像构建参数 `APP_VERSION`（本部署为 git sha），
   若形如 sha 则核对它在本仓库里存在且是 `HEAD` 的祖先（=「镜像里跑的就是这份代码」）；
3. **schema 一致性**：`/api/health` 的 `schema_version` 必须等于
   `pilotstd/core/db/_constants.py` 的 `CURRENT_SCHEMA_VERSION`（迁移链最新版本）；
4. 健康检查内部项：磁盘余量、调度器心跳、数据库读写。

只读：仅 `GET`。任何需要登录的项都先 `POST /api/login`（白名单，仅建会话）。

用法：
  python scripts/ops/probe_health.py
  python scripts/ops/probe_health.py --base-url http://192.168.1.18:9028 --json
  python scripts/ops/probe_health.py --strict        # 诊断项失败也阻断

退出码：0 通过 / 1 有失败或必跑项无法验证 / 2 环境不可达。
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _probe_common as common  # noqa: E402  共享层（凭据/HTTP/报告）

ROOT = common.ROOT
VERSION_FILE = ROOT / "VERSION"
CONSTANTS_FILE = ROOT / "pilotstd" / "core" / "db" / "_constants.py"
# `/api/health` 的 version 来自 Dockerfile 的 APP_VERSION 构建参数，本部署是 40 位 git sha
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _local_version() -> tuple[str, str]:
    """读仓库 `VERSION` 文件与 `pilotstd.__version__`，返回 `(VERSION 文件, 包内版本)`。"""
    file_version = ""
    if VERSION_FILE.exists():
        file_version = VERSION_FILE.read_text(encoding="utf-8").strip()
    package_version = ""
    init_py = ROOT / "pilotstd" / "__init__.py"
    if init_py.exists():
        match = re.search(r'__version__\s*=\s*"([^"]+)"', init_py.read_text(encoding="utf-8"))
        package_version = match.group(1) if match else ""
    return file_version, package_version


def _local_schema_version() -> int:
    """读 `_constants.py` 的 `CURRENT_SCHEMA_VERSION`（迁移链最新版本）；读不到返回 -1。"""
    if not CONSTANTS_FILE.exists():
        return -1
    match = re.search(
        r"^CURRENT_SCHEMA_VERSION\s*=\s*(\d+)",
        CONSTANTS_FILE.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    return int(match.group(1)) if match else -1


def _git_commit_exists(sha: str) -> tuple[bool, str]:
    """判断 sha 是否存在于本地仓库，并返回它相对 `HEAD` 的关系说明（只读 git 调用）。"""
    try:
        kind = subprocess.run(
            ["git", "cat-file", "-t", sha],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        # git 不可用：无法验证，必须明说而不是当成通过
        return False, f"git 不可用（{type(exc).__name__}），无法核对 sha 是否在仓库中"
    if kind.returncode != 0 or kind.stdout.strip() != "commit":
        return False, f"本地仓库中不存在该 commit（git cat-file 返回 {kind.returncode}）"
    subject = subprocess.run(
        ["git", "log", "--oneline", "-1", sha],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=20,
    ).stdout.strip()
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", sha, "HEAD"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=20,
    )
    if ancestor.returncode == 0:
        return True, f"commit 存在且是 HEAD 的祖先：{subject}"
    return True, f"commit 存在但**不是** HEAD 的祖先（本地领先/分叉）：{subject}"


def probe_service_health(report: common.Report, client: common.HttpClient) -> dict:
    """探测 `/api/health`：状态码语义、内部检查项、服务标记；返回原始载荷供后续比对。"""
    response = client.get("/api/health")
    payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    status_code = response.status_code
    # 状态码 → 结论：207 是「可用但降级」，按必跑项失败处理（部署验证要求全绿）
    if status_code == 200 and payload.get("status") == "ok":
        report.add("health.status", common.STATUS_PASS, "200 ok", status=payload.get("status"))
    elif status_code == 207:
        report.add(
            "health.status",
            common.STATUS_FAIL,
            "207 degraded：服务可用但降级，需看 disk/scheduler 明细",
            status=payload.get("status"),
            checks=payload.get("checks", {}),
        )
    elif status_code == 500:
        report.add(
            "health.status",
            common.STATUS_FAIL,
            "500 down：数据库读写失败，核心不可用",
            status=payload.get("status"),
        )
    elif status_code == 403:
        report.add(
            "health.status",
            common.STATUS_UNVERIFIED,
            "403：生产环境仅允许内网 RFC1918 访问，请从内网发起探测",
            status=status_code,
        )
    else:
        report.add("health.status", common.STATUS_FAIL, f"未预期的状态码 {status_code}")

    checks = payload.get("checks") or {}
    disk = checks.get("disk") or {}
    if disk:
        ok = bool(disk.get("ok"))
        report.add(
            "health.disk",
            common.STATUS_PASS if ok else common.STATUS_FAIL,
            f"剩余 {disk.get('free_mb')} MB（阈值 {disk.get('threshold_mb')} MB）",
            free_mb=disk.get("free_mb"),
            threshold_mb=disk.get("threshold_mb"),
        )
    scheduler = checks.get("scheduler") or {}
    if scheduler:
        ok = bool(scheduler.get("ok"))
        report.add(
            "health.scheduler",
            common.STATUS_PASS if ok else common.STATUS_FAIL,
            f"心跳 {scheduler.get('heartbeat_at')}（{scheduler.get('age_seconds')}s 前，阈值 180s）",
            age_seconds=scheduler.get("age_seconds"),
        )
    database_rw = checks.get("database_rw") or {}
    if database_rw:
        ok = bool(database_rw.get("read")) and bool(database_rw.get("write"))
        report.add(
            "health.database_rw",
            common.STATUS_PASS if ok else common.STATUS_FAIL,
            f"read={database_rw.get('read')} write={database_rw.get('write')}",
        )
    services = payload.get("services") or {}
    if services:
        report.add(
            "health.services",
            common.STATUS_PASS if all(services.values()) else common.STATUS_FAIL,
            "、".join(f"{k}={v}" for k, v in services.items()),
            tier=common.TIER_ADVISORY,
        )
    return payload


def probe_version_consistency(report: common.Report, client: common.HttpClient, health: dict) -> None:
    """比对版本：`/api/system/version`、仓库 `VERSION`、`pilotstd.__version__` 三者一致。"""
    file_version, package_version = _local_version()
    status_code, payload = client.get_json("/api/system/version")
    api_version = str((payload or {}).get("version") or "") if status_code == 200 else ""
    if status_code != 200:
        report.add(
            "version.api",
            common.STATUS_UNVERIFIED,
            f"/api/system/version 返回 {status_code}（该端点在鉴权白名单内，非 200 说明镜像异常）",
        )
        return
    consistent = bool(api_version) and api_version == file_version == package_version
    report.add(
        "version.consistency",
        common.STATUS_PASS if consistent else common.STATUS_FAIL,
        f"服务端 {api_version or '空'} / VERSION 文件 {file_version or '空'} / 包内 {package_version or '空'}",
        api_version=api_version,
        file_version=file_version,
        package_version=package_version,
        image=str((payload or {}).get("image") or ""),
    )
    # `/api/health` 的 version 是构建参数 APP_VERSION：本部署为 git sha，需单独核对来源
    health_version = str(health.get("version") or "")
    if _SHA_RE.match(health_version):
        exists, detail = _git_commit_exists(health_version)
        is_ancestor = exists and "是 HEAD 的祖先" in detail
        report.add(
            "version.deployed_commit",
            common.STATUS_PASS if is_ancestor else common.STATUS_UNVERIFIED,
            f"health.version={health_version[:12]}… {detail}",
            tier=common.TIER_ADVISORY,
            sha=health_version,
        )
    elif health_version and health_version != "unknown":
        report.add(
            "version.deployed_commit",
            common.STATUS_PASS if health_version == api_version else common.STATUS_FAIL,
            f"health.version={health_version}（非 sha 形态，按语义版本比对）",
            tier=common.TIER_ADVISORY,
        )
    else:
        report.add(
            "version.deployed_commit",
            common.STATUS_UNVERIFIED,
            "health.version=unknown：镜像构建未注入 APP_VERSION（Dockerfile ARG 未传）",
            tier=common.TIER_ADVISORY,
        )


def probe_schema_consistency(report: common.Report, client: common.HttpClient, health: dict) -> None:
    """比对 schema：`/api/health.schema_version` 必须等于代码库迁移链最新版本。"""
    local_schema = _local_schema_version()
    api_schema = health.get("schema_version")
    if local_schema < 0:
        report.add(
            "schema.consistency",
            common.STATUS_UNVERIFIED,
            "读不到 pilotstd/core/db/_constants.py 的 CURRENT_SCHEMA_VERSION",
        )
        return
    if api_schema is None:
        report.add(
            "schema.consistency",
            common.STATUS_FAIL,
            "健康检查未返回 schema_version（字段缺失或读取失败时服务端返回 0）",
            local=local_schema,
        )
        return
    ok = int(api_schema) == local_schema
    report.add(
        "schema.consistency",
        common.STATUS_PASS if ok else common.STATUS_FAIL,
        f"服务端 {api_schema} / 代码库 {local_schema}"
        + ("" if ok else "（镜像未执行最新迁移，或代码比镜像新）"),
        api_schema=int(api_schema),
        local_schema=local_schema,
    )


def run(options: common.ProbeOptions, session=None) -> common.Report:
    """执行本 probe 的全部探测，返回 `Report`（不打印、不退出，便于测试与 `probe_all` 复用）。"""
    creds = common.read_creds()
    base_url = common.resolve_base_url(options.base_url, creds)
    report = common.Report("health", base_url)
    client = common.HttpClient(base_url, timeout=options.timeout, session=session, creds=creds)
    try:
        health = probe_service_health(report, client)
    except common.EnvironmentUnreachable as exc:
        # 环境不可达：不编造通过/失败，明确记录原因，由调用方转退出码 2
        report.unreachable_reason = str(exc)
        report.add("health.status", common.STATUS_UNVERIFIED, f"环境不可达：{exc}")
        return report
    probe_version_consistency(report, client, health)
    probe_schema_consistency(report, client, health)
    return report


def main(argv: list[str] | None = None) -> int:
    """命令行入口：解析参数 → 跑探测 → 按退出码语义返回。"""
    common.stdout_utf8()
    parser = argparse.ArgumentParser(description="部署探测：版本 / schema / 服务健康（只读）")
    common.add_common_args(parser)
    args = parser.parse_args(argv)
    options = common.ProbeOptions(base_url=args.base_url, timeout=args.timeout, strict=args.strict)
    report = run(options)
    if report.unreachable_reason:
        common.finish(report, args)
        return common.EXIT_UNREACHABLE
    return common.finish(report, args)


if __name__ == "__main__":
    sys.exit(main())
