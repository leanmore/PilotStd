"""公告原文 / 附件归档：把抓到的详情 HTML 与附件落盘，供事后复核。

2026-11-20 补齐：此前只把正文写进 `announcements.raw_data`（DB），
`data/announcements/{gb,hb,db}` 目录只被创建、从未写入 —— 用户看到的"原始网页/附件没保存"
就是这个原因。本模块把原始 HTML 与附件字节落到：

    {data_dir}/announcements/{std_type}/{announce_no}.html
    {data_dir}/announcements/{std_type}/{announce_no}{ext}

约定：
- 开关 `announcement.save_raw_files`（默认 True），目录 `announcement.raw_dir`（默认空 ⇒ 上面路径）；
- 归档失败**只告警不影响解析**：原文是证据链，不是业务数据；
- 同一公告重抓/重解析直接覆盖（幂等）。
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# 附件扩展名白名单：只接受这些后缀，其余按 `.bin` 存，避免 URL 里的怪字符拼出畸形文件名
_ATTACH_EXTS = (
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".wps", ".et", ".ppt", ".pptx",
    ".zip", ".rar", ".7z", ".txt", ".html", ".htm", ".csv", ".jpg", ".png",
)
_UNSAFE = re.compile(r"[^0-9A-Za-z\u4e00-\u9fff._-]+")


def _safe_name(text: str, fallback: str = "unknown") -> str:
    """文件名安全化：保留中日韩/字母数字/._-，其余压成单个下划线，限长 80。"""
    s = _UNSAFE.sub("_", (text or "").strip()).strip("._-")
    return (s or fallback)[:80]


def _settings() -> tuple[bool, str]:
    """读开关与根目录；配置不可用时按"开 + 默认目录"降级（原文归档宁愿多存）。"""
    enabled = True
    raw_dir = ""
    try:
        from pilotstd.core.config import ConfigManager

        cfg = ConfigManager()
        enabled = bool(cfg.get("announcement.save_raw_files", True))
        raw_dir = str(cfg.get("announcement.raw_dir", "") or "")
    except Exception as exc:  # noqa: BLE001 — 配置异常不得影响抓取
        logger.warning("读取公告归档配置失败，按默认值处理: %s", exc)  # i18n-allow: 内部日志
    if not raw_dir:
        from pilotstd.core.config import get_data_dir

        raw_dir = os.path.join(get_data_dir(), "announcements")
    return enabled, raw_dir


# 目录结构固定为 <root>/<std_type>/，std_type 来自适配器（gb/hb/db），不信任外部输入；
# 公告号只做文件名，安全化后不允许包含路径分隔符，因此不可能越级写到归档根之外。
def _target(std_type: str, announce_no: str, suffix: str) -> Path | None:
    """算出归档路径并建目录；关闭归档时返回 None。"""
    enabled, root = _settings()
    if not enabled:
        return None
    folder = Path(root) / _safe_name(std_type, "unknown")
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{_safe_name(announce_no)}{suffix}"


# 原文按 utf-8 存：源站响应已被 `_fetch_detail` 统一按 utf-8 解码，这里存解码后的文本，
# 便于事后直接用编辑器/浏览器复核，不需要再猜源站编码。
def archive_html(std_type: str, announce_no: str, html: str) -> str | None:
    """落盘公告详情 HTML；成功返回路径，关闭/失败返回 None。"""
    if not html:
        return None
    try:
        path = _target(std_type, announce_no, ".html")
        if path is None:
            return None
        path.write_text(html, encoding="utf-8")
        return str(path)
    except Exception as exc:  # noqa: BLE001 — 归档失败不阻断解析
        logger.warning("公告原文归档失败: type=%s no=%s err=%s", std_type, announce_no, exc)  # i18n-allow: 内部日志
        return None


# 只认白名单后缀：URL 可能带查询串或奇怪扩展名（.php/.asp），一律降级为 `.bin`，
# 避免把可执行后缀写进归档目录造成误解或误双击。
def _attachment_suffix(url: str) -> str:
    """从 URL 取白名单后缀；取不到用 .bin（不猜，避免写出 `.php` 之类）。"""
    try:
        suffix = Path(str(url).split("?")[0]).suffix.lower()
    except Exception:  # noqa: BLE001 — 只做后缀判断
        suffix = ""
    return suffix if suffix in _ATTACH_EXTS else ".bin"


def archive_attachment(std_type: str, announce_no: str, url: str, data: bytes | None) -> str | None:
    """落盘公告附件字节；成功返回路径，关闭/失败返回 None。"""
    if not data:
        return None
    try:
        path = _target(std_type, announce_no, _attachment_suffix(url))
        if path is None:
            return None
        path.write_bytes(data)
        return str(path)
    except Exception as exc:  # noqa: BLE001 — 归档失败不阻断解析
        logger.warning(  # i18n-allow: 内部日志
        "公告附件归档失败: type=%s no=%s url=%s err=%s", std_type, announce_no, str(url)[:80], exc
    )
        return None
