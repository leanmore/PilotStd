# pilotstd/core/notification/_message_builders.py
# 通知消息构建器混入 — 门面类，聚合三个分类 mixin


from ._builders_batch import _BatchBuildersMixin
from ._builders_system import _SystemBuildersMixin
from ._builders_validity import _ValidityBuildersMixin


def _make_link(standard_number: str | None) -> str | None:
    """根据标准号生成跳转链接。"""
    return f"/standards/{standard_number}" if standard_number else None


class MessageBuildersMixin(_ValidityBuildersMixin, _BatchBuildersMixin, _SystemBuildersMixin):
    """事件消息构建器方法集合（混入 NotificationManager）。

    有效性检查构建器: _ValidityBuildersMixin
    批次/查询/下载构建器: _BatchBuildersMixin
    系统/备份/错误构建器: _SystemBuildersMixin
    """

    # 所有 _build_*_message 方法均由三个父类 mixin 提供
    pass
