# pilotstd/wechat_ip/logic.py
"""Pure logic extracted from browser/scheduler for unit testing.

All functions have zero I/O and zero Qt/Playwright/crypto dependencies.
"""

from __future__ import annotations


def parse_cookie_string(cookie_str: str) -> list[dict[str, str]]:
    """Parse 'name=value; name2=value2' into Playwright cookie dicts.

    Extracted from WechatIPUpdater._parse_cookie (browser.py:115-130).
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
    """Return (merged_string, skipped).

    If new_ip already in current → (current, True)
    Otherwise → (current;new_ip or new_ip, False)

    Extracted from update_trusted_ip append-mode logic (browser.py:191-195).
    """
    if new_ip in current:
        return current, True
    merged = f"{current};{new_ip}" if current else new_ip
    return merged, False


def parse_app_urls(urls_str: str) -> list[str]:
    """Split comma-separated URLs, strip whitespace, drop empties.

    Extracted from run_check (scheduler.py:48-49).
    """
    return [u.strip() for u in urls_str.split(",") if u.strip()]


def is_ip_changed(current_ip: str, last_ip: str) -> bool:
    """Return True if IP has changed.

    Extracted from run_check (scheduler.py:34-36).
    """
    return current_ip != last_ip and current_ip != ""


def build_update_result(results: dict[str, bool]) -> tuple[bool, list[str]]:
    """Return (all_ok, failed_urls) from updater.update_multiple output.

    Extracted from run_check (scheduler.py:62-67).
    """
    failed = [url for url, ok in results.items() if not ok]
    all_ok = len(results) > 0 and len(failed) == 0
    return all_ok, failed
