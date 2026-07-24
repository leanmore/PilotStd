#!/usr/bin/env python
"""探测 {{ cookiecutter.site_label }} 的接口形态。用法: python probe.py"""

import sys
from pathlib import Path

import httpx


def probe():
    """探测接口形态。"""
    client = httpx.Client(
        verify={{ cookiecutter.verify_ssl }},
        timeout=15.0,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json,text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        },
    )
    url = "{{ cookiecutter.base_url }}{{ cookiecutter.search_endpoint }}"

    try:
        if "{{ cookiecutter.method }}" == "POST":
            resp = client.post(url, data={"keyword": "GB"}, timeout=15)
        else:
            resp = client.get(url, params={"keyword": "GB"}, timeout=15)
    except Exception as e:
        print(f"FAIL request: {e}")
        sys.exit(1)

    print(f"STATUS: {resp.status_code}")
    print(f"CONTENT-TYPE: {resp.headers.get('content-type', 'unknown')}")
    print(f"ENCODING: {resp.encoding or 'unknown'}")

    fixture_dir = Path(__file__).parent.parent / "tests" / "fixtures"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    fixture_path = fixture_dir / "probe_raw.txt"
    fixture_path.write_text(resp.text[:5000], encoding="utf-8")
    print(f"SAVED: {fixture_path}")

    try:
        data = resp.json()
        print(f"JSON: type={type(data).__name__}")
        if isinstance(data, list) and data:
            print(f"  len={len(data)} fields={list(data[0].keys())[:10] if isinstance(data[0], dict) else 'N/A'}")
        elif isinstance(data, dict):
            print(f"  keys={list(data.keys())[:10]}")
            for k in ["data", "rows", "results", "list"]:
                if k in data and isinstance(data[k], list) and data[k]:
                    print(f"  {k}[0] fields={list(data[k][0].keys())[:10]}")
                    break
    except Exception:
        print("NOT JSON (HTML response saved)")

if __name__ == "__main__":
    probe()
