#!/usr/bin/env python3
"""一次性迁移：把 config.json 里仍以明文保存的敏感字段加密写回。

背景：`core/config/crypto.py` 原只认「.api_key/.secret_key/...」点号后缀，
`ocr.baidu_api_key`、`notification.channels.telegram.bot_token`、`wechat.webhook_url`、
`wechat_ip.encrypt_secret` 等一直以明文落盘（2026-11-03 实测）。后缀已补全，
且 `ConfigManager` 加载时检测到明文会自愈写回；本脚本用于**部署前离线**执行并给出报告。

用法：
    python scripts/encrypt_config_secrets.py                 # 默认 data/config.json
    python scripts/encrypt_config_secrets.py --path <file>   # 指定文件
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pilotstd.core.config import ConfigManager  # noqa: E402
from pilotstd.core.config.crypto import has_plaintext_sensitive  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="加密 config.json 中的明文敏感字段")
    parser.add_argument("--path", default=str(Path(__file__).resolve().parents[1] / "data" / "config.json"))
    args = parser.parse_args()

    path = Path(args.path)
    if not path.is_file():
        print(f"[SKIP] 配置文件不存在: {path}")
        return 0

    before = json.loads(path.read_text(encoding="utf-8-sig"))
    if not has_plaintext_sensitive(before):
        print(f"[OK] 无明文敏感字段，无需迁移: {path}")
        return 0

    # ConfigManager 加载时会检测明文并写回密文；这里再显式 save 一次，确保落盘
    cfg = ConfigManager(str(path))
    cfg.save()

    after = json.loads(path.read_text(encoding="utf-8-sig"))
    if has_plaintext_sensitive(after):
        print(f"[FAIL] 仍存在明文敏感字段，请检查 .fernet_key 与目录权限: {path}")
        return 1
    print(f"[DONE] 已加密写回: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
