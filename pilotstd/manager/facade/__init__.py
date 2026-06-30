# pilotstd/manager/facade/__init__.py
# StandardManager — 业务逻辑门面，统一 API 封装扫描→查询→下载→归类完整流程

from ._auto import AutoMixin
from ._base import BaseFacade
from ._download import DownloadMixin
from ._file_index import FileIndexMixin
from ._organize import OrganizeMixin
from ._query import QueryMixin
from ._scan import ScanMixin


class StandardManager(
    BaseFacade,
    ScanMixin,
    QueryMixin,
    DownloadMixin,
    OrganizeMixin,
    AutoMixin,
    FileIndexMixin,
):
    """标准管理统一 API — 业务逻辑门面。

    封装扫描→查询→下载→归类的完整流水线，
    同时管理所有子系统（配置、数据库、适配器、缓存、任务队列）的生命周期。
    """


__all__ = ["StandardManager"]
