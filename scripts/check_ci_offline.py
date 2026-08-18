#!/usr/bin/env python3
"""CI 离线门禁检查：确认外部标准站点已被网络层阻断。

在 ci.yml 的 test-backend job 中，iptables 阻断外部网络后运行本脚本，
快速 fail-fast 验证阻断是否生效，避免 3000+ 测试白跑。

仅当 CI=true 时执行检查；本地开发环境跳过。
"""

import io
import os
import socket
import sys

# Windows 控制台默认编码无法输出部分字符，统一改用 UTF-8 输出，任何平台不崩溃
if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DOMAINS_TO_TEST = [
    "std.samr.gov.cn",
    "www.csres.com",
    "www.cssn.net.cn",
    "openstd.samr.gov.cn",
    "jjg.spc.org.cn",
]


def main() -> int:
    """入口：执行离线网络门禁检查，按探测结果返回退出码。"""
    if os.environ.get("CI") != "true":
        print("⏭️  非 CI 环境，跳过网络门禁检查")
        return 0

    print("🔒 CI 网络门禁检查...")
    blocked = 0
    for domain in DOMAINS_TO_TEST:
        try:
            socket.create_connection((domain, 443), timeout=3)
        except (ConnectionRefusedError, OSError, socket.timeout):
            print(f"  ✅ {domain} — 已阻断")
        else:
            print(f"  ❌ {domain} — 可连通！（应该被阻断）")
            blocked += 1

    if blocked:
        print(f"\n❌ {blocked} 个站点未被阻断，请检查 iptables 规则")
        return 1

    print("✅ 所有外部站点已阻断")
    return 0


if __name__ == "__main__":
    sys.exit(main())
