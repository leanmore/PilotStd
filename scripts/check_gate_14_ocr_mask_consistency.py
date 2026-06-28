#!/usr/bin/env python3
"""GATE-14: OCR 敏感字段掩码一致性 — 确保所有字段统一使用原生 input type=password"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# OCR Tab 内必须存在的 6 个敏感字段
EXPECTED_FIELDS = [
    "ocr.baidu_api_key",
    "ocr.baidu_secret_key",
    "ocr.tencent_secret_id",
    "ocr.tencent_secret_key",
    "ocr.aliyun_access_key_id",
    "ocr.aliyun_access_key_secret",
]


def check_ocr_mask_consistency(filepath: str = "web/src/views/SettingsView.vue") -> bool:
    full_path = ROOT / filepath
    if not full_path.exists():
        print(f"文件不存在: {full_path}")
        return False

    content = full_path.read_text(encoding="utf-8")

    # 提取 OCR Tab 区域（<div v-show="activeTab === 'ocr'"> 到下一个同级 </div>）
    ocr_match = re.search(
        r'<div\s+v-show="activeTab\s*===?\s*[\'"]ocr[\'"]"[^>]*>(.*?)</div>\s*(?=\s*<(?:div|!--))',
        content,
        re.DOTALL,
    )
    if not ocr_match:
        print("未找到 OCR Tab 区域")
        return False

    ocr_content = ocr_match.group(1)

    for field in EXPECTED_FIELDS:
        # 检查字段是否存在且使用原生 input
        input_pattern = rf'<input[^>]*:value="getp\(\'{field}\'\)"[^>]*>'
        match = re.search(input_pattern, ocr_content)
        if not match:
            # 检查是否误用了 Password 组件
            password_pattern = rf'<Password[^>]*[:\-]model[^>]*=.*[\'"]{field}[\'"]'
            if re.search(password_pattern, ocr_content):
                print(f"FAIL: {field} 使用了 <Password> 组件（应为原生 <input>）")
                return False
            print(f"FAIL: {field} 未找到或格式不正确")
            return False

        tag = match.group(0)

        # 检查 type="password"
        if not re.search(r'type\s*=\s*["\']password["\']', tag):
            print(f'FAIL: {field} 缺少 type="password"')
            return False

        # 检查 autocomplete="off"
        if not re.search(r'autocomplete\s*=\s*["\']off["\']', tag):
            print(f'FAIL: {field} 缺少 autocomplete="off"')
            return False

        # 检查 class 包含 "fi"
        if not re.search(r'class\s*=\s*["\'][^"\']*\bfi\b[^"\']*["\']', tag):
            print(f'FAIL: {field} 缺少 class="fi"')
            return False

    print('GATE-14 PASS: OCR 敏感字段掩码方式一致（全部使用原生 input type="password"）')
    return True


def main() -> int:
    return 0 if check_ocr_mask_consistency() else 1


if __name__ == "__main__":
    sys.exit(main())
