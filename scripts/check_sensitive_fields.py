#!/usr/bin/env python
"""门禁 GATE-03：检查 OCR 敏感字段是否已掩码。
退出门禁：返回 0=通过, 1=阻断。"""

import ast
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SETTINGS = _ROOT / "docker" / "api" / "settings.py"

# 应掩码的 OCR 字段
_SENSITIVE = {
    "baidu_api_key",
    "baidu_secret_key",
    "tencent_secret_key",
    "aliyun_access_key_id",
    "aliyun_access_key_secret",
}


def check() -> int:
    src = _SETTINGS.read_text(encoding="utf-8")
    tree = ast.parse(src)
    failed = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value in _SENSITIVE:
                    val_src = ast.get_source_segment(src, value) or ""
                    if '"***"' not in val_src:
                        failed.append(key.value)
    if failed:
        print(f"[GATE-03] FAIL: 未掩码字段: {failed}")
        return 1
    print("[GATE-03] PASS: OCR 敏感字段已掩码")
    return 0


if __name__ == "__main__":
    sys.exit(check())
