# 模块：容器/健康检查服务脚本
# 独立健康检查：对查询/公告适配器做轻量级探活，与业务任务（查询/抓取）彻底分离

import logging
from datetime import datetime, timezone
from typing import Any

from pilotstd.core.config import get_db_path
from pilotstd.core.db import Database
from pilotstd.query.network import CHROME_UA, safe_raw_get, safe_raw_post
from pilotstd.query.site_config import create_default_sites

logger = logging.getLogger(__name__)

# 公告适配器探活地址：三站分别探活各自搜索端点，健康状态相互独立
_ANNOUNCE_ADAPTERS = {
    "gb": "https://std.samr.gov.cn/noc/search/nocGBPage",
    "hb": "https://std.samr.gov.cn/noc/search/nocHBPage",
    "db": "https://std.samr.gov.cn/noc/search/nocDBPage",
}

_HEALTH_TIMEOUT = 10  # 探活超时秒数


def _probe(url: str, site_name: str, probe_method: str = "GET", probe_params: dict | None = None) -> str:
    """对单个站点做轻量级探活，返回 'up' 或 'down'。

    `probe_params` 为站点真实请求形态所需的参数：AJAX 端点（energy 的 stdPage）
    不带参数会返回 400，曾让在线站点被误判为 down。
    失败日志传 `log_failures=False`：探活每小时一次，重复告警由调用方按
    "状态变化才告警"处理，避免淹没有效信号。
    """
    # miit 的 requests TLS 指纹被拦截（403），curl 实测可通，用 subprocess 单独探活
    if site_name == "miit" or "std.miit.gov.cn" in url:
        import subprocess

        try:
            result = subprocess.run(
                ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "10", url],
                capture_output=True,
                text=True,
                timeout=12,
            )
            code = result.stdout.strip()
            return "up" if code.isdigit() and int(code) < 400 else "down"
        except Exception as e:
            logger.warning("[health] miit curl 探活失败: %s", e)
            return "down"

    # energy 为纯 IP + 自签名证书站点，跳过 SSL 验证（与适配器 verify=False 保持一致）
    verify = site_name != "energy"
    # 用浏览器 UA 探活，避免站点反爬拦截（与公告/查询适配器保持一致）
    headers = {"User-Agent": CHROME_UA}
    kwargs: dict[str, Any] = {
        "timeout": _HEALTH_TIMEOUT,
        "verify": verify,
        "headers": headers,
        "params": probe_params or None,
        "log_failures": False,
    }
    if probe_method.upper() == "POST":
        resp = safe_raw_post(url, site_name, **kwargs)
    else:
        resp = safe_raw_get(url, site_name, **kwargs)
    if resp is not None and resp.status_code < 400:
        return "up"
    return "down"


def _log_health_transition(name: str, previous: str | None, status: str) -> None:
    """只在健康状态**变化**时告警。

    探活每小时跑一次：持续 down 的站点（如 jtst 外部不可达）若每次都打 WARNING，
    会把日志淹成噪音；状态本身仍照常写入 adapter_state，不掩盖真实错误。
    """
    if previous == status:
        logger.debug("[health] %s 仍为 %s", name, status)
    elif status == "down":
        logger.warning("[health] %s 转为不可用（%s → down）", name, previous or "未知")
    else:
        logger.info("[health] %s 已恢复（%s → up）", name, previous or "未知")


def _write_health(name: str, status: str) -> str | None:
    """将探活结果 UPSERT 写入 adapter_state，仅更新健康检查字段组。

    Returns:
        写入前的 health_status（无记录时为 None），供调用方判断是否发生状态变化。
    """
    db = Database(get_db_path())
    previous: str | None = None
    try:
        row = db.fetchone("SELECT health_status FROM adapter_state WHERE adapter_name = ?", (name,))
        previous = row["health_status"] if row else None
        db.execute(
            "INSERT INTO adapter_state (adapter_name, last_health_check, health_status, updated_at) "
            "VALUES (?, ?, ?, datetime('now', 'localtime')) "
            "ON CONFLICT(adapter_name) DO UPDATE SET "
            "last_health_check = excluded.last_health_check, "
            "health_status = excluded.health_status, "
            "updated_at = excluded.updated_at",
            (name, datetime.now(timezone.utc).isoformat(), status),
        )
    except Exception as e:
        logger.warning("[health] %s 健康状态写入失败: %s", name, e)
    finally:
        db.close()
    return previous


def run_health_check() -> dict[str, Any]:
    """执行全量健康检查：遍历查询适配器与公告适配器，返回统计结果。"""
    stats: dict[str, Any] = {"total": 0, "up": 0, "down": 0}

    # 查询适配器：从站点配置读取主页地址，逐一探活
    try:
        sites = create_default_sites()
    except Exception:
        logger.exception("[health] 加载查询站点配置失败")
        sites = []
    for site in sites:
        probe_url = site.probe_url or site.base_url
        status = _probe(probe_url, site.name, site.probe_method, site.probe_params)
        previous = _write_health(site.name, status)
        _log_health_transition(site.name, previous, status)
        stats["total"] += 1
        stats[status] += 1

    # 公告适配器：国标/行标/地标共用官方平台主页地址
    for std_type, url in _ANNOUNCE_ADAPTERS.items():
        status = _probe(url, std_type)
        previous = _write_health(std_type, status)
        _log_health_transition(std_type, previous, status)
        stats["total"] += 1
        stats[status] += 1

    logger.info(
        "[health] 健康检查完成: total=%s up=%s down=%s",
        stats["total"],
        stats["up"],
        stats["down"],
    )
    return stats
