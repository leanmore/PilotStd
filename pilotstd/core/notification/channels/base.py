# 模块：项目/核心//渠道/脚本
"""渠道抽象基类（v1.1 R2，MoviePilot 风格）——所有通知渠道的统一契约。

设计要点：
- send(): 发送通知（失败填充 last_error 供管理层写入发送日志）
- test(): 发送测试消息验证连通性（供配置页"测试连接"使用）
- name: 渠道唯一标识（telegram/wechat/dingtalk/feishu，与 _CHANNEL_CLASSES 键一致）
- get_config_schema(): 渠道配置字段 schema（供前端动态渲染配置表单）
- 配置以 DB（user_credentials，经 CredentialHelper）为唯一真实数据源（SSOT）；
  config.json 仅作一次性显式迁移源（migrate_from_config_if_empty），运行时不再读取

与 channel.py 中旧 NotificationChannel 的关系：本类为规范基类（v1.1 R2），
channel.py 旧基类保留仅为公共导出兼容（__init__.py），不再被任何渠道继承。
"""

from abc import ABC, abstractmethod
from typing import Any

from ..channel import NotificationMessage


class NotificationChannel(ABC):
    """通知渠道抽象基类。"""

    def __init__(self) -> None:
        # 错误详情透传：发送失败时由子类填充具体原因供管理层读取
        self.last_error: str = ""

    @abstractmethod
    def send(self, message: NotificationMessage) -> bool:
        """发送通知，成功返回真；失败返回假并应填充 last_error 属性。"""

    @abstractmethod
    def test(self) -> bool:
        """发送一条测试消息验证渠道连通性，返回是否发送成功。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """渠道唯一标识（与 _CHANNEL_CLASSES 键一致）。"""

    @abstractmethod
    def get_config_schema(self) -> dict[str, Any]:
        """渠道配置字段 schema，供前端动态渲染配置表单。"""

    @staticmethod
    def validate_config(config: dict) -> bool:
        """验证渠道配置是否完整。子类可覆盖。"""
        return True
