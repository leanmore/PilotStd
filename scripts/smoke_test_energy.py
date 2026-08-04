#!/usr/bin/env python
# 模块：scripts/smoke_test_energy.py
"""能源标准适配器网络冒烟测试。

用途：验证 EnergyAdapter 在真实网络环境下能正常访问 114.251.111.103:18080。
用法：python scripts/smoke_test_energy.py
要求：执行环境必须能访问 https://114.251.111.103:18080
"""

import sys
from pathlib import Path

import urllib3

# 适配器内部已设置 verify=False，此处消除控制台警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 确保项目根目录在 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    from pilotstd.query.adapters.energy import EnergyAdapter

    print("=" * 60)
    print("能源标准适配器 — 网络冒烟测试")
    print("=" * 60)

    # 1. 初始化适配器
    adapter = EnergyAdapter()
    print(f"\n[1/5] 适配器初始化: {adapter.site_label} ({adapter.site_name})")
    print(f"      API_URL: {adapter.API_URL}")

    # 2. 验证 Host Header
    host = adapter._client.headers.get("Host", "")
    print(f"\n[2/5] Host Header: {host}")
    assert host == "114.251.111.103:18080", f"Host Header 不正确: {host}"
    print("      Host Header 断言通过")

    # 3. 搜索
    keyword = "消防"
    print(f'\n[3/5] 搜索关键词: "{keyword}"')
    try:
        results = adapter.query_standards(keyword)
    except Exception as e:
        print(f"\n[FAIL] 网络请求失败: {e}")
        print("原因: 当前环境无法访问 114.251.111.103:18080")
        print("解决: 请在可访问该 IP 的环境中重新执行本脚本")
        return 1

    # 4. 验证结果
    print(f"\n[4/5] 返回 {len(results)} 条结果")
    if len(results) == 0:
        print("[FAIL] 搜索返回 0 条结果")
        print("可能原因: 关键词无匹配 / 网站结构变更 / AJAX 参数不匹配")
        return 1

    all_ok = True
    for i, r in enumerate(results):
        fields_ok = bool(r.standard_number) and bool(r.standard_name)
        status_icon = "OK" if fields_ok else "MISSING"
        if not fields_ok:
            all_ok = False
        name_display = r.standard_name[:50] if r.standard_name else "(空)"
        print(f"  [{status_icon}] #{i + 1}: {r.standard_number} — {name_display}")
        if r.publish_date or r.implementation_date:
            print(f"         日期: {r.publish_date} / {r.implementation_date}  状态: {r.status}")

    # 5. 最终断言
    print("\n[5/5] 最终断言")
    assert all_ok, "存在核心字段为空的结果"
    assert len(results) >= 1, "搜索结果不足 1 条"

    print("=" * 60)
    print("冒烟测试通过")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
