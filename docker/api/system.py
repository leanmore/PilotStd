# docker/api/system.py — 系统管理 API（版本信息、自更新、重启、资源监控）
import json
import logging
import os
import subprocess
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from pilotstd import __version__

from ..manager import get_manager_dep

router = APIRouter(prefix="/api/system", tags=["system"])
logger = logging.getLogger(__name__)

IMAGE_REGISTRY = "ghcr.io/leanmore/pilotstd"
IMAGE_LATEST = f"{IMAGE_REGISTRY}:latest"
IMAGE_VERSIONED = f"{IMAGE_REGISTRY}:v{__version__}"


def _get_container_id() -> str:
    """读取当前容器的 ID（从 /proc/self/cgroup 或 HOSTNAME 环境变量）。"""
    try:
        with open("/proc/self/cgroup") as f:
            for line in f:
                if "docker" in line or "containerd" in line:
                    return line.strip().split("/")[-1][:12]
    except Exception:
        pass
    return os.environ.get("HOSTNAME", os.environ.get("CONTAINER_NAME", ""))


def _run_docker(args: list, timeout: int = 120) -> subprocess.CompletedProcess:
    """执行 docker 命令，docker.sock 未挂载时提前报错。"""
    if not os.path.exists("/var/run/docker.sock"):
        raise RuntimeError("docker.sock 未挂载，无法执行容器管理操作")
    return subprocess.run(
        ["docker"] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


@router.get("/version")
async def get_version():
    """返回当前版本和容器信息。"""
    cid = ""
    try:
        cid = _get_container_id()
    except Exception:
        pass
    return {
        "version": __version__,
        "tag": f"v{__version__}",
        "container_id": cid,
        "image": IMAGE_VERSIONED,
        "image_latest": IMAGE_LATEST,
    }


@router.post("/update")
async def update_container():
    """拉取最新镜像并检查是否有更新。需挂载 /var/run/docker.sock。

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
        # 1. 查当前镜像 digest
        inspect = _run_docker(["inspect", cid])
        info = json.loads(inspect.stdout)[0]
        old_image = info.get("Image", "")
        old_digest = ""
        try:
            img_inspect = _run_docker(["image", "inspect", old_image, "--format", "{{.RepoDigests}}"])
            old_digest = img_inspect.stdout.strip()
        except Exception:
            pass

        # 2. 拉取最新镜像
        pull = _run_docker(["pull", IMAGE_LATEST], timeout=300)
        pulled_layers = [line for line in pull.stdout.split("\n") if "Downloaded" in line or "Pulled" in line]

        # 3. 比较
        new_inspect = _run_docker(["image", "inspect", IMAGE_LATEST, "--format", "{{.RepoDigests}}"])
        new_digest = new_inspect.stdout.strip()

        if new_digest and old_digest and new_digest == old_digest:
            return {
                "updated": False,
                "message": "已是最新版本",
                "version": __version__,
                "digest": new_digest[:80],
            }

        # 4. 有新版本 → 重启容器
        logger.info("检测到新镜像: %s → %s", old_digest[:80], new_digest[:80])
        if pulled_layers:
            logger.info("拉取的新层: %s", pulled_layers)

        # 仅支持 compose 重建（docker restart 不会应用新镜像）
        compose_file = os.environ.get("COMPOSE_FILE", "")
        compose_project = os.environ.get("COMPOSE_PROJECT_NAME", "")

        restart_ok = False
        if compose_file and os.path.exists(compose_file):
            try:
                _run_docker(
                    [
                        "compose",
                        "-f",
                        compose_file,
                        "-p",
                        compose_project,
                        "up",
                        "-d",
                        "--force-recreate",
                    ],
                    timeout=120,
                )
                restart_ok = True
            except Exception as e:
                logger.warning("compose 重启失败: %s", e)

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

    except subprocess.TimeoutExpired:
        raise HTTPException(504, "docker pull 超时")
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        logger.error("自更新失败: %s", e)
        raise HTTPException(500, f"更新失败: {e}")


@router.get("/health")
def system_health(mgr=Depends(get_manager_dep)):
    """系统健康检查。

    检查项：数据库连接、缓存状态、适配器总数/可用数。
    始终返回 200，通过 ok 字段指示整体健康状态。
    """
    from datetime import datetime

    result: dict = {"ok": True, "timestamp": datetime.now().isoformat()}

    # 1. 数据库连接
    try:
        mgr.db.fetchone("SELECT 1")
        result["database"] = "ok"
    except Exception as e:
        result["database"] = f"error: {e}"
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
def system_resources():
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
