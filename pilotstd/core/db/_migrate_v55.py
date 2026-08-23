# 模块：项目/核心/数据库/迁移_v55脚本
# v55：为 Key 指纹校验做准备（仅推进版本号，不解密或修改任何现有数据）
# 设计：版本号由迁移框架自动写入版本记录表，本函数仅作为占位迁移，
#      保证 schema 版本推进到 55（指纹逻辑在凭据层惰性执行）。

from typing import Any

from ._constants import migration


@migration(55)
def _migrate_v55_credential_fingerprint_ready(db: Any) -> None:
    """推进 schema 版本至 55，为凭据指纹校验做准备（幂等空操作）。"""
    # 版本号由迁移框架自动写入版本记录表，此处无需手动操作
    pass
