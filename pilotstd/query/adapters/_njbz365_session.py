# pilotstd/query/adapters/_njbz365_session.py
# 已迁移至 _njbz365_session_manager.py
# 保留 _PRIVATE_KEY 导出兼容旧测试

from ._njbz365_session_manager import Njz365SessionManager, _PRIVATE_KEY

_Njbz365SessionMixin = Njz365SessionManager  # 兼容旧代码的别名
