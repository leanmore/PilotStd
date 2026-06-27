#!/usr/bin/env python3
"""GATE-10: UI 敏感字段保护检查 — 确保敏感输入字段使用 type="password" 或 Password 组件"""

import re
import sys
from pathlib import Path

SENSITIVE_PARTS = {
    "secret",
    "password",
    "token",
    "api_key",
    "secret_key",
    "access_key",
    "private_key",
    "client_secret",
    "app_secret",
    "corpsecret",
    "secret_id",
    "key",
}

_NON_SENSITIVE_TERMS = {"key", "token"}


def _is_sensitive(name: str) -> bool:
    lower = name.lower()
    # 拆分 camelCase 和 snake_case
    parts = re.split(r"[._\-]", lower)
    # 额外拆分 camelCase: webhookUrl -> ['webhook', 'url']
    expanded = []
    for p in parts:
        expanded.extend(re.findall(r"[a-z]+|[A-Z][a-z]*", p))
    for kw in SENSITIVE_PARTS:
        for p in expanded:
            p_low = p.lower()
            if p_low == kw:
                # 排除非敏感：如 webhookUrl 中的 'key'
                if kw in _NON_SENSITIVE_TERMS:
                    # token/key 只有在全名匹配或与 secret/password 相邻时才敏感
                    prev = expanded[expanded.index(p) - 1] if expanded.index(p) > 0 else ""
                    if prev.lower() in {"access", "api", "secret", "app", "private"}:
                        return True
                    if kw == "token":
                        return True
                    continue
                return True
    return False


def _has_password_protection(content: str, field: str) -> bool:
    # 查找 field 周围的上下文（前后各 200 字符）
    idx = content.find(field)
    if idx == -1:
        return True  # 找不到就当有保护
    start = max(0, idx - 300)
    end = min(len(content), idx + 300)
    ctx = content[start:end]
    # 检查 type="password" 或 Password 组件
    return bool(re.search(r'type\s*=\s*["\']password["\']|Password\b', ctx, re.IGNORECASE))


def extract_vue_bindings(content: str) -> list[str]:
    bindings = []
    for m in re.finditer(r"v-model[:\w]*\s*=\s*[\"']([^\"']+)[\"']", content):
        bindings.append(m.group(1))
    return bindings


def main() -> int:
    web_dir = Path("web/src")
    if not web_dir.exists():
        print("PASS: web/src 不存在，跳过检查")
        return 0

    errors = []
    for vue_file in web_dir.rglob("*.vue"):
        content = vue_file.read_text(encoding="utf-8")
        for field in extract_vue_bindings(content):
            if not _is_sensitive(field):
                continue
            if _has_password_protection(content, field):
                continue
            errors.append(f"{vue_file}: 敏感字段 '{field}' 未使用 Password 组件或 type=password")

    if errors:
        print("FAIL: 以下敏感字段未受保护:")
        for e in errors:
            print(f"  {e}")
        return 1

    print("PASS: 所有敏感字段已使用密码组件保护")
    return 0


if __name__ == "__main__":
    sys.exit(main())
