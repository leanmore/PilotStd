# 应用版本号——唯一真相来源（持续集成、更新检查、打包均从此读取）

import os
from typing import Any

# 轻量数据模型（启动时需用）
from .models import FileInfo, ParsedStdInfo, ScanResult, ScanStats
from .scan import FileScanner, StandardParser

__version__ = "0.111.1"
FRONTEND_VERSION = __version__  # 与后端保持一致，更新脚本据此下载前端 dist.zip
SUPERUSER_USERNAME = os.getenv("SUPERUSER")  # 超级管理员用户名（权限判断唯一依据，须通过环境变量显式设置）
ADMIN_ROLE = "admin"  # 内部角色标识符（与 SUPERUSER_USERNAME 无关，前者是用户名，后者是角色名）
# 启动校验已迁移至应用入口（容器/脚本+入口脚本），避免_脚本导入时触发

__all__ = [
    "ParsedStdInfo",
    "FileInfo",
    "ScanResult",
    "ScanStats",
    "FileScanner",
    "StandardParser",
    "__version__",
]


# 延迟导入（其依赖查询/下载引擎和全部适配器）
def get_manager() -> type[Any]:
    """懒加载 StandardManager 类（避免启动时导入全部查询/下载引擎依赖）。"""
    from .manager import StandardManager

    return StandardManager
