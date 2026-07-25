# docker/api/settings.py — 系统配置读写 API + 静态令牌管理
import logging
from datetime import datetime, timezone

from fastapi import Depends, HTTPException
from fastapi.routing import APIRouter

from docker.scheduler import update_job

from ..auth import get_static_token, refresh_static_token, require_admin
from ..manager import get_manager_dep

logger = logging.getLogger(__name__)
router = APIRouter(tags=["settings"])


@router.get("/api/settings")
def get_settings(mgr=Depends(get_manager_dep)):
    """读取当前系统配置，包括存储、扫描、查询、定时任务、外观（Windows 基线 + Docker 特有项）。"""
    from pilotstd import __version__

    cfg = mgr.cfg
    return {
        "version": __version__,
        "storage": {
            "root_dir": cfg.get("storage.root_dir", ""),
            "expire_folder": cfg.get("storage.expire_folder", "过期作废"),
            "downloads_dir": cfg.get("storage.downloads_dir", ""),
            "mirror_skipped_dirs": cfg.get("storage.mirror_skipped_dirs", True),
            "mirror_fallback": cfg.get("storage.mirror_fallback", True),
            "scan_paths": ["/inbox", "/standards"],
        },
        "organize": {"auto_clean_source": cfg.get("organize.auto_clean_source", False)},
        "file": {"clear_readonly": cfg.get("file.clear_readonly", True)},
        "network": {
            "proxy": cfg.get("network.proxy", ""),
            "ua_rotation": cfg.get("network.ua_rotation", True),
        },
        "scan": {
            "skip_folders": cfg.get("scan.skip_folders", []),
            "extensions": cfg.get("scan.extensions", []),
            "exclude_patterns": cfg.get("scan.exclude_patterns", []),
        },
        "query": {
            "site_order": cfg.get("query.site_order", []),
            "interval": (cfg.get("query.query_interval") or [0.5])[0],
            "query_interval": cfg.get("query.query_interval", [0.5, 1.5]),
            "use_cache": cfg.get("query.use_cache", True),
        },
        "tasks": {
            "auto_scan_enabled": cfg.get("tasks.auto_scan_enabled", False),
            "auto_scan_cron": cfg.get("tasks.auto_scan_cron", "0 3 * * *"),
            "auto_announce_enabled": cfg.get("tasks.auto_announce_enabled", False),
            "auto_announce_cron": cfg.get("tasks.auto_announce_cron", "0 1 * * *"),
            "date_reminder_enabled": cfg.get("tasks.date_reminder_enabled", False),
            "date_reminder_cron": cfg.get("tasks.date_reminder_cron", "0 2 * * *"),
        },
        "appearance": {
            "theme": cfg.get("appearance.theme", "经典白"),
            "language": cfg.get("appearance.language", "zh_CN"),
            "hyphen_style": cfg.get("appearance.hyphen_style", True),
            "icon_theme": cfg.get("appearance.icon_theme", "default"),
            "skip_welcome": cfg.get("appearance.skip_welcome", False),
            "column_visibility": cfg.get("appearance.column_visibility", [True] * 9),
            "login_bg": cfg.get("appearance.login_bg", ""),
        },
        "ocr": {
            "baidu_api_key": "***" if cfg.get("ocr.baidu_api_key") else "",
            "baidu_secret_key": "***" if cfg.get("ocr.baidu_secret_key") else "",
            "tencent_secret_id": "***" if cfg.get("ocr.tencent_secret_id") else "",
            "tencent_secret_key": "***" if cfg.get("ocr.tencent_secret_key") else "",
            "aliyun_access_key_id": "***" if cfg.get("ocr.aliyun_access_key_id") else "",
            "aliyun_access_key_secret": "***" if cfg.get("ocr.aliyun_access_key_secret") else "",
        },
    }


@router.put("/api/settings")
def put_settings(data: dict, mgr=Depends(get_manager_dep), user: str = Depends(require_admin)):
    """保存系统配置并更新定时任务调度。"""
    cfg = mgr.cfg
    # 只读字段：GET 返回供前端展示，但不允许通过 PUT 回写 config
    _READONLY_KEYS = {"storage.scan_paths"}
    mappings = {
        "storage": "storage",
        "organize": "organize",
        "file": "file",
        "network": "network",
        "scan": "scan",
        "query": "query",
        "tasks": "tasks",
        "appearance": "appearance",
        "ocr": "ocr",
        "announcement": "announcement",
    }
    for cat, cfg_prefix in mappings.items():
        if cat in data:
            for k, v in data[cat].items():
                # 跳过掩码后的密钥值（"***" = 保持不变）
                if v == "***":
                    continue
                if f"{cfg_prefix}.{k}" in _READONLY_KEYS:
                    continue
                cfg.set(f"{cfg_prefix}.{k}", v)
    # 同步定时任务 cron 配置到调度器
    tasks = data.get("tasks", {})
    for job_id, cron_key in [
        ("auto_scan", "auto_scan_cron"),
        ("auto_announce", "auto_announce_cron"),
        ("date_reminder", "date_reminder_cron"),
    ]:
        enabled = tasks.get(cron_key.replace("_cron", "_enabled"), False)
        cron = tasks.get(cron_key, "0 0 * * *")
        update_job(job_id, cron, enabled)
    cfg.save()
    return {"ok": True}


# ── 站点配置管理（Q15）──────────────────────────────────────────

from pydantic import BaseModel, Field


class SiteConfigUpdate(BaseModel):
    """站点限额配置更新请求体 — 窗口上限/日限额/冷却时间。"""

    max_requests: int = Field(ge=0, description="窗口查询限额")
    daily_limit: int = Field(ge=0, description="日限额")
    cooling_seconds: int = Field(ge=0, description="冷却时间（秒）")


def _build_site_config(name: str, mgr) -> dict | None:
    """聚合单个适配器的 9 字段配置。label 动态导入容错，单个适配器异常不影响整体。"""
    try:
        status = mgr.adapter_manager.get_adapter_status(name)
        remaining_quota = mgr.adapter_manager._quota.get_remaining(name) if mgr.adapter_manager._quota else 0
        cooling_remaining = (
            mgr.adapter_manager._rotator.get_cooldown_remaining(name) if mgr.adapter_manager._rotator else 0
        )

        # label 动态导入
        try:
            import importlib

            mod = importlib.import_module(f"pilotstd.query.adapters.{name}")
            label = getattr(mod, "DISPLAY_NAME", name.title())
            if not isinstance(label, str) or not label.strip():
                label = name.title()
        except Exception:
            label = name.title()

        # url 从 rotator 获取
        site_state = mgr.adapter_manager._rotator._sites.get(name) if mgr.adapter_manager._rotator else None
        url = site_state.active_url if site_state else ""
        priority = list(mgr.adapter_manager._rotator._sites.keys()).index(name) + 1 if site_state else 0
        max_requests = site_state.max_requests if site_state else 200
        cooling_seconds = site_state.cooldown_seconds if site_state else 600
        daily_limit = mgr.adapter_manager._quota._limits.get(name, 800) if mgr.adapter_manager._quota else 800

        return {
            "name": name,
            "label": label,
            "url": url,
            "priority": priority,
            "maxRequests": max_requests,
            "dailyLimit": daily_limit,
            "coolingSeconds": cooling_seconds,
            "remainingQuota": remaining_quota,
            "coolingRemaining": int(cooling_remaining),
        }
    except Exception:
        logger.warning("站点配置聚合失败: %s", name, exc_info=True)
        return None


@router.get("/api/settings/sites")
def get_sites(mgr=Depends(get_manager_dep)):
    """返回全部查询适配器的站点配置（9 字段 / 站点），单站点异常不影响整体。"""
    names = mgr.adapter_manager.list_adapters()
    sites = []
    for name in names:
        cfg = _build_site_config(name, mgr)
        if cfg:
            sites.append(cfg)
    return {"sites": sites}


@router.put("/api/settings/sites/{name}")
def put_site(name: str, data: SiteConfigUpdate, mgr=Depends(get_manager_dep)):
    """更新站点限额配置，持久化 + 内存热更新。"""
    if name not in mgr.adapter_manager.list_adapters():
        raise HTTPException(status_code=404, detail=f"适配器 {name} 不存在")

    cfg = mgr.cfg
    rotator = mgr.adapter_manager._rotator
    quota = mgr.adapter_manager._quota

    # 1. 持久化（先写 Config，失败则不更新内存）
    try:
        cfg.set(f"query.sites.{name}.window_limit", data.max_requests)
        cfg.set(f"query.sites.{name}.daily_limit", data.daily_limit)
        cfg.set(f"query.sites.{name}.cooling_seconds", data.cooling_seconds)
        cfg.save()
    except Exception as e:
        logger.exception("站点配置持久化失败: %s", name)
        raise HTTPException(status_code=500, detail=f"配置保存失败: {e}")

    # 2. 内存热更新（原子：任一失败则回滚已更新的部分）
    old_rotator = None
    old_quota = None
    try:
        if rotator and name in rotator._sites:
            old_rotator = (
                rotator._sites[name].max_requests,
                rotator._sites[name].cooldown_seconds,
            )
            rotator._sites[name].max_requests = data.max_requests
            rotator._sites[name].cooldown_seconds = data.cooling_seconds
        if quota and name in quota._limits:
            old_quota = quota._limits[name]
            quota._limits[name] = data.daily_limit
    except Exception as e:
        # 回滚内存
        if old_rotator and rotator:
            rotator._sites[name].max_requests = old_rotator[0]
            rotator._sites[name].cooldown_seconds = old_rotator[1]
        if old_quota is not None and quota:
            quota._limits[name] = old_quota
        logger.exception("站点内存热更新失败: %s", name)
        raise HTTPException(status_code=500, detail=f"热更新失败: {e}")

    # 返回更新后的完整配置
    updated = _build_site_config(name, mgr)
    return {"success": True, "site": updated}


# ── 静态令牌管理 ──────────────────────────────────────────────────


@router.get("/api/settings/token")
def get_token(user: str = Depends(require_admin)):
    """返回当前静态 API 令牌值（仅管理员）。"""
    return {"token": get_static_token()}


@router.post("/api/settings/token/refresh")
def refresh_token(user: str = Depends(require_admin)):
    """重新生成静态令牌（立即生效，旧令牌立即失效）。

    刷新后刷新数据库 api_keys 表的 pst_static 记录 +
    内存缓存 + 环境变量 PILOTSTD_API_TOKEN。
    """
    new_token = refresh_static_token()
    now_iso = datetime.now(timezone.utc).isoformat()
    logger.info("静态令牌已刷新")
    return {"token": new_token, "refreshed_at": now_iso}


# ── 配置 Schema（单一数据源）─────────────────────────────────────


@router.get("/api/settings/schema")
def get_schema():
    """返回配置 Schema——按 Tab 分组的完整字段定义。

    前端可据此动态渲染表单，无需手写每个 Tab 组件。
    """
    from pilotstd.core.config.settings_schema import get_schema_by_tab

    return {"tabs": get_schema_by_tab()}
