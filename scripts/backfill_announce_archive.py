#!/usr/bin/env python3
"""补抓历史公告的原文/附件归档（2026-11-20）。

背景：`data/announcements/` 此前只建目录不写文件；新代码只对**之后**的抓取生效。
本脚本遍历 `announcements` 表里的历史公告，逐个调
`POST /api/announcements/{announce_no}/reparse?source=<source_site>` 重新抓取，
从而让新代码把 HTML/附件落盘。

用法（部署含归档代码的版本后执行）：
    python scripts/backfill_announce_archive.py --dry-run          # 只列待补数量
    python scripts/backfill_announce_archive.py --limit 20         # 先试 20 条
    python scripts/backfill_announce_archive.py --delay 1.5        # 全量（默认 1.5s/条）

特性：
- 断点续跑：状态写在 `%TEMP%/pilotstd_archive_backfill.json`（key = source|announce_no）；
- 单条失败只记日志继续，退出码反映失败条数是否为 0；
- 只调用现有 admin 接口，不改库结构、不删数据。
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
STATE = Path(tempfile.gettempdir()) / "pilotstd_archive_backfill.json"


def _creds() -> dict:
    """读取生产访问凭据（GBK/UTF-8 都兼容；不打印内容）。"""
    raw = (ROOT / "config" / "docker_creds.json").read_bytes()
    for enc in ("utf-8", "gbk"):
        try:
            return json.loads(raw.decode(enc))
        except Exception:  # noqa: BLE001 — 两种编码都试
            continue
    raise SystemExit("凭据文件解析失败")


def _login(base: str, cfg: dict) -> requests.Session:
    """登录拿会话；同时把 CSRF token 放进请求头（写接口需要）。"""
    s = requests.Session()
    resp = s.post(
        f"{base}/api/login",
        data={"username": cfg["docker"]["username"], "password": cfg["docker"]["password"]},
        timeout=20,
    )
    resp.raise_for_status()
    token = s.cookies.get("csrf_token", "")
    if token:
        s.headers["X-CSRF-Token"] = token
    return s


# 目标清单直接走管理 SQL：比翻列表接口更准（列表接口是去重后的展示口径）
def targets(session: requests.Session, base: str) -> list[tuple[str, str]]:
    """取全部公告（来源, 公告号），按年份升序（先补最老的，便于尽早看到归档效果）。"""
    sql = (
        "SELECT source_site, TRIM(announce_no) AS no FROM announcements "
        "WHERE announce_no IS NOT NULL AND TRIM(announce_no) != '' "
        "ORDER BY source_site, no"
    )
    resp = session.post(f"{base}/query", json={"sql": sql}, timeout=120)
    resp.raise_for_status()
    rows = resp.json().get("rows", [])
    return [(str(r["source_site"]), str(r["no"])) for r in rows]


def pending(all_targets: list[tuple[str, str]], done: set[str]) -> list[tuple[str, str]]:
    """过滤掉已完成的（key = source|no）；纯函数，便于测试。"""
    return [(s, n) for s, n in all_targets if f"{s}|{n}" not in done]


def main(argv: list[str] | None = None) -> int:
    """入口：取目标 → 逐条 reparse → 断点续跑。返回 0 表示本轮无失败。"""
    parser = argparse.ArgumentParser(description="补抓历史公告原文/附件归档")
    parser.add_argument("--delay", type=float, default=1.5, help="每条之间暂停秒数")
    parser.add_argument("--limit", type=int, default=0, help="本次最多处理多少条（0=不限）")
    parser.add_argument("--dry-run", action="store_true", help="只统计待补数量，不发请求")
    args = parser.parse_args(argv)

    cfg = _creds()
    base = cfg["docker"]["base_url"].rstrip("/")
    session = _login(base, cfg)

    # 断点续跑：每条 `reparse` 都要抓详情+附件，945 条可能几十分钟，中断后不能从头再来
    done: set[str] = set()
    if STATE.exists():
        try:
            done = set(json.loads(STATE.read_text(encoding="utf-8")).get("done", []))
        except Exception as exc:  # noqa: BLE001 — 状态文件损坏就从零开始
            print(f"[WARN] 状态文件损坏，从零开始: {exc}", file=sys.stderr)

    todo = pending(targets(session, base), done)
    print(f"公告总数={len(done) + len(todo)} 已完成={len(done)} 待补={len(todo)}")
    if args.dry_run:
        return 0

    if args.limit:
        todo = todo[: args.limit]

    # 逐条串行：源站有频控，并发只会换来整批 429；失败不重试，靠断点续跑二次执行
    failed = 0
    for idx, (source, no) in enumerate(todo, start=1):
        # 公告号含中文与“第/号”，必须转义；`source` 用于消歧（同一公告号可能在多来源出现）
        url = f"{base}/api/announcements/{requests.utils.quote(no, safe='')}/reparse"
        try:
            resp = session.post(url, params={"source": source}, timeout=300)
            ok = resp.status_code == 200
            detail = resp.text[:120] if not ok else ""
        except Exception as exc:  # noqa: BLE001 — 单条网络异常不中断整批
            ok, detail = False, str(exc)[:120]
        if ok:
            done.add(f"{source}|{no}")
            if idx % 20 == 0 or idx == len(todo):
                STATE.write_text(json.dumps({"done": sorted(done)}, ensure_ascii=False), encoding="utf-8")
            print(f"[{idx}/{len(todo)}] OK {source} {no}")
        else:
            failed += 1
            print(f"[{idx}/{len(todo)}] FAIL {source} {no} -> {detail}", file=sys.stderr)
        time.sleep(max(0.0, args.delay))

    STATE.write_text(json.dumps({"done": sorted(done)}, ensure_ascii=False), encoding="utf-8")
    print(f"完成：成功={len(todo) - failed} 失败={failed} 累计已完成={len(done)}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
