#!/usr/bin/env python3
"""部署探测：`mark_missing` 路径映射 + `/inbox` 挂载 + 端点存在性（只读）。

对应 G-48「mark_missing 已修复待部署」与 G-32「33 条 file_missing 已查清」的验收口径：

1. **`/inbox` 与 `/standards` 挂载**：`GET /api/files?path=/inbox` 能列出条目（容器内挂载正常），
   并用 `GET /api/settings` 的 `storage.scan_paths` 确认探测根目录就是配置的扫描根；
2. **路径映射**：pending 里 `reason=file_missing` 的行，其 `file_path` 必须①落在配置的扫描根下
   （否则是「路径映射错误」而不是文件缺失），且②在**同相对路径的其他扫描根**下也找不到
   （否则是「镜像目录里还在 → 假 missing」）。两者任一命中即判定为**假 missing**并阻断；
3. **`mark_missing` 端点是否已部署**：`OPTIONS /api/pending/mark-missing` 返回 `405` 且
   `Allow` 含 `POST` = 已部署；`404` = 未部署（旧镜像）；`401/403` = 权限不足无法判断。
   **绝不发送 POST**（该端点无请求体，空 body 也会真的执行标记）；
4. **挂载保护**：按 pending 实际缺失比例推算 `_is_mass_delete_anomaly` 是否会把整轮标记跳过
   （≥50 行且缺失占比 ≥90%），避免「跑完却什么都没标记」被误读成通过；
5. 定时任务 `pending_missing_check` 是否注册（诊断项）。

只读：仅 `GET` / `OPTIONS` + 白名单内的 `POST /api/login`。

用法：
  python scripts/ops/probe_pending_paths.py
  python scripts/ops/probe_pending_paths.py --base-url http://192.168.1.18:9028 --json
  python scripts/ops/probe_pending_paths.py --max-items 5   # 只抽样 5 条 pending 核对路径

退出码：0 通过 / 1 有失败或必跑项无法验证 / 2 环境不可达。
"""

from __future__ import annotations

import argparse
import posixpath
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _probe_common as common  # noqa: E402  共享层（凭据/HTTP/报告）

# 复用生产判据需要能 `import` `pilotstd`（直接运行脚本时 sys.path[0] 是 scripts/ops，不含仓库根）
if str(common.ROOT) not in sys.path:
    sys.path.insert(0, str(common.ROOT))

# 扫描根缺省值：与 `pilotstd/core/config/defaults.py` 的 `storage` 默认一致（取不到配置时兜底）
DEFAULT_ROOTS = ("/inbox", "/standards")
# 挂载保护判据的来源：`pilotstd/core/file_index.py` 的同名常量（复用函数而非复制阈值）
GUARD_MIN_ROWS = 50
GUARD_MISSING_RATIO = 0.9


def _guard_would_skip(total: int, missing: int) -> bool:
    """复用生产判据 `_is_mass_delete_anomaly`，判断本轮 mark_missing 是否会被整轮跳过。

    直接 import 生产函数而不是复制阈值，避免探测口径与生产口径漂移。
    """
    from pilotstd.core.file_index import _is_mass_delete_anomaly

    return bool(_is_mass_delete_anomaly(total, missing))


def _list_dir(client: common.HttpClient, path: str) -> tuple[int, list[str]]:
    """用 `GET /api/files` 列出目录条目名，返回 `(状态码, 名称列表)`；404=目录不存在。"""
    response = client.get("/api/files", params={"path": path})
    if response.status_code != 200:
        return response.status_code, []
    payload = response.json()
    return 200, [str(item.get("name") or "") for item in payload.get("files", [])]


def _path_exists(
    client: common.HttpClient,
    file_path: str,
    cache: dict[str, list[str] | None] | None = None,
) -> tuple[bool, str]:
    """判断容器内某个绝对路径是否存在，返回 `(存在, 说明)`。

    只读实现：列出父目录后比对文件名。父目录不存在即路径不存在；父目录可列但名字不在其中
    也判不存在（`/api/files` 只列直接子项，不递归）。`cache` 按父目录缓存，避免同一目录重复请求。
    """
    parent = posixpath.dirname(file_path.rstrip("/")) or "/"
    name = posixpath.basename(file_path.rstrip("/"))
    if cache is not None and parent in cache:
        status, names = (200, cache[parent]) if cache[parent] is not None else (404, [])
    else:
        status, names = _list_dir(client, parent)
        if cache is not None:
            cache[parent] = names if status == 200 else None
    if status == 404:
        return False, f"父目录 {parent} 不存在"
    if status != 200:
        return False, f"列目录失败 HTTP {status}（无法判定，按不存在处理并已在报告中标注）"
    if name in names:
        return True, f"父目录 {parent} 中存在同名条目"
    return False, f"父目录 {parent} 可列（{len(names)} 项）但不含 {name}"


def probe_mounts(report: common.Report, client: common.HttpClient) -> tuple[list[str], dict]:
    """探测 `/inbox` 与 `/standards` 挂载，返回 `(扫描根列表, settings 载荷)`。"""
    status_code, settings = client.get_json("/api/settings")
    scan_paths: list[str] = []
    if status_code == 200 and isinstance(settings, dict):
        storage = settings.get("storage") or {}
        scan_paths = [str(p) for p in (storage.get("scan_paths") or []) if p]
        inbox_cfg = str(storage.get("downloads_dir") or "")
        if inbox_cfg and inbox_cfg not in scan_paths:
            scan_paths.append(inbox_cfg)
    if not scan_paths:
        scan_paths = list(DEFAULT_ROOTS)
        report.add(
            "mounts.scan_paths",
            common.STATUS_UNVERIFIED,
            f"读不到 /api/settings 的 storage.scan_paths，按默认 {DEFAULT_ROOTS} 兜底",
            tier=common.TIER_ADVISORY,
        )
    else:
        report.add("mounts.scan_paths", common.STATUS_PASS, "扫描根：" + "、".join(scan_paths))
    for root in scan_paths:
        status, names = _list_dir(client, root)
        if status == 200:
            # 挂载正常的判据：能列出条目（空目录也算挂载成功，但要在报告里说明）
            report.add(
                f"mounts{root}",
                common.STATUS_PASS,
                f"可列目录，直接子项 {len(names)} 个",
                entries=len(names),
                sample=names[:5],
            )
        elif status == 404:
            report.add(
                f"mounts{root}",
                common.STATUS_FAIL,
                "404 路径不存在：容器内该目录未创建或宿主机未挂载",
            )
        else:
            report.add(f"mounts{root}", common.STATUS_UNVERIFIED, f"列目录返回 HTTP {status}")
    return scan_paths, settings if isinstance(settings, dict) else {}


def _root_of(path: str, roots: list[str]) -> str:
    """返回 `path` 所属的扫描根（最长前缀匹配）；不属于任何根返回空串。"""
    matched = [root for root in roots if path == root or path.startswith(root.rstrip("/") + "/")]
    return max(matched, key=len, default="")


def probe_pending_paths(
    report: common.Report, client: common.HttpClient, roots: list[str], max_items: int
) -> dict[str, Any]:
    """核对 pending 行的路径是否**真的**不存在，返回统计摘要。

    抽样范围是**所有带路径的 pending 行**（不只是已标 `file_missing` 的）：`mark_missing_files`
    的生产口径是 `WHERE status='pending'`，只抽查已标 missing 的行会低估缺失比例，导致
    「挂载保护会不会整轮跳过」推算失真。
    """
    status_code, payload = client.get_json("/api/pending")
    if status_code != 200:
        report.add(
            "pending.list",
            common.STATUS_UNVERIFIED,
            f"GET /api/pending 返回 {status_code}（需要登录且为 admin）",
            tier=common.TIER_REQUIRED,
        )
        return {"total": 0, "sampled": 0}
    items = (payload or {}).get("items") or []
    with_path = [it for it in items if str(it.get("file_path") or "").strip()]
    already_missing = [it for it in with_path if str(it.get("reason") or "") == "file_missing"]
    report.add(
        "pending.rows",
        common.STATUS_PASS,
        f"pending 共 {len(items)} 条（带路径 {len(with_path)}，已标 file_missing {len(already_missing)}）",
        total=len(items),
        with_path=len(with_path),
        already_missing=len(already_missing),
    )

    sample = with_path[: max(0, int(max_items))]
    dir_cache: dict[str, list[str] | None] = {}
    genuinely_missing = 0
    fake_missing: list[str] = []
    mapping_errors: list[str] = []
    unverifiable: list[str] = []
    for row in sample:
        file_path = str(row.get("file_path") or "")
        root = _root_of(file_path, roots)
        if not root:
            # 路径不落在任何配置的扫描根下：这是「路径映射错误」，不是文件缺失
            mapping_errors.append(f"{file_path}（不在扫描根 {roots} 下）")
            continue
        exists, detail = _path_exists(client, file_path, dir_cache)
        if exists:
            fake_missing.append(f"{file_path}（{detail}）")
            continue
        if "无法判定" in detail:
            unverifiable.append(f"{file_path}（{detail}）")
            continue
        # 镜像假设：同一相对路径在另一个扫描根下是否还在（在 → 之前标 `missing` 是假缺失）
        rel = file_path[len(root) :].lstrip("/")
        mirrored = ""
        for other in roots:
            if other == root:
                continue
            candidate = other.rstrip("/") + "/" + rel
            if _path_exists(client, candidate, dir_cache)[0]:
                mirrored = candidate
                break
        if mirrored:
            fake_missing.append(f"{file_path}（镜像路径仍存在：{mirrored}）")
        else:
            genuinely_missing += 1

    report.add(
        "pending.path_mapping",
        (
            common.STATUS_SKIP
            if not sample
            else common.STATUS_FAIL
            if (mapping_errors or fake_missing)
            else common.STATUS_PASS
        ),
        (
            "无带路径的 pending 行或 --max-items=0，未抽样核对（不据此判通过）"
            if not sample
            else f"抽样 {len(sample)} 条：真缺失 {genuinely_missing} / 假缺失 {len(fake_missing)} / "
            f"映射错误 {len(mapping_errors)}"
        ),
        sampled=len(sample),
        genuinely_missing=genuinely_missing,
        fake_missing=fake_missing[:10],
        mapping_errors=mapping_errors[:10],
    )
    if unverifiable:
        report.add(
            "pending.path_unverifiable",
            common.STATUS_UNVERIFIED,
            f"{len(unverifiable)} 条路径无法判定（列目录失败）：" + "；".join(unverifiable[:5]),
            tier=common.TIER_ADVISORY,
        )
    return {
        "total": len(items),
        "with_path": len(with_path),
        "already_missing": len(already_missing),
        "sampled": len(sample),
        "genuinely_missing": genuinely_missing,
        "fake_missing": len(fake_missing),
        "mapping_errors": len(mapping_errors),
    }

def probe_mark_missing_endpoint(report: common.Report, client: common.HttpClient) -> None:
    """判断 `POST /api/pending/mark-missing` 是否已部署；**只发 OPTIONS，绝不 POST**。

    判据（实测语义）：
      * `405` 且 `Allow` 含 `POST` → 路由已注册（已部署）；
      * `404` → 路由不存在（旧镜像，需更新镜像）；
      * `401/403` → 未登录/权限不足，无法判断（需要 admin token）；
      * `405` 但 `Allow` 只有 `GET` → 命中的是 SPA 回退路由，同样视为未部署。
    """
    response = client.options("/api/pending/mark-missing")
    allow = str(response.headers.get("allow") or "").upper()
    status_code = response.status_code
    if status_code == 405 and "POST" in allow:
        report.add(
            "endpoint.mark_missing",
            common.STATUS_PASS,
            f"OPTIONS 405 Allow={allow}：端点已部署（未执行任何标记）",
            allow=allow,
        )
    elif status_code == 404:
        report.add(
            "endpoint.mark_missing",
            common.STATUS_FAIL,
            "OPTIONS 404：端点未部署 → 需更新镜像（代码已实现，镜像未跟上）",
        )
    elif status_code in (401, 403):
        report.add(
            "endpoint.mark_missing",
            common.STATUS_UNVERIFIED,
            f"OPTIONS {status_code}：鉴权未通过，无法判断端点是否存在（需要 admin 会话）",
        )
    elif status_code == 405:
        report.add(
            "endpoint.mark_missing",
            common.STATUS_FAIL,
            f"OPTIONS 405 Allow={allow or '空'}：未命中 POST 路由（可能是 SPA 回退），判定未部署",
            allow=allow,
        )
    else:
        report.add(
            "endpoint.mark_missing",
            common.STATUS_UNVERIFIED,
            f"OPTIONS 返回未预期状态码 {status_code}",
        )


def probe_scheduler_job(report: common.Report, client: common.HttpClient) -> None:
    """核对定时任务 `pending_missing_check` 是否已注册（诊断项）。"""
    status_code, payload = client.get_json("/api/scheduler/status")
    if status_code != 200:
        report.add(
            "scheduler.pending_missing_check",
            common.STATUS_UNVERIFIED,
            f"/api/scheduler/status 返回 {status_code}",
            tier=common.TIER_ADVISORY,
        )
        return
    jobs = (payload or {}).get("jobs") or []
    job = next((j for j in jobs if str(j.get("id") or "") == "pending_missing_check"), None)
    if job is None:
        report.add(
            "scheduler.pending_missing_check",
            common.STATUS_FAIL,
            "调度器未注册 pending_missing_check（配置 pending.mark_missing_enabled 可能被关闭）",
            tier=common.TIER_ADVISORY,
            jobs=[str(j.get("id") or "") for j in jobs][:20],
        )
        return
    report.add(
        "scheduler.pending_missing_check",
        common.STATUS_PASS,
        f"已注册，下次执行 {job.get('next_run_time')}（触发 {job.get('trigger')}）",
        tier=common.TIER_ADVISORY,
        next_run_time=job.get("next_run_time"),
        trigger=job.get("trigger"),
    )


def run(options: common.ProbeOptions, session=None) -> common.Report:
    """执行本 probe 的全部探测；登录失败不抛异常，转「无法验证」。"""
    creds = common.read_creds()
    base_url = common.resolve_base_url(options.base_url, creds)
    report = common.Report("pending_paths", base_url)
    client = common.HttpClient(base_url, timeout=options.timeout, session=session, creds=creds)
    try:
        status_code, _ = client.get_json("/api/health")
    except common.EnvironmentUnreachable as exc:
        report.unreachable_reason = str(exc)
        report.add("health.reachable", common.STATUS_UNVERIFIED, f"环境不可达：{exc}")
        return report
    if status_code != 200:
        report.add(
            "health.reachable",
            common.STATUS_UNVERIFIED,
            f"/api/health 返回 {status_code}，无法继续探测",
        )
        return report

    try:
        login_detail = client.require_admin()
        report.add("auth.admin", common.STATUS_PASS, login_detail)
    except common.AuthError as exc:
        # 没有 `admin` 会话：端点存在性、`pending` 路径都无从核对，如实标「无法验证」
        report.add(
            "auth.admin",
            common.STATUS_UNVERIFIED,
            f"{exc}；所需条件：config/docker_creds.json 的 username/password 为 admin 账号",
        )
        probe_mark_missing_endpoint(report, client)
        return report

    roots, _settings = probe_mounts(report, client)
    stats = probe_pending_paths(report, client, roots, options.max_items)
    probe_mark_missing_endpoint(report, client)
    probe_scheduler_job(report, client)

    # 挂载保护推算：本轮若真跑 mark_missing，会不会因「疑似挂载异常」整轮跳过。
    # 生产判据（`mark_missing_files`）用的是 `status='pending'` 的**全部行**与其中路径不存在的行数，
    # 这里按抽样缺失率外推到全表，避免用抽样数冒充全表数。
    pending_total = int(stats.get("total") or 0)
    sampled = int(stats.get("sampled") or 0)
    sampled_missing = int(stats.get("genuinely_missing") or 0)
    if pending_total and sampled:
        estimated_missing = round(pending_total * sampled_missing / sampled)
        would_skip = _guard_would_skip(pending_total, estimated_missing)
        # 保护判据本身分不清「真的大批缺失」与「挂载没起来」；本 `probe` 已独立核对过挂载可列、
        # 路径都在配置的扫描根下，故这里能给出更准确的结论：挂载正常时即为保护的**误报**。
        mounts_ok = all(
            c.status == common.STATUS_PASS for c in report.checks if c.name.startswith("mounts/")
        )
        mapping_ok = not any(
            c.name == "pending.path_mapping" and c.status == common.STATUS_FAIL for c in report.checks
        )
        if would_skip and mounts_ok and mapping_ok:
            conclusion = (
                "**会整轮跳过**：缺失比例触发了挂载保护，定时任务与端点跑完都不会标记任何行。"
                "本探测已确认挂载可列、路径都在配置扫描根下 → 这是保护的**误报**（数据真的缺失），"
                "需要管理员在维护窗口内以 protect=False 执行一次，或先清理这批 pending"
            )
        elif would_skip:
            conclusion = "**会整轮跳过**：缺失比例触发挂载保护，需先人工确认 /inbox 挂载与路径映射"
        else:
            conclusion = "不会触发，可正常标记"
        report.add(
            "pending.mass_delete_guard",
            common.STATUS_PASS if not would_skip else common.STATUS_FAIL,
            (
                f"按抽样外推：缺失约 {estimated_missing}/{pending_total}"
                f"（阈值 ≥{GUARD_MIN_ROWS} 行且 ≥{GUARD_MISSING_RATIO:.0%}）：" + conclusion
            ),
            tier=common.TIER_REQUIRED,
            pending_total=pending_total,
            estimated_missing=estimated_missing,
            sampled=sampled,
            sampled_missing=sampled_missing,
            mounts_ok=mounts_ok,
            mapping_ok=mapping_ok,
        )
    return report


def main(argv: list[str] | None = None) -> int:
    """命令行入口：解析参数 → 跑探测 → 按退出码语义返回。"""
    common.stdout_utf8()
    parser = argparse.ArgumentParser(description="部署探测：mark_missing 路径映射 / 挂载 / 端点（只读）")
    common.add_common_args(parser)
    parser.add_argument(
        "--max-items", type=int, default=20, help="最多抽样核对的 pending 行数（默认 20，0 表示不抽样）"
    )
    args = parser.parse_args(argv)
    options = common.ProbeOptions(
        base_url=args.base_url, timeout=args.timeout, max_items=args.max_items, strict=args.strict
    )
    report = run(options)
    if report.unreachable_reason:
        common.finish(report, args)
        return common.EXIT_UNREACHABLE
    return common.finish(report, args)


if __name__ == "__main__":
    sys.exit(main())
