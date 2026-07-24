#!/usr/bin/env python
# scripts/probe_ncha_api.py
"""文物保护标准站点 API 侦查 — Playwright 自动捕获 XHR 搜索接口"""

import json
import re

from playwright.sync_api import sync_playwright


def main():
    captured_apis = []

    def on_response(response):
        url = response.url
        if "ncha.gov.cn" not in url:
            return
        ct = response.headers.get("content-type", "")
        if "json" not in ct and "javascript" not in ct:
            return
        try:
            body = response.text()
            if len(body) < 50:
                return
            # 宽松捕获：任何含标准号模式或数组结构的 JSON 响应
            if re.search(r"(WW|GB|DB)/T?\s*\d+", body) or '"list"' in body or '"rows"' in body or '"data"' in body:
                captured_apis.append(
                    {
                        "url": url,
                        "method": response.request.method,
                        "status": response.status,
                        "body_preview": body[:3000],
                        "headers": dict(response.request.headers),
                        "post_data": response.request.post_data,
                    }
                )
                print(f"[CAPTURE] {response.request.method} {url}  status={response.status}  len={len(body)}")
        except Exception:
            pass

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1920, "height": 1080})

        # 监听所有响应
        page.on("response", on_response)

        print("[1/5] 加载页面 ...")
        page.goto("http://bz.ncha.gov.cn/portal?id=311&navId=3", timeout=30000)
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(3000)

        # 定位搜索框
        print("[2/5] 定位搜索框 ...")
        search_selectors = [
            'input[placeholder*="搜索"]',
            '.el-input__inner[placeholder*="搜"]',
            ".search-box input",
            'input[type="text"]:visible',
            "input.el-input__inner",
            "input",
        ]
        search_input = None
        for sel in search_selectors:
            try:
                el = page.wait_for_selector(sel, timeout=3000)
                if el and el.is_visible():
                    search_input = el
                    placeholder = el.get_attribute("placeholder") or ""
                    print(f"  OK 定位到: {sel}  placeholder={placeholder}")
                    break
            except Exception:
                continue

        if not search_input:
            print("  WARN 自动定位失败，尝试获取所有 input ...")
            inputs = page.query_selector_all("input")
            for inp in inputs:
                try:
                    ph = inp.get_attribute("placeholder") or ""
                    print(f"  input: type={inp.get_attribute('type')} placeholder={ph}")
                except Exception:
                    pass

        # 执行搜索
        print("[3/5] 执行搜索 ...")
        keyword = "WW/T"
        if search_input:
            search_input.fill(keyword)
            page.wait_for_timeout(500)

            btn_selectors = [
                'button:has-text("搜索")',
                ".search-btn",
                '.el-button--primary:has-text("搜")',
                "button .el-icon-search",
            ]
            clicked = False
            for sel in btn_selectors:
                try:
                    el = page.query_selector(sel)
                    if el and el.is_visible():
                        el.click()
                        clicked = True
                        print(f"  OK 搜索按钮点击: {sel}")
                        break
                except Exception:
                    continue
            if not clicked:
                # 按回车触发搜索
                search_input.press("Enter")
                print("  OK 按 Enter 触发搜索")
        else:
            print("  WARN 无搜索框，手动构造搜索 URL 试探 ...")

        # 等待 XHR 响应
        print("[4/5] 等待 AJAX 响应 (10s) ...")
        page.wait_for_timeout(10000)

        # 如果没捕获到，尝试点击搜索按钮
        if not captured_apis:
            print("  未捕获，尝试更多搜索触发方式 ...")
            # 尝试直接调可能的 API 路径
            import httpx

            test_urls = [
                "http://bz.ncha.gov.cn/portal/standard-common/national?keyword=WW/T&pageNum=1&pageSize=10",
                "http://bz.ncha.gov.cn/portal/standard-common/industry?keyword=WW/T&pageNum=1&pageSize=10",
                "http://bz.ncha.gov.cn/standard/applicant/findItemByProjectName?projectName=WW/T",
            ]
            for url in test_urls:
                try:
                    r = httpx.get(url, headers={"Accept": "application/json"}, timeout=10)
                    print(
                        f"  GET {url.split('?')[0]}: status={r.status_code} ct={r.headers.get('content-type', '')[:30]}"
                    )
                except Exception as e:
                    print(f"  GET {url.split('?')[0]}: ERROR {e}")

        browser.close()

    # 输出结果
    print(f"\n[5/5] 结果: 共捕获 {len(captured_apis)} 个疑似搜索 API")
    for i, api in enumerate(captured_apis):
        print(f"\n{'=' * 60}")
        print(f"API #{i + 1}")
        print(f"  URL: {api['url']}")
        print(f"  Method: {api['method']}")
        print(f"  Status: {api['status']}")
        if api["post_data"]:
            print(f"  PostData: {api['post_data'][:500]}")
        print(f"  Body (前 2000): {api['body_preview'][:2000]}")

    # 输出 JSON 汇总
    print("\n--- JSON_SUMMARY ---")
    print(
        json.dumps(
            [
                {
                    "url": a["url"],
                    "method": a["method"],
                    "status": a["status"],
                    "body_preview": a["body_preview"][:500],
                    "post_data": (a["post_data"] or "")[:300],
                }
                for a in captured_apis
            ],
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
