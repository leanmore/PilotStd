#!/usr/bin/env python3
"""G-018: 敏感字段保护检查 — 前端 Password 组件 + 后端 OCR 掩码 + OCR 一致性
（合并原 GATE-03 check_sensitive_fields.py + GATE-10 check_ui_sensitive_fields.py +
GATE-14 check_gate_14_ocr_mask_consistency.py）"""

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ════════════════════════════════════════════════════════
# Part A: 前端 Vue 组件 — 敏感字段 Password 保护
# ════════════════════════════════════════════════════════

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
_NON_SENSITIVE = {"key", "token"}


def _is_sensitive(name: str) -> bool:
    lower = name.lower()
    parts = re.split(r"[._\-]", lower)
    expanded: list[str] = []
    for p in parts:
        expanded.extend(re.findall(r"[a-z]+|[A-Z][a-z]*", p))
    for kw in SENSITIVE_PARTS:
        for i, p in enumerate(expanded):
            if p.lower() != kw:
                continue
            if kw in _NON_SENSITIVE:
                prev = expanded[i - 1] if i > 0 else ""
                if prev.lower() in {"access", "api", "secret", "app", "private"}:
                    return True
                if kw == "token":
                    return True
                continue
            return True
    return False


def _has_password_protection(content: str, field: str) -> bool:
    idx = content.find(field)
    if idx == -1:
        return True
    ctx = content[max(0, idx - 300) : min(len(content), idx + 300)]
    return bool(re.search(r'type\s*=\s*["\']password["\']|Password\b', ctx, re.IGNORECASE))


def _extract_vue_bindings(content: str) -> list[str]:
    return [m.group(1) for m in re.finditer(r"v-model[:\w]*\s*=\s*[\"']([^\"']+)[\"']", content)]


def check_frontend() -> int:
    web_dir = ROOT / "web" / "src"
    if not web_dir.exists():
        print("  [前端] SKIP: web/src 不存在")
        return 0
    errors = []
    for vue_file in web_dir.rglob("*.vue"):
        content = vue_file.read_text(encoding="utf-8")
        for field in _extract_vue_bindings(content):
            if not _is_sensitive(field):
                continue
            if _has_password_protection(content, field):
                continue
            errors.append(f"  {vue_file.relative_to(ROOT)}: '{field}' 未使用 Password 组件或 type=password")
    if errors:
        print("  [前端] FAIL:")
        for e in errors:
            print(e)
        return 1
    print("  [前端] PASS")
    return 0


# ════════════════════════════════════════════════════════
# Part B: 后端 OCR 敏感字段掩码检查
# ════════════════════════════════════════════════════════

_OCR_SENSITIVE = {
    "baidu_api_key",
    "baidu_secret_key",
    "tencent_secret_key",
    "aliyun_access_key_id",
    "aliyun_access_key_secret",
}


def check_backend_ocr() -> int:
    settings = ROOT / "docker" / "api" / "settings.py"
    if not settings.exists():
        print("  [后端OCR] SKIP: settings.py 不存在")
        return 0
    src = settings.read_text(encoding="utf-8")
    tree = ast.parse(src)
    failed = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value in _OCR_SENSITIVE:
                    val_src = ast.get_source_segment(src, value) or ""
                    if '"***"' not in val_src:
                        failed.append(key.value)
    if failed:
        print(f"  [后端OCR] FAIL: 未掩码字段: {failed}")
        return 1
    print("  [后端OCR] PASS")
    return 0


# ════════════════════════════════════════════════════════
# Part C: OCR Tab 掩码一致性（SettingsView.vue）
# ════════════════════════════════════════════════════════

_EXPECTED_OCR_FIELDS = [
    "ocr.baidu_api_key",
    "ocr.baidu_secret_key",
    "ocr.tencent_secret_id",
    "ocr.tencent_secret_key",
    "ocr.aliyun_access_key_id",
    "ocr.aliyun_access_key_secret",
]


def check_ocr_consistency() -> int:
    fp = ROOT / "web" / "src" / "views" / "SettingsView.vue"
    if not fp.exists():
        print("  [OCR一致性] SKIP: SettingsView.vue 不存在")
        return 0
    content = fp.read_text(encoding="utf-8")
    ocr_match = re.search(
        r'<div\s+v-show="activeTab\s*===?\s*[\'"]ocr[\'"]"[^>]*>(.*?)</div>\s*(?=\s*<(?:div|!--))',
        content,
        re.DOTALL,
    )
    if not ocr_match:
        print("  [OCR一致性] SKIP: 未找到 OCR Tab 区域")
        return 0
    ocr_content = ocr_match.group(1)
    for field in _EXPECTED_OCR_FIELDS:
        m = re.search(rf'<input[^>]*:value="getp\(\'{field}\'\)"[^>]*>', ocr_content)
        if not m:
            if re.search(rf'<Password[^>]*[:\-]model[^>]*=.*[\'"]{field}[\'"]', ocr_content):
                print(f"  [OCR一致性] FAIL: {field} 使用了 <Password> 组件（应为原生 <input>）")
                return 1
            print(f"  [OCR一致性] FAIL: {field} 未找到或格式不正确")
            return 1
        tag = m.group(0)
        if not re.search(r'type\s*=\s*["\']password["\']', tag):
            print(f'  [OCR一致性] FAIL: {field} 缺少 type="password"')
            return 1
        if not re.search(r'autocomplete\s*=\s*["\']off["\']', tag):
            print(f'  [OCR一致性] FAIL: {field} 缺少 autocomplete="off"')
            return 1
        if not re.search(r'class\s*=\s*["\'][^"\']*\bfi\b[^"\']*["\']', tag):
            print(f'  [OCR一致性] FAIL: {field} 缺少 class="fi"')
            return 1
    print("  [OCR一致性] PASS")
    return 0


# ════════════════════════════════════════════════════════
# 入口
# ════════════════════════════════════════════════════════


def main() -> int:
    print("G-018: 敏感字段保护检查")
    rc = 0
    rc |= check_frontend()
    rc |= check_backend_ocr()
    rc |= check_ocr_consistency()
    if rc == 0:
        print("G-018 PASS: 全部通过")
    return rc


if __name__ == "__main__":
    sys.exit(main())
