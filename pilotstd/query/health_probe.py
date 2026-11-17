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
    "ahbz": "GB/T 19001-2016",
    "ccsn": "GB/T 19001-2016",
    "csres": "GB/T 19001-2016",
    "cssn": "GB/T 19001-2016",
    "dbba": "GB/T 19001-2016",
    "energy": "NB/T 47014-2011",
    "gongbiaoku": "GB/T 19001-2016",
    "hbba": "HG/T 20592-2009",
    "iso_gov": "ISO 9001:2015",
    "jjg": "JJG 1-2003",
    "jtst": "GB/T 19001-2016",
    "mee": "HJ 536-2009",
    "miit": "GB/T 19001-2016",
    "ncha": "GB/T 19001-2016",
    "njbz365": "GB/T 19001-2016",
    "nrsis": "NB/T 47013-2015",
    "sppt": "GB/T 19001-2016",
    "sppt_local": "GB/T 19001-2016",
    "std_gov": "GB/T 19001-2016",
    "tdpress": "GB/T 19001-2016",
    "ttbz": "GB/T 19001-2016",
}

_HEALTH_FILE = os.environ.get("PILOTSTD_HEALTH_PROBE_FILE", "/app/data/health_probe.json")
_last_result: dict | None = None


def _classify(results) -> str:
    """查询结果三态：found / no_result；异常在外层记 error。"""
    if not results:
        return "no_result"
    return "found" if any(getattr(r, "is_found", lambda: False)() for r in results) else "no_result"


# 单站探针：独立线程 + 超时，任何异常都落 error，不阻断其余站点
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
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(_probe_one, site, probe, timeout): site for site, probe in PROBES.items()}
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
    rows.sort(key=lambda r: r["site"])
    summary = {k: sum(1 for r in rows if r["status"] == k) for k in ("found", "no_result", "error")}
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
