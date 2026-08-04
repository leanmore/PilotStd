# 项目/下载/适配器/脚本—下载适配器抽象基类
# 所有下载网站适配器的基类，定义统一接口。
# 分隔
# 如何新增一个下载适配器：
# 1.继承
# 2.实现_属性（返回唯一标识，如"_"）
# 3.实现_()——检查._==._返回
# 4.实现下载()——返回[]，失败时设置._
# 5.如需额外参数（如），通过.字典传递，在适配器文档字符串中说明
# 6.在构造时传入适配器实例（含）
# 7.适配器负责管理自身的请求头、、验证码等逻辑
# 分隔
# .约定：
# "":—标准唯一（下载需要，取自查询结果）
#   - 其他键由各适配器自行定义

from abc import ABC, abstractmethod
from typing import Optional

import requests

from ..models import DownloadTask


class BaseDownloadAdapter(ABC):
    """所有下载网站适配器的抽象基类。"""

    def __init__(self, session: Optional[requests.Session] = None):
        self._session = session or requests.Session()

    @property
    @abstractmethod
    def site_name(self) -> str:
        """网站唯一标识，用于引擎路由和 can_handle 匹配。"""
        ...

    @abstractmethod
    def can_handle(self, task: DownloadTask) -> bool:
        """判断此适配器能否处理该下载任务。
        实现时应检查 task.source_site 是否等于 self.site_name，
        或根据标准号特征判断（如特定前缀）。
        """
        ...

    @abstractmethod
    def download(self, task: DownloadTask) -> Optional[bytes]:
        """执行下载，返回文件字节内容；失败返回 None 并在 task.error_message 中记录原因。"""
        ...
