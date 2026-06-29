# pilotstd/manager/organize/__init__.py
# 归类服务 — 从 organizer_service.py 拆分为 4 个子模块

from ._utils import _is_word_or_template, _resolve_industry_in_path
from .expire import OrganizerExpireMixin
from .mirror import OrganizerMirrorMixin
from .organizer import OrganizerCore


class OrganizerService(OrganizerCore, OrganizerMirrorMixin, OrganizerExpireMixin):
    """归类服务：将标准文件按代号/名称归类到标准库目录。"""

    _is_word_or_template = staticmethod(_is_word_or_template)
    _resolve_industry_in_path = staticmethod(_resolve_industry_in_path)


__all__ = ["OrganizerService"]
