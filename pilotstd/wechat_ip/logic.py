# 模块：pilotstd/wechat_ip/logic.py
"""从浏览器/调度器中提取的纯逻辑，供单元测试使用。

所有函数均为零 I/O、零 Qt/Playwright/加密依赖。
"""

from __future__ import annotations


def parse_cookie_string(cookie_str: str) -> list[dict[str, str]]:
    """将 "name=value; name2=value2" 格式解析为 Playwright cookie 字典列表。

    提取自 WechatIPUpdater._parse_cookie（browser.py:115-130）。
    """
    result: list[dict[str, str]] = []
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            result.append(
                {
                    "name": k.strip(),
                    "value": v.strip(),
                    "domain": ".work.weixin.qq.com",
                    "path": "/",
                }
            )
    return result


def merge_ip_list(current: str, new_ip: str) -> tuple[str, bool]:
    """返回 (合并后的字符串, 是否跳过)。

    若 new_ip 已在 current 中 → (current, True)
    否则 → (current;new_ip 或 new_ip, False)

    提取自 update_trusted_ip 追加模式逻辑（browser.py:191-195）。
    """
    if new_ip in current:
        return current, True
    merged = f"{current};{new_ip}" if current else new_ip
    return merged, False


def parse_app_urls(urls_str: str) -> list[str]:
    """按逗号拆分 URL 列表，去除空白并过滤空值。

    提取自 run_check（scheduler.py:48-49）。
    """
    return [u.strip() for u in urls_str.split(",") if u.strip()]


def is_ip_changed(current_ip: str, last_ip: str) -> bool:
    """若 IP 地址发生变化则返回 True。

    提取自 run_check（scheduler.py:34-36）。
    """
    return current_ip != last_ip and current_ip != ""


def build_update_result(results: dict[str, bool]) -> tuple[bool, list[str]]:
    """从 updater.update_multiple 输出中提取 (全部成功, 失败URL列表)。

    提取自 run_check（scheduler.py:62-67）。
    """
    failed = [url for url, ok in results.items() if not ok]
    all_ok = len(results) > 0 and len(failed) == 0
    return all_ok, failed
