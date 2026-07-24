#!/usr/bin/env python
# scripts/probe_miit_api.py
"""工信部行业标准平台 API 侦查 — JSL 反爬 + Vue SPA XHR 捕获"""

import json

from playwright.sync_api import sync_playwright


def main():
    captured_requests = []

    def on_response(response):
        ct = response.headers.get("content-type", "")
        if "application/json" not in ct:
            return
        url = response.url
        keywords = [
            "std",
            "standard",
            "query",
            "search",
            "list",
            "miit",
            "api",
            "rest",
            "gateway",
            "page",
            "fullText",
            "industry",
            "gb",
        ]
        if not any(kw in url.lower() for kw in keywords):
            return
        try:
            resp_data = response.json() if response.status == 200 else None
        except Exception:
            resp_data = None
        captured_requests.append(
            {
                "url": url,
                "method": response.request.method,
                "headers": dict(response.request.headers),
                "body": response.request.post_data,
                "status": response.status,
                "response_truncated": str(resp_data)[:3000] if resp_data else None,
            }
        )
        print(f"\n[CAPTURE] {response.request.method} {url}  status={response.status}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()

        # 监听 XHR
        page.on("response", on_response)

        print("[1/5] 加载页面 + 等待 JSL 挑战 ...")
        page.goto("https://std.miit.gov.cn/#/fullTextList", timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # 等待 JSL clearance cookie
        try:
            page.wait_for_function(
                "document.cookie.includes('__jsl_clearance_s')",
                timeout=15000,
            )
            print("  OK JSL 挑战通过")
        except Exception:
            print("  WARN JSL clearance 未获取，尝试继续 ...")

        # 等待 Vue 挂载
        try:
            page.wait_for_selector("#app", state="visible", timeout=10000)
            print("  OK Vue 挂载完成")
        except Exception:
            print("  WARN #app 未找到")

        page.wait_for_timeout(3000)

        # 获取页面标题
        title = page.title()
        print(f"  页面标题: {title}")

        # 定位搜索框
        print("[2/5] 定位搜索框 ...")
        selectors = [
            'input[placeholder*="标准"]',
            'input[placeholder*="搜索"]',
            'input[placeholder*="全文"]',
            ".search-input input",
            '.el-input__inner[type="text"]',
            'input[type="text"]:visible',
            "input:visible",
        ]
        input_sel = None
        for sel in selectors:
            try:
                el = page.wait_for_selector(sel, timeout=3000)
                if el and el.is_visible():
                    input_sel = sel
                    ph = el.get_attribute("placeholder") or ""
                    print(f"  OK 定位: {sel}  placeholder='{ph}'")
                    break
            except Exception:
                continue

        if not input_sel:
            # 列出所有可见 input
            print("  WARN 自动定位失败，列出所有 input:")
            inputs = page.query_selector_all("input")
            for inp in inputs:
                try:
                    if inp.is_visible():
                        print(
                            f"    type={inp.get_attribute('type')} placeholder={inp.get_attribute('placeholder')} id={inp.get_attribute('id')} class={inp.get_attribute('class')}"
                        )
                except Exception:
                    pass

        # 执行搜索
        print("[3/5] 执行搜索 ...")
        if input_sel:
            try:
                page.fill(input_sel, "GB/T")
                page.wait_for_timeout(500)

                # 搜索按钮
                btn_sels = [
                    'button:has-text("搜索")',
                    'button:has-text("查询")',
                    ".search-btn",
                    ".el-button--primary",
                    "button.el-button",
                ]
                clicked = False
                for sel in btn_sels:
                    try:
                        el = page.query_selector(sel)
                        if el and el.is_visible():
                            el.click()
                            clicked = True
                            print(f"  OK 按钮点击: {sel}")
                            break
                    except Exception:
                        continue
                if not clicked:
                    page.press(input_sel, "Enter")
                    print("  OK 按 Enter 搜索")
            except Exception as e:
                print(f"  ERR 搜索操作失败: {e}")
                page.press("Enter")
        else:
            print("  WARN 无搜索框可用，直接尝试 API 探测 ...")

        # 等待响应
        print("[4/5] 等待 AJAX 响应 (10s) ...")
        page.wait_for_timeout(10000)

        # 如果没捕获，尝试直接构造可能的 API
        if not captured_requests:
            print("  未捕获到 API，尝试直接探测已知路径 ...")
            import httpx

            cookies_list = page.context.cookies()
            cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies_list)
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Cookie": cookie_str,
                "Accept": "application/json",
                "Referer": "https://std.miit.gov.cn/",
                "X-Requested-With": "XMLHttpRequest",
            }
            test_urls = [
                "https://std.miit.gov.cn/api/fullTextList",
                "https://std.miit.gov.cn/api/searchResult",
                "https://std.miit.gov.cn/api/standard/list",
                "https://std.miit.gov.cn/api/std/list",
                "https://std.miit.gov.cn/api/industry/query",
                "https://std.miit.gov.cn/gateway/search",
                "https://std.miit.gov.cn/rest/standard/search",
            ]
            for url in test_urls:
                try:
                    r = httpx.get(url, headers=headers, timeout=10)
                    print(f"  GET {url}: {r.status_code} {len(r.text)}")
                except Exception as e:
                    print(f"  GET {url}: ERROR {e}")

        # 导出 Cookies
        cookies = context.cookies()
        with open("std_miit_cookies.json", "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        print(f"\n[5/5] Cookies 已导出 ({len(cookies)} 条)")

        browser.close()

    # 输出结果
    print(f"\n{'=' * 60}")
    print(f"共捕获 {len(captured_requests)} 个疑似搜索 API")
    for i, req in enumerate(captured_requests):
        print(f"\n--- API #{i + 1} ---")
        print(f"URL: {req['url']}")
        print(f"Method: {req['method']}")
        print(
            f"Headers: {json.dumps({k: v for k, v in req['headers'].items() if k.lower() not in ('host', 'content-length', 'accept-encoding', 'user-agent')}, indent=2)}"
        )
        if req["body"]:
            print(f"Body: {req['body'][:500]}")
        if req["response_truncated"]:
            print(f"Response: {req['response_truncated'][:2000]}")


if __name__ == "__main__":
    main()
