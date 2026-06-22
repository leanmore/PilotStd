# pilotstd/download/adapters/mock.py
# 模拟下载适配器（用于 UI 调试，后续替换为真实网站适配器）

import random
from typing import Optional

from pilotstd.download.adapters.base import BaseDownloadAdapter
from pilotstd.download.models import DownloadTask


class MockDownloadAdapter(BaseDownloadAdapter):
    """模拟下载适配器，生成虚拟 PDF 内容。80% 成功率。"""

    @property
    def site_name(self) -> str:
        return "mock_download"

    def can_handle(self, task: DownloadTask) -> bool:
        return True

    def download(self, task: DownloadTask) -> Optional[bytes]:
        if random.random() > 0.8:
            task.error_message = "模拟网络错误"
            return None
        return f"%PDF-1.4\n% 模拟内容: {task.standard_number}\n".encode("utf-8")
