# docker/api/settings.py — 系统配置读写 API + 静态令牌管理
import logging
from datetime import datetime, timezone

from fastapi import Depends
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
                cfg.set(f"{cfg_prefix}.{k}", v)
    # 同步定时任务 cron 配置到调度器
    tasks = data.get("tasks", {})
    for job_id, cron_key in [
        ("auto_scan", "auto_scan_cron"),
        ("auto_announce", "auto_announce_cron"),
    ]:
        enabled = tasks.get(cron_key.replace("_cron", "_enabled"), False)
        cron = tasks.get(cron_key, "0 0 * * *")
        update_job(job_id, cron, enabled)
    cfg.save()
    return {"ok": True}


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
