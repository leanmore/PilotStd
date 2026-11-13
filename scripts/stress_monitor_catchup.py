#!/usr/bin/env python3
"""P3-16 本地 825 文件批量压测：真 parse + 真搬文件 + 真写 file_index + 真批次计数。

不 mock 数据库/文件系统，只把「查询/下载」替换为确定命中（避免外网依赖），
用于验证启动补扫在真实批量下的：
- 批次数（按目录）、成功/失败/解析失败/兜底数
- UNIQUE constraint / database is locked 次数
- 空目录清理结果

用法：python scripts/stress_monitor_catchup.py --files 825 --dirs 62
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pilotstd.core.db import Database  # noqa: E402
from pilotstd.core.file_index import FileIndexRepository  # noqa: E402
from pilotstd.core.status import Status  # noqa: E402
from pilotstd.monitor import scheduler as scheduler_mod  # noqa: E402
from pilotstd.monitor.handler import StandardFileHandler  # noqa: E402
from pilotstd.monitor.scheduler import FileMonitorScheduler  # noqa: E402
from pilotstd.organizer.industry_lookup import build_code_mapping  # noqa: E402
from pilotstd.scan.parser import StandardParser  # noqa: E402

_PDF = b"%PDF-1.4 fake standard full text"


class _ArchiveMgr:
    """压测用管理器替身：真递归扫目录、真解析文件名、真搬文件、真写 file_index。"""

    def __init__(self, db, dst: Path):
        # 解析器/索引仓库都是生产实现，只有查询/下载被"确定命中"替代
        self._parser = StandardParser(build_code_mapping())
        self._repo = FileIndexRepository(db)
        self._dst = dst
        self.auto_run_roots: list[str] = []
        self.moved = 0
        self.parse_failed = 0

    def scan_directory(self, root_path: str):
        """递归扫描目录并解析文件名；解析失败计入 parse_failed。"""
        parsed = []
        for f in sorted(Path(root_path).rglob("*.pdf")):
            info = self._parser.parse(f.name)
            if info:
                info.source_path = str(f)
                parsed.append(info)
            else:
                self.parse_failed += 1
        return parsed

    def auto_run(self, root_path: str):
        """模拟主链：扫描 → 搬文件到库目录 → 写索引；返回主链报告四键。"""
        self.auto_run_roots.append(str(root_path))
        parsed = self.scan_directory(root_path)
        self._dst.mkdir(parents=True, exist_ok=True)
        for item in parsed:
            dst = self._dst / Path(item.source_path).name
            os.replace(item.source_path, dst)
            self._repo.upsert(
                file_path=str(dst),
                logical_code=item.logical_code,
                number=item.number,
                year=item.year,
                std_name="压测标准",
                status=Status.ACTIVE.value,
            )
            self.moved += 1
        return {
            "scan": len(parsed),
            "query_found": len(parsed),
            "download_success": 0,
            "organize_moved": len(parsed),
            "organize_failed": 0,
        }


class _Capture(logging.Handler):
    """把日志文本收集到内存，用于统计 UNIQUE/locked 次数。"""

    def __init__(self):
        super().__init__()
        self.text: list[str] = []

    def emit(self, record):
        """记录一条日志消息（不落盘）。"""
        self.text.append(record.getMessage())


def main() -> int:
    """创建 N 个文件 → 跑一次启动补扫 → 输出 JSON 结果。"""
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", type=int, default=825)
    ap.add_argument("--dirs", type=int, default=62)
    args = ap.parse_args()

    # 1) 造数据：先建目录，再按 divmod 均摊文件，保证标准号唯一
    tmp = Path(tempfile.mkdtemp(prefix="pilotstd-stress-"))
    inbox = tmp / "inbox"
    inbox.mkdir()
    per_dir, rem = divmod(args.files, args.dirs)
    created = 0
    for d in range(args.dirs):
        sub = inbox / f"GB 分组{d:02d}"
        sub.mkdir()
        count = per_dir + (1 if d < rem else 0)
        for i in range(count):
            # 用不同 number 保证唯一标准号
            n = 10000 + d * 100 + i
            name = f"GB {n}-2020 压测标准{d}-{i}.pdf"
            (sub / name).write_bytes(_PDF)
            created += 1

    # 2) 初始化真实 SQLite + 索引仓库（触发器/UNIQUE 约束都是生产定义）
    db_path = str(tmp / "stress.db")
    Database(db_path).close()
    db = Database(db_path)
    mgr = _ArchiveMgr(db, tmp / "library")
    stats = MagicMock()

    # 日志收集器：从日志文本里数 UNIQUE / locked，避免只靠异常冒泡判断
    cap = _Capture()
    logging.getLogger().addHandler(cap)
    logging.getLogger("pilotstd.monitor").setLevel(logging.DEBUG)

    # 3) 固定 Monitor 配置：默认关延迟、watermark=0（首次全处理），只替换 DB 读写
    cfg = {
        "enabled": True,
        "watch_path": str(inbox),
        "delay_seconds": 0,
        "recursive": True,
        "auto_archive": True,
        "scan_existing_on_start": True,
        "file_patterns": [".pdf"],
        "ignore_patterns": ["~$", ".tmp", ".swp"],
    }
    scheduler_mod.get_config = lambda: cfg
    scheduler_mod.get_monitor_stats = lambda: stats
    scheduler_mod.get_catchup_watermark = lambda: 0.0
    scheduler_mod.set_catchup_watermark = lambda ts: None
    scheduler_mod.get_last_processed = lambda: ""
    scheduler_mod.set_last_processed = lambda p: None

    # 4) 直接跑补扫（不启动 observer：压测目标是批量主链，不是事件监听）
    scheduler = FileMonitorScheduler(manager=mgr)
    scheduler.handler = StandardFileHandler(callback=lambda p: None, delay_seconds=0)
    try:
        scheduler._catch_up_existing(threading.Event())
    finally:
        db.close()
        logging.getLogger().removeHandler(cap)

    # 5) 汇总：批次数、搬移、失败、DB 竞争、inbox/空目录残留
    inc: dict[str, int] = {}
    for c in stats.increment.call_args_list:
        inc[c.args[0]] = inc.get(c.args[0], 0) + 1
    text = "\n".join(cap.text)
    remaining_dirs = sum(1 for _ in inbox.rglob("*") if _.is_dir())
    remaining_files = len(list(inbox.rglob("*.pdf")))
    result = {
        "files_created": created,
        "dirs_created": args.dirs,
        "batches": len(mgr.auto_run_roots),
        "moved": mgr.moved,
        "parse_failed": mgr.parse_failed,
        "stats_processed": inc.get("processed", 0),
        "stats_success": inc.get("success", 0),
        "stats_failed": inc.get("failed", 0),
        "unique_errors": text.count("UNIQUE constraint failed"),
        "locked_errors": text.count("database is locked"),
        "remaining_files": remaining_files,
        "remaining_dirs": remaining_dirs,
        "library_files": len(list((tmp / "library").glob("*.pdf"))),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if remaining_files == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
