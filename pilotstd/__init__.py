# 应用版本号——唯一真相来源（CI、更新检查、打包均从此读取）

from typing import Any

# 轻量数据模型（启动时需用）
from .models import FileInfo, ParsedStdInfo, ScanResult, ScanStats
from .scan import FileScanner, StandardParser

__version__ = "0.35.0"
FRONTEND_VERSION = __version__  # 与后端保持一致，更新脚本据此下载前端 dist.zip

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
