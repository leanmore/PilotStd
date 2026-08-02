"""UI 状态管理 Handler — 组合模式替代 Mixin 多重继承。

存活 Handler（由 MainWindowCore._init_all_handlers 实例化）:
  AnnounceUIHandler  (_announce.py)     — 公告检查
  ArchiveUIHandler   (_archive.py)      — 归档操作
  AutoUIHandler      (_auto.py)         — 自动流水线
  CleanupHandler     (_cleanup.py)      — 清理/去重
  DownloadUIHandler  (_download.py)     — 下载管理
  PersistenceHandler (_persistence.py)  — 序列化/反序列化
  ProjectHandler     (_project.py)      — 项目文件 I/O
  QueryUIHandler     (_query.py)        — 查询引擎交互
  QuerySummaryHandler(_query_summary.py) — 查询结果汇总
  ScanUIHandler      (_scan.py)         — 文件扫描
  SettingsHandler    (_settings.py)     — 设置页管理
  SettingsConfigIO   (_settings_io.py)  — 配置持久化

FlowEngine（纯逻辑，零 Qt 依赖，共 14 个）:
  actions / announce / archive / archive_worker_factory / auto / cleanup
  download / persistence / project / protocols / query / query_summary
  query_worker_factory / scan / settings_io

已删除（2026-08-02 Phase 1+2，-3323 行，-67%）:
  _dialog / _export / _file_dialog / _file_tree / _table / _table_helper
  _theme / _ui_layout / _ui_setup / *_flow_engine (C 组 5 个)
"""

from ._cleanup import CleanupHandler
from ._persistence import PersistenceHandler
from ._project import ProjectHandler
from ._settings import SettingsHandler

__all__ = [
    "CleanupHandler",
    "PersistenceHandler",
    "ProjectHandler",
    "SettingsHandler",
]
