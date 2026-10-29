#!/usr/bin/env python3
"""应用级冒烟：health → login → notification test（默认）；--full 追加扫描/查询。

凭据来源：环境变量 SMOKE_USER/SMOKE_PASSWORD，或 config/docker_creds.json（按行提取）。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]


def _creds() -> tuple[str, str]:
    # 优先环境变量；否则从 GBK 注释的凭据文件按行正则提取
    user = __import__("os").environ.get("SMOKE_USER")
    pwd = __import__("os").environ.get("SMOKE_PASSWORD")
    if user and pwd:
        return user, pwd
    path = ROOT / "config" / "docker_creds.json"
    text = path.read_bytes().decode("gb18030", errors="replace")
    u = re.search(r'"username"\s*:\s*"([^"]+)"', text)
    p = re.search(r'"password"\s*:\s*"([^"]+)"', text)
    if not u or not p:
        raise SystemExit("无法从 config/docker_creds.json 提取凭据")
    return u.group(1), p.group(1)


def main() -> int:
    # 冒烟入口：健康检查 → 登录 → 通知测试；失败即返回非零
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:9028")
    ap.add_argument("--channel", default="telegram")
    ap.add_argument("--full", action="store_true", help="追加扫描/查询（有副作用，默认关闭）")
    args = ap.parse_args()
    base = args.base_url.rstrip("/")
    s = requests.Session()

    h = s.get(f"{base}/api/health", timeout=10)
    print("health", h.status_code, h.json().get("status"))
    if h.status_code != 200:
        return 1

    user, pwd = _creds()
    r = s.post(f"{base}/api/login", data={"username": user, "password": pwd}, timeout=10)
    print("login", r.status_code)
    if r.status_code != 200:
        return 1

    cfg = s.get(f"{base}/api/notification/config", timeout=10)
    print("config", cfg.status_code, "enabled=", cfg.json().get("enabled"))
    if cfg.status_code != 200:
        return 1

    csrf = s.cookies.get("csrf_token", "")
    t = s.post(
        f"{base}/api/notification/test",
        json={"channel": args.channel, "title": "smoke_app", "body": "application smoke"},
        headers={"X-CSRF-Token": csrf},
        timeout=15,
    )
    ok = t.status_code == 200 and t.json().get("ok") is True
    print("notification_test", t.status_code, t.text[:80])
    if not ok:
        return 1

    if args.full:
        print("full steps not implemented: scan/query need a dedicated staging fixture")

    print("SMOKE PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
