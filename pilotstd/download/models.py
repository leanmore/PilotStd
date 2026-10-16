# 模块：项目/下载/模型脚本
# 下载任务数据模型

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

# 采标标准（版权受限）跳过口径：调用方据此识别"业务终态"而非可重试失败，
# 统一引用本常量，避免各层各自拼字符串导致判定失配。
# ⚠️ 定义在 models（叶子模块）而非 engine：下载适配器自身也要用它（openstd 的
# "采"标记判定），若从 engine 反向导入会构成循环导入。
# i18n-allow: 下载链路业务终态文案，进 API error 字段且各层按文本判定（翻译即失效）
ADOPTED_SKIP_MESSAGE = "采标标准，版权受限，自动跳过"


class DownloadStatus(Enum):
    """下载任务状态枚举：待处理、运行中、成功、失败、跳过、重试中。"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"  # 采标受限等
    RETRYING = "retrying"


@dataclass
class DownloadTask:
    """单个下载任务"""

    standard_number: str  # 标准完整编号
    download_url: str = ""  # 下载直链
    source_site: str = ""  # 来源网站标识
    query_result: Optional[object] = None  # 关联的 QueryResult（含标准名、采标状态等）

    status: DownloadStatus = DownloadStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    error_message: str = ""
    saved_path: str = ""  # 下载后本地路径

    # 供适配器使用的临时数据
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchDownloadStats:
    """批量下载统计"""

    total: int = 0
    success: int = 0
    failed: int = 0
    skipped_adopted: int = 0  # 采标跳过
    skipped_exists: int = 0  # 文件已存在跳过
    errors: int = 0
    # 通知聚合 B1-1：批量下载的**逐条失败明细**（4 列口径：standard_number / standard_name /
    # error_type / error_message）。默认空列表 = 现状语义，供 `batch_download_complete` 的
    # payload（G-045 契约要求声明的 key 必须由生产者提供）与聚合渲染使用。
    failed_items: list[dict[str, str]] = field(default_factory=list)
