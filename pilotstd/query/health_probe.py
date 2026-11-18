"""适配器健康检查：每小时对 21 个适配器发一条固定探针查询，记录 found/no_result/error。

结果同时写结构化日志与 `/app/data/health_probe.json`（最后一次结果），供 API 查看。
"""

from __future__ import annotations

import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# 每站固定探针（可按站点实际收录调整；同一探针不随机，保证可比）
PROBES: dict[str, str] = {
    # 2026-11-17 校准：取各站点 standard_info_cache 中最近一次 match_status=exact 的标准号
    "ahbz": "NB/T 47016-2023",
    "csres": "GB/T 17395-2024",
    "cssn": "GB/T 8165-2008",
    "dbba": "DB50/T 1982-2026",
    "hbba": "JB/T 13964-2020",
    "iso_gov": "ISO 16852:2016",
    "jjg": "JJG 141-2013",
    "mee": "GB 37822-2019",
    "njbz365": "NB/T 47033-2013",
    "std_gov": "GB/T 10827.6-2023",
}

# 无成功缓存、无法校准探针的站点：只报“探针待定”，不输出误导性 no_result
PROBE_PENDING: dict[str, str] = {
    "ccsn": "no exact cache",
    "energy": "no exact cache",
    "gongbiaoku": "no exact cache",
    "jtst": "no exact cache",
    "miit": "no exact cache",
    "ncha": "no exact cache",
    "nrsis": "no exact cache",
    "sppt": "no exact cache",
    "sppt_local": "no exact cache",
    "tdpress": "no exact cache",
    "ttbz": "no exact cache",
}


_HEALTH_FILE = os.environ.get("PILOTSTD_HEALTH_PROBE_FILE", "/app/data/health_probe.json")
_last_result: dict | None = None


def _classify(results) -> str:
    """查询结果三态：found / no_result；异常在外层记 error。"""
    if not results:
        return "no_result"
    return "found" if any(getattr(r, "is_found", lambda: False)() for r in results) else "no_result"


# 单站探针：独立线程 + 超时，任何异常都落 error，不阻断其余站点
def discover_probes() -> dict[str, str]:
    """从 standard_info_cache 的 exact 记录为 probe_pending 站点自动发现探针。"""
    try:
        from pilotstd.core.config.paths import get_db_path
        from pilotstd.core.db import Database

        db = Database(get_db_path())
        rows = db.fetchall(
            "SELECT source_site, standard_number FROM standard_info_cache "
            "WHERE result_json LIKE '%\"match_status\": \"exact\"%' "
            "ORDER BY id DESC"
        )
        found: dict[str, str] = {}
        for r in rows:
            site = str(r["source_site"] or "")
            if site in PROBE_PENDING and site not in found and r["standard_number"]:
                found[site] = str(r["standard_number"])
        return found
    except Exception as exc:  # noqa: BLE001 - 探针发现失败不影响主流程
        logger.warning("adapter_health probe discovery failed: %s", exc)
        return {}


def _probe_one(site: str, probe: str, timeout: float) -> dict:
    started = time.time()
    try:
        from .adapters.registry import ALL_ADAPTERS

        cls = ALL_ADAPTERS.get(site)
        if cls is None:
            raise RuntimeError("adapter not registered")
        adapter: Any = cls()
        with ThreadPoolExecutor(max_workers=1) as pool:
            if hasattr(adapter, "query_standards"):
                # 站点级适配器：直接按标准号查询
                future = pool.submit(adapter.query_standards, probe)
                results = future.result(timeout=timeout)
            else:
                # 搜索引擎型适配器：走渐进式搜索（与主查询链同入口）
                from ..core.std_utils import parse_std_number

                parsed = parse_std_number(probe)
                if not parsed:
                    raise ValueError(f"probe parse failed: {probe}")
                future = pool.submit(
                    adapter.query_with_strategy,
                    parsed["code"],
                    parsed["number"],
                    parsed["year"],
                    "",
                    parsed.get("part"),
                    parsed.get("num_prefix", "") or "",
                    parsed.get("num_suffix", "") or "",
                )
                single = future.result(timeout=timeout)
                results = [single] if single is not None else []
        status = _classify(results)
        error = ""
    except Exception as exc:  # noqa: BLE001 - 单站失败必须记 error，不阻断其余站点
        status = "error"
        error = str(exc)[:200]
    elapsed_ms = int((time.time() - started) * 1000)
    row = {"site": site, "probe": probe, "status": status, "elapsed_ms": elapsed_ms, "error": error}
    logger.info(
        "adapter_health site=%s probe=%s status=%s elapsed_ms=%d error=%s",
        site,
        probe,
        status,
        elapsed_ms,
        error,
    )
    return row


def run_health_check(timeout: float = 20.0) -> dict:
    """并发跑全部适配器探针，返回并持久化最后一次结果。"""
    started_at = datetime.now(timezone.utc).isoformat()
    rows: list[dict] = []
    probes = dict(PROBES)
    probes.update(discover_probes())
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(_probe_one, site, probe, timeout): site for site, probe in probes.items()}
        for future in as_completed(futures):
            try:
                rows.append(future.result())
            except Exception as exc:  # noqa: BLE001 - 兜底，理论到不了
                site = futures[future]
                rows.append(
                    {
                        "site": site,
                        "probe": PROBES[site],
                        "status": "error",
                        "elapsed_ms": 0,
                        "error": str(exc)[:200],
                    }
                )
    for site, reason in PROBE_PENDING.items():
        if site in probes:
            continue
        rows.append(
            {"site": site, "probe": "", "status": "probe_pending", "elapsed_ms": 0, "error": reason}
        )
    rows.sort(key=lambda r: r["site"])
    summary = {
        k: sum(1 for r in rows if r["status"] == k)
        for k in ("found", "no_result", "error", "probe_pending")
    }
    result = {"checked_at": started_at, "summary": summary, "results": rows}
    global _last_result
    _last_result = result
    try:
        os.makedirs(os.path.dirname(_HEALTH_FILE), exist_ok=True)
        with open(_HEALTH_FILE, "w", encoding="utf-8") as fh:
            json.dump(result, fh, ensure_ascii=False, indent=2)
    except OSError as exc:
        logger.warning("adapter_health persist failed: %s", exc)
    return result


def get_last_result() -> dict | None:
    """返回内存中的最后一次结果；进程重启后从 JSON 文件回读。"""
    global _last_result
    if _last_result is not None:
        return _last_result
    try:
        with open(_HEALTH_FILE, encoding="utf-8") as fh:
            _last_result = json.load(fh)
    except (OSError, ValueError) as exc:
        # 无历史结果不是错误路径，但留日志便于排查文件损坏/权限问题
        logger.warning("adapter_health read failed: %s", exc)
        return None
    return _last_result
