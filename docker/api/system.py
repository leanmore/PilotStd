# 容器//脚本—系统管理接口（版本信息、自更新、重启、资源监控）
import json
import logging
import os
import subprocess
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from pilotstd import __version__

from ..auth import require_role
from ..manager import get_manager_dep

router = APIRouter(prefix="/api/system", tags=["system"])
logger = logging.getLogger(__name__)

# 镜像仓库地址常量
IMAGE_REGISTRY = "ghcr.io/leanmore/pilotstd"
IMAGE_LATEST = f"{IMAGE_REGISTRY}:latest"
IMAGE_VERSIONED = f"{IMAGE_REGISTRY}:v{__version__}"


def _get_image_tag() -> str:
    """返回拉取时使用的镜像标签，优先版本号标签，异常时降级 latest。"""
    if __version__ and __version__ != "0.0.0":
        tag = IMAGE_VERSIONED
    else:
        tag = IMAGE_LATEST
        logger.warning("__version__ 无效 (%s)，降级使用 latest 标签", __version__)
    return tag


def _get_container_id() -> str:
    """读取当前容器的 ID（从 /proc/self/cgroup 或 HOSTNAME 环境变量）。"""
    try:
        with open("/proc/self/cgroup") as f:
            for line in f:
                # 容器行包含"容器"或""关键字
                if "docker" in line or "containerd" in line:
                    return line.strip().split("/")[-1][:12]
    except Exception as e:
        logger.warning("获取容器 ID 失败: %s", e)
    return os.environ.get("HOSTNAME", os.environ.get("CONTAINER_NAME", ""))


def _run_docker(args: list, timeout: int = 120) -> subprocess.CompletedProcess:
    """执行 docker 命令，docker.sock 未挂载时提前报错。"""
    # 未挂载容器.时提前报错，避免后续超时等待
    if not os.path.exists("/var/run/docker.sock"):
        raise RuntimeError("docker.sock 未挂载，无法执行容器管理操作")
    return subprocess.run(
        ["docker"] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


@router.get("/version")
async def get_version(request: Request):
    """返回当前版本和镜像信息（公开接口）。

    SEC-001: 移除 @require_role（版本号是登录页/系统状态卡片的基础信息），
    并从返回值移除 container_id（容器 ID 是容器逃逸攻击的辅助信息，前端不使用）。
    """
    return {
        "version": __version__,
        "tag": f"v{__version__}",
        "image": IMAGE_VERSIONED,
        "image_latest": IMAGE_LATEST,
    }


def _get_current_digest(cid: str) -> str:
    """获取容器当前镜像的 RepoDigest，失败返回空字符串。"""
    # 容器获取容器元数据→从中提取
    inspect = _run_docker(["inspect", cid])
    info = json.loads(inspect.stdout)[0]
    old_image = info.get("Image", "")
    old_digest = ""
    try:
        # 查询镜像的（含256哈希）
        img_inspect = _run_docker(["image", "inspect", old_image, "--format", "{{.RepoDigests}}"])
        old_digest = img_inspect.stdout.strip()
    except Exception as e:
        logger.warning("Docker 镜像检查失败: %s", e)
    return old_digest


def _pull_and_compare(old_digest: str) -> tuple[str, bool]:
    """拉取版本号标签镜像并比对 digest，返回 (new_digest, needs_update)。"""
    tag = _get_image_tag()
    logger.info("拉取镜像: %s", tag)
    pull = _run_docker(["pull", tag], timeout=300)
    pulled_layers = [line for line in pull.stdout.split("\n") if "Downloaded" in line or "Pulled" in line]
    if pulled_layers:
        logger.info("拉取的新层: %s", pulled_layers)
    new_inspect = _run_docker(["image", "inspect", tag, "--format", "{{.RepoDigests}}"])
    new_digest = new_inspect.stdout.strip()
    needs_update = not (new_digest and old_digest and new_digest == old_digest)
    return new_digest, needs_update


def _restart_via_compose() -> bool:
    """执行 docker compose up -d 重建容器，返回是否成功。"""
    compose_file = os.environ.get("COMPOSE_FILE", "")
    compose_project = os.environ.get("COMPOSE_PROJECT_NAME", "")
    if not compose_file or not os.path.exists(compose_file):
        return False
    try:
        _run_docker(
            ["compose", "-f", compose_file, "-p", compose_project, "up", "-d", "--force-recreate"],
            timeout=120,
        )
        return True
    except Exception as e:
        logger.warning("compose 重启失败: %s", e)
        return False


def _build_update_response(restart_ok: bool, old_digest: str, new_digest: str) -> dict:
    """构造更新响应体（已检测到新版本时调用）。"""
    return {
        "updated": True,
        "restarted": restart_ok,
        "method": "compose" if restart_ok else "",
        "message": (
            "已拉取并应用更新"
            if restart_ok
            else "已拉取新镜像，但需要 compose 配置才能重建容器。"
            "请设置 COMPOSE_FILE 环境变量后重试，或手动执行 docker compose up -d"
        ),
        "old_digest": old_digest[:80] if old_digest else "",
        "new_digest": new_digest[:80] if new_digest else "",
    }


def _notify_update_failed(mgr: Any, error: str) -> None:
    """镜像更新检查失败时发送通知（静默失败）。"""
    try:
        if hasattr(mgr, "notification_mgr") and mgr.notification_mgr:
            mgr.notification_mgr.send_event(
                "image_update_available",
                {"error": error},
            )
    except Exception:
        pass


@router.post("/update")
@require_role("admin")
async def update_container(request: Request, mgr=Depends(get_manager_dep)):
    """拉取最新镜像并检查是否有更新（仅管理员）。需挂载 /var/run/docker.sock。

    流程：
      1. 获取当前容器使用的镜像 digest
      2. docker pull 最新镜像
      3. 比较 digest → 有变化则尝试重启容器
      4. 返回更新状态

    注意：容器重启后此请求不会收到 HTTP 响应，前端应设超时处理。
    """
    cid = _get_container_id()
    if not cid:
        raise HTTPException(500, "无法获取容器 ID，请设置 HOSTNAME 环境变量")

    try:
        old_digest = _get_current_digest(cid)
        new_digest, needs_update = _pull_and_compare(old_digest)
        if not needs_update:
            return {
                "updated": False,
                "message": "已是最新版本",
                "version": __version__,
                "digest": new_digest[:80],
            }

        logger.info("检测到新镜像: %s → %s", old_digest[:80], new_digest[:80])
        restart_ok = _restart_via_compose()
        # 镜像更新通知(1.7)
        try:
            if hasattr(mgr, "notification_mgr"):
                mgr.notification_mgr.send_event(
                    "image_update_available", {"old_digest": old_digest, "new_digest": new_digest}
                )
        except Exception:
            pass
        return _build_update_response(restart_ok, old_digest, new_digest)
    except subprocess.TimeoutExpired:
        _notify_update_failed(mgr, "docker pull 超时")
        raise HTTPException(504, "docker pull 超时")
    except RuntimeError as e:
        _notify_update_failed(mgr, str(e))
        raise HTTPException(503, str(e))
    except Exception as e:
        logger.error("自更新失败: %s", e)
        _notify_update_failed(mgr, str(e))
        raise HTTPException(500, f"更新失败: {e}")


@router.get("/health")
@require_role("admin")
def system_health(request: Request, mgr=Depends(get_manager_dep)) -> dict:
    """系统健康检查。

    检查项：数据库连接、缓存状态、适配器总数/可用数。
    始终返回 200，通过 ok 字段指示整体健康状态。
    """
    from datetime import datetime

    result: dict = {"ok": True, "timestamp": datetime.now().isoformat()}

    # 1. 数据库连接
    status = mgr.system_service.get_status()
    if status["db_connected"]:
        result["database"] = "ok"
    else:
        result["database"] = "error"
        result["ok"] = False

    # 2. 缓存状态
    try:
        from pilotstd.core.cache_manager import CacheManager

        CacheManager(mgr.db)
        result["cache"] = "ok"
    except Exception as e:
        result["cache"] = f"error: {e}"
        result["ok"] = False

    # 3. 适配器状态
    try:
        if hasattr(mgr, "adapter_manager"):
            adapters = mgr.adapter_manager.list_adapters()
            available = 0
            for a in adapters:
                status = mgr.adapter_manager.get_adapter_status(a)
                if status.get("status") == "normal":
                    available += 1
            result["adapters"] = {"count": len(adapters), "available": available}
        else:
            result["adapters"] = "未初始化"
            result["ok"] = False
    except Exception as e:
        result["adapters"] = f"error: {e}"
        result["ok"] = False

    return result


@router.get("/resources")
@require_role("admin")
def system_resources(request: Request):
    """获取系统资源使用情况。"""
    try:
        import psutil  # type: ignore[import-untyped]

        return {
            "cpu": {"percent": psutil.cpu_percent(interval=0.3), "count": psutil.cpu_count()},
            "memory": {
                "total": psutil.virtual_memory().total,
                "available": psutil.virtual_memory().available,
                "percent": psutil.virtual_memory().percent,
            },
            "disk": {
                "total": psutil.disk_usage("/").total,
                "used": psutil.disk_usage("/").used,
                "free": psutil.disk_usage("/").free,
                "percent": psutil.disk_usage("/").percent,
            },
            "timestamp": datetime.now().isoformat(),
        }
    except ImportError:
        return {"error": "psutil 未安装"}
