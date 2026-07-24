#!/usr/bin/env python
# scripts/probe_cssn_api.py
"""中国标准服务网 API 侦查 — JSL 反爬 + Vue SPA XHR 捕获"""

import json

from playwright.sync_api import sync_playwright


def main():
    captured = []

    url_keywords = [
        "search",
        "query",
        "list",
        "standard",
        "std",
        "find",
        "get",
        "api",
        "service",
        "handler",
        "bz",
        "biaozhun",
        "chaxun",
        "result",
    ]

    def on_response(response):
        ct = response.headers.get("content-type", "")
        if "application/json" not in ct:
            return
        if response.status >= 400:
            return
        url = response.url
        if not any(kw in url.lower() for kw in url_keywords):
            return
        req = response.request
        req_body = req.post_data
        req_headers = dict(req.headers)
        if req_body:
            if req_body.startswith("{"):
                body_type = "json"
            elif "=" in req_body:
                body_type = "form"
            else:
                body_type = "unknown"
        else:
            body_type = "none"
        captured.append(
            {
                "url": url,
                "method": req.method,
                "headers": req_headers,
                "referer": req_headers.get("referer", ""),
                "body": req_body,
                "body_type": body_type,
                "content_type_req": req_headers.get("content-type", ""),
                "status": response.status,
                "response_truncated": response.text()[:3000] if response.status == 200 else None,
            }
        )
        print(f"[CAPTURE] {req.method} {url}  status={response.status}  body_type={body_type}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()
        page.on("response", on_response)

        print("[1/5] 加载页面 + 等待 JSL ...")
        page.goto("https://www.cssn.net.cn/cssn/index", timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        try:
            page.wait_for_function(
                "document.cookie.includes('__jsl_clearance_s')",
                timeout=15000,
            )
            print("  OK JSL 挑战通过")
        except Exception:
            print("  WARN JSL clearance 未获取")

        # 等待 Vue 挂载
        try:
            page.wait_for_selector("#app", state="visible", timeout=10000)
            print("  OK Vue 挂载完成")
        except Exception:
            print("  WARN #app 未找到")

        page.wait_for_timeout(3000)
        print(f"  页面标题: {page.title()}")

        # 导出 Cookies
        cookies = context.cookies()
        with open("cssn_cookies.json", "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        print(f"  Cookies 已导出 ({len(cookies)} 条)")

        # 定位搜索框
        print("[2/5] 定位搜索框 ...")
        selectors = [
            'input[placeholder*="标准"]',
            'input[placeholder*="搜索"]',
            'input[placeholder*="编号"]',
            'input[placeholder*="关键词"]',
            ".el-input__inner",
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
            print("  WARN 自动定位失败，列出所有 input:")
            inputs = page.query_selector_all("input")
            for inp in inputs:
                try:
                    if inp.is_visible():
                        print(
                            f"    type={inp.get_attribute('type')} placeholder={inp.get_attribute('placeholder')} class={inp.get_attribute('class')}"
                        )
                except Exception:
                    pass

        # 执行搜索
        print("[3/5] 执行搜索 (GB/T) ...")
        if input_sel:
            try:
                page.fill(input_sel, "GB/T")
                page.wait_for_timeout(500)
                page.press(input_sel, "Enter")
                print("  OK 搜索已触发")
            except Exception as e:
                print(f"  ERR: {e}")
        page.wait_for_timeout(5000)

        # 第二次搜索
        print("[4/5] 执行搜索 (SH/T) ...")
        if input_sel:
            try:
                page.fill(input_sel, "")
                page.wait_for_timeout(300)
                page.fill(input_sel, "SH/T")
                page.wait_for_timeout(500)
                page.press(input_sel, "Enter")
                print("  OK 第二次搜索已触发")
            except Exception as e:
                print(f"  ERR: {e}")
        page.wait_for_timeout(5000)

        browser.close()

    # 输出结果
    print(f"\n[5/5] 共捕获 {len(captured)} 个疑似搜索 API")
    for i, req in enumerate(captured):
        print(f"\n{'=' * 60}")
        print(f"API #{i + 1}")
        print(f"  URL: {req['url']}")
        print(f"  Method: {req['method']}")
        print(f"  Body Type: {req['body_type']}")
        print(f"  Content-Type: {req['content_type_req']}")
        print(f"  Referer: {req['referer']}")
        print(f"  Status: {req['status']}")
        if req["body"]:
            print(f"  Body: {req['body'][:500]}")
        if req["response_truncated"]:
            print(f"  Response: {req['response_truncated'][:2000]}")

    # JSON 导出
    with open("cssn_captured_apis.json", "w", encoding="utf-8") as f:
        json.dump(
            [
                {
                    "url": r["url"],
                    "method": r["method"],
                    "body_type": r["body_type"],
                    "body": r["body"],
                    "response": r["response_truncated"],
                }
                for r in captured
            ],
            f,
            ensure_ascii=False,
            indent=2,
        )
    print("\n完整数据已导出至 cssn_captured_apis.json")


if __name__ == "__main__":
    main()
