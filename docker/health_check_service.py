# 模块：容器/健康检查服务脚本
# 独立健康检查：对查询/公告适配器做轻量级探活，与业务任务（查询/抓取）彻底分离

import logging
from datetime import datetime, timezone
from typing import Any

from pilotstd.core.config import get_db_path
from pilotstd.core.db import Database
from pilotstd.query.network import CHROME_UA, safe_raw_get
from pilotstd.query.site_config import create_default_sites

logger = logging.getLogger(__name__)

# 公告适配器探活地址：三站分别探活各自搜索端点，健康状态相互独立
_ANNOUNCE_ADAPTERS = {
    "gb": "https://std.samr.gov.cn/noc/search/nocGBPage",
    "hb": "https://std.samr.gov.cn/noc/search/nocHBPage",
    "db": "https://std.samr.gov.cn/noc/search/nocDBPage",
}

_HEALTH_TIMEOUT = 10  # 探活超时秒数


def _probe(url: str, site_name: str) -> str:
    """对单个站点做轻量级 GET 探活，返回 'up' 或 'down'。"""
    # energy 为纯 IP + 自签名证书站点，跳过 SSL 验证（与适配器 verify=False 保持一致）
    verify = site_name != "energy"
    # 用浏览器 UA 探活，避免站点反爬拦截（与公告/查询适配器保持一致）
    headers = {"User-Agent": CHROME_UA}
    resp = safe_raw_get(url, site_name, timeout=_HEALTH_TIMEOUT, verify=verify, headers=headers)
    if resp is not None and resp.status_code < 400:
        return "up"
    return "down"


def _write_health(name: str, status: str) -> None:
    """将探活结果 UPSERT 写入 adapter_state，仅更新健康检查字段组。"""
    db = Database(get_db_path())
    try:
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
        status = _probe(site.base_url, site.name)
        _write_health(site.name, status)
        stats["total"] += 1
        stats[status] += 1

    # 公告适配器：国标/行标/地标共用官方平台主页地址
    for std_type, url in _ANNOUNCE_ADAPTERS.items():
        status = _probe(url, std_type)
        _write_health(std_type, status)
        stats["total"] += 1
        stats[status] += 1

    logger.info(
        "[health] 健康检查完成: total=%s up=%s down=%s",
        stats["total"],
        stats["up"],
        stats["down"],
    )
    return stats
