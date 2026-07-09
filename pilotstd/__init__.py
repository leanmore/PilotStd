# 应用版本号——唯一真相来源（CI、更新检查、打包均从此读取）

import os
from typing import Any

# 轻量数据模型（启动时需用）
from .models import FileInfo, ParsedStdInfo, ScanResult, ScanStats
from .scan import FileScanner, StandardParser

__version__ = "0.62.1"
FRONTEND_VERSION = __version__  # 与后端保持一致，更新脚本据此下载前端 dist.zip
SUPERUSER_USERNAME = os.getenv("SUPERUSER")  # 超级管理员用户名（权限判断唯一依据，须通过环境变量显式设置）
# 启动校验已迁移至应用入口（docker/app.py lifespan + main.py），避免 bump_version.py 导入时触发

__all__ = [
    "ParsedStdInfo",
    "FileInfo",
    "ScanResult",
    "ScanStats",
    "FileScanner",
    "StandardParser",
    "__version__",
]


# StandardManager 延迟导入（其依赖 query/download 引擎和全部适配器）
def get_manager() -> type[Any]:
    from .manager import StandardManager

    return StandardManager
