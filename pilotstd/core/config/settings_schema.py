# 模块：项目/核心/配置/_表结构脚本
"""配置 Schema 注册表 —— 单一数据源（SSOT）。

所有可配置项的元数据集中定义于此。
前端可请求 GET /api/settings/schema 获取完整 schema，按 tab 分组动态渲染表单。
新增配置项只需在 SCHEMA 中加一条记录，无需修改前后端任何其他文件。
"""

from dataclasses import dataclass, field
from typing import Any

# 控件类型：前端根据此字段选择渲染的用户界面组件
FIELD_INPUT = "input"  # <input> 文本框
FIELD_PASSWORD = "password"  # <input type="password">
FIELD_SELECT = "select"  # <select> 下拉（options 必填）
FIELD_TOGGLE = "toggle"  # 开关组件
FIELD_NUMBER = "number"  # <input type="number">
FIELD_TAGS = "tags"  # 逗号分隔标签输入
FIELD_TIME = "time"  # 时间选择器
FIELD_CRON = "cron"  # cron 表达式输入


@dataclass
class SettingDef:
    """单个配置项的元数据。"""

    key: str  # 配置键名（如 "storage.root_dir"）
    tab: str  # 所属 Tab（"storage"/"network"/"query"/"scan"/"ui"/"ocr"）
    field_type: str = FIELD_INPUT  # 控件类型
    default: Any = ""  # 默认值
    placeholder: str = ""  # 占位提示
    options: list[dict[str, Any]] = field(default_factory=list)  # SELECT 的选项
    help_text: str = ""  # 辅助说明
    required: bool = False  # 是否必填


# ──完整配置──

SCHEMA: list[SettingDef] = [
    # ──存储──
    SettingDef(
        key="storage.root_dir",
        tab="storage",
        field_type=FIELD_INPUT,
        default="",
        placeholder="~/标准",
        help_text="标准文件的本地存储根目录",
    ),
    SettingDef(
        key="storage.expire_folder",
        tab="storage",
        field_type=FIELD_INPUT,
        default="过期作废",
        placeholder="过期作废",
        help_text="过期标准的归档文件夹名",
    ),
    SettingDef(
        key="storage.downloads_dir",
        tab="storage",
        field_type=FIELD_INPUT,
        default="",
        placeholder="默认同标准库",
        help_text="下载文件存放目录，留空则使用标准库目录",
    ),
    SettingDef(
        key="organize.auto_clean_source",
        tab="storage",
        field_type=FIELD_TOGGLE,
        default=False,
        help_text="归档后自动清理源文件",
    ),
    SettingDef(
        key="file.clear_readonly",
        tab="storage",
        field_type=FIELD_TOGGLE,
        default=True,
        help_text="自动清理文件的只读属性",
    ),
    SettingDef(
        key="tasks.auto_scan_enabled",
        tab="tasks",
        field_type=FIELD_TOGGLE,
        default=False,
        help_text="定时自动扫描标准库目录，解析文件名中的标准号",
    ),
    SettingDef(
        key="tasks.auto_scan_cron",
        tab="tasks",
        field_type=FIELD_CRON,
        default="0 3 * * *",
        placeholder="0 3 * * *",
        help_text="定时扫描的 cron 表达式",
    ),
    # ──网络──
    SettingDef(
        key="network.proxy",
        tab="network",
        field_type=FIELD_INPUT,
        default="",
        placeholder="http://127.0.0.1:8080",
        help_text="HTTP 代理地址，留空表示直连",
    ),
    SettingDef(
        key="network.ua_rotation",
        tab="network",
        field_type=FIELD_TOGGLE,
        default=True,
        help_text="启用 User-Agent 轮转，降低反爬检测风险",
    ),
    # ──查询──
    SettingDef(
        key="query.query_interval",
        tab="query",
        field_type=FIELD_NUMBER,
        default=[0.5, 1.5],
        help_text="查询请求间隔范围（秒），输入最小值，最大值保持不变",
    ),
    SettingDef(
        key="query.use_cache",
        tab="query",
        field_type=FIELD_TOGGLE,
        default=True,
        help_text="启用查询结果缓存，减少重复请求",
    ),
    # ──扫描──
    SettingDef(
        key="scan.skip_folders",
        tab="scan",
        field_type=FIELD_TAGS,
        default=[],
        placeholder="过期作废",
        help_text="扫描时跳过的文件夹名，逗号分隔",
    ),
    SettingDef(
        key="scan.extensions",
        tab="scan",
        field_type=FIELD_TAGS,
        default=[".pdf", ".doc", ".docx", ".txt"],
        placeholder=".pdf, .doc, .docx",
        help_text="扫描时关注的文件扩展名，逗号分隔",
    ),
    SettingDef(
        key="scan.exclude_patterns",
        tab="scan",
        field_type=FIELD_TAGS,
        default=[],
        placeholder="~$",
        help_text="文件名包含这些关键词时跳过扫描",
    ),
    # ──界面──
    SettingDef(
        key="appearance.login_bg",
        tab="ui",
        field_type=FIELD_INPUT,
        default="",
        placeholder="https://... 或留空使用默认",
        help_text="登录页背景图 URL 或上传图片",
    ),
    SettingDef(
        key="tasks.auto_announce_enabled",
        tab="tasks",
        field_type=FIELD_TOGGLE,
        default=False,
        help_text="定时自动检查标准公告更新",
    ),
    SettingDef(
        key="tasks.auto_announce_cron",
        tab="tasks",
        field_type=FIELD_CRON,
        default="0 1 * * *",
        placeholder="0 1 * * *",
        help_text="定时公告检查的 cron 表达式",
    ),
    SettingDef(
        key="tasks.date_reminder_enabled",
        tab="tasks",
        field_type=FIELD_TOGGLE,
        default=False,
        help_text="标准实施日期到期提醒（30/15/7/0天前推送）",
    ),
    SettingDef(
        key="tasks.date_reminder_cron",
        tab="tasks",
        field_type=FIELD_CRON,
        default="0 2 * * *",
        placeholder="0 2 * * *",
        help_text="日期提醒的 cron 表达式",
    ),
    SettingDef(
        key="tasks.auto_health_check_enabled",
        tab="tasks",
        field_type=FIELD_TOGGLE,
        default=True,
        help_text="定时对查询/公告适配器做轻量级健康检查",
    ),
    SettingDef(
        key="tasks.auto_health_check_cron",
        tab="tasks",
        field_type=FIELD_CRON,
        default="0 * * * *",
        placeholder="0 * * * *",
        help_text="健康检查的 cron 表达式",
    ),
    # 说明：──文字识别──
    SettingDef(
        key="ocr.baidu_api_key",
        tab="ocr",
        field_type=FIELD_PASSWORD,
        default="",
        placeholder="百度云 API Key",
        help_text="百度云 OCR API Key（有免费额度）",
    ),
    SettingDef(
        key="ocr.baidu_secret_key",
        tab="ocr",
        field_type=FIELD_PASSWORD,
        default="",
        placeholder="百度云 Secret Key",
        help_text="百度云 OCR Secret Key",
    ),
    SettingDef(
        key="ocr.tencent_secret_id",
        tab="ocr",
        field_type=FIELD_PASSWORD,
        default="",
        placeholder="腾讯云 Secret ID",
        help_text="腾讯云 OCR Secret ID（有免费额度）",
    ),
    SettingDef(
        key="ocr.tencent_secret_key",
        tab="ocr",
        field_type=FIELD_PASSWORD,
        default="",
        placeholder="腾讯云 Secret Key",
        help_text="腾讯云 OCR Secret Key",
    ),
    SettingDef(
        key="ocr.aliyun_access_key_id",
        tab="ocr",
        field_type=FIELD_PASSWORD,
        default="",
        placeholder="阿里云 Access Key ID",
        help_text="阿里云 OCR Access Key ID（应急备用）",
    ),
    SettingDef(
        key="ocr.aliyun_access_key_secret",
        tab="ocr",
        field_type=FIELD_PASSWORD,
        default="",
        placeholder="阿里云 Access Key Secret",
        help_text="阿里云 OCR Access Key Secret",
    ),
]


def get_schema() -> list[dict[str, Any]]:
    """返回 schema 的 JSON 可序列化形式。"""
    return [
        {
            "key": s.key,
            "tab": s.tab,
            "field_type": s.field_type,
            "default": s.default,
            "placeholder": s.placeholder,
            "options": s.options,
            "help_text": s.help_text,
            "required": s.required,
        }
        for s in SCHEMA
    ]


def get_schema_by_tab() -> dict[str, list[dict[str, Any]]]:
    """按 Tab 分组的 schema，方便前端按标签页渲染。"""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for s in get_schema():
        grouped.setdefault(s["tab"], []).append(s)
    return grouped
