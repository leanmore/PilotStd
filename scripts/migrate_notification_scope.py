#!/usr/bin/env python3
"""A-28 通知配置迁移：备份 → 校验 → （可选）写入用户偏好。

默认**只打印计划**（dry-run），不写任何文件/数据库；`--apply` 才执行。
迁移只移动静音时段到 `user_preferences`（键 `notification_quiet_hours`），
config 原键保留（回滚/双读一版）；规则已在 DB policy，不再搬。
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pilotstd.core.config.scope import scope_of  # noqa: E402

MARKER = "notification.scope_migrated"
QUIET_PREF = "notification_quiet_hours"
QUIET_KEYS = (
    "notification.quiet_hours_enabled",
    "notification.quiet_hours_start",
    "notification.quiet_hours_end",
)


def plan(config: dict) -> list[dict]:
    # 逐键判定归属并给出动作：system 保留、rules 已在策略表、静音迁偏好
    """生成待迁移项；同时标出系统级键（只报告，不移动）。"""
    rows = []
    for key in sorted(config):
        scope = scope_of(key)
        if scope == "system":
            rows.append({"key": key, "scope": "system", "action": "keep"})
        elif key.startswith("notification.rules."):
            rows.append({"key": key, "scope": "user", "action": "policy-already"})
        elif key in QUIET_KEYS:
            rows.append({"key": key, "scope": "user", "action": "move-to-pref"})
        else:
            rows.append({"key": key, "scope": scope, "action": "keep"})
    return rows


def _backup(config_path: Path, db_path: Path, backup_dir: Path) -> Path:
    # 备份 config 与两张用户级表，供回滚；目录带时间戳
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    target = backup_dir / f"a28_scope_{stamp}"
    target.mkdir(parents=True, exist_ok=False)
    shutil.copy2(config_path, target / "config.json")
    if db_path.exists():
        conn = sqlite3.connect(db_path)
        try:
            for table in ("user_preferences", "notification_policy"):
                try:
                    cur = conn.execute(f"SELECT * FROM {table}")
                    cols = [c[0] for c in cur.description]
                    rows = [dict(zip(cols, r)) for r in cur]
                except sqlite3.Error:
                    rows = []
                (target / f"{table}.json").write_text(
                    json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
                )
        finally:
            conn.close()
    return target


def apply(config: dict, db_path: Path) -> None:
    # 只搬静音三键到所有用户的偏好；config 原键保留供回滚/双读
    """把静音时段写入所有现有用户的偏好；config 保留原键。"""
    conn = sqlite3.connect(db_path)
    try:
        users = [r[0] for r in conn.execute("SELECT id FROM users")]
        payload = {
            "enabled": bool(config.get("notification.quiet_hours_enabled", False)),
            "start": config.get("notification.quiet_hours_start", "22:00"),
            "end": config.get("notification.quiet_hours_end", "07:00"),
        }
        for user_id in users:
            conn.execute(
                "INSERT INTO user_preferences(user_id, preference_key, preference_value) VALUES(?,?,?) "
                "ON CONFLICT(user_id, preference_key) DO UPDATE SET preference_value=excluded.preference_value",
                (user_id, QUIET_PREF, json.dumps(payload, ensure_ascii=False)),
            )
        conn.commit()
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    # 入口：默认 dry-run；--apply 备份后写入；--reset 只删标记
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/config.json")
    ap.add_argument("--db", default="data/pilotstd.db")
    ap.add_argument("--backup-dir", default="backups")
    ap.add_argument("--apply", action="store_true", help="实际写入（默认 dry-run）")
    ap.add_argument("--force", action="store_true", help="忽略已迁移标记，强制重跑")
    ap.add_argument("--reset", action="store_true", help="只删除迁移标记，不清数据")
    ap.add_argument("--rollback", action="store_true", help="导出偏好→删迁移键→删标记")
    args = ap.parse_args(argv)

    config_path = Path(args.config)
    db_path = Path(args.db)
    if not config_path.exists():
        print(f"[FAIL] config not found: {config_path}")
        return 1
    if not db_path.exists():
        print(f"[FAIL] db not found: {db_path}")
        return 1

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"[FAIL] config read/parse failed: {exc}")
        return 1

    # 回滚：先导出全部 notification* 偏好，再删迁移写入的键与标记
    if args.rollback:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        target = Path(args.backup_dir) / f"a28_rollback_{stamp}"
        target.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        try:
            cur = conn.execute(
                "SELECT user_id, preference_key, preference_value FROM user_preferences "
                "WHERE preference_key LIKE 'notification%'"
            )
            rows = [dict(zip([c[0] for c in cur.description], r)) for r in cur]
            (target / "preferences.json").write_text(
                json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            conn.execute("DELETE FROM user_preferences WHERE preference_key=?", (QUIET_PREF,))
            conn.commit()
        finally:
            conn.close()
        config.pop(MARKER, None)
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[ROLLBACK] backup={target}")
        return 0

    # 只删标记，保留已写数据，便于清单调整后重新迁移
    if args.reset:
        config.pop(MARKER, None)
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        print("[RESET] marker removed; data kept")
        return 0

    if config.get(MARKER) and not args.force:
        print("[SKIP] already migrated（--force 可重跑）")
        return 0

    rows = plan(config)
    print(f"{'KEY':55} {'SCOPE':7} ACTION")
    for row in rows:
        print(f"{row['key']:55} {row['scope']:7} {row['action']}")
    to_move = [r for r in rows if r["action"] == "move-to-pref"]
    print(f"\n将迁移 {len(to_move)} 个静音键到用户偏好；config 原键保留（回滚用）。")

    if not args.apply:
        print("[DRY-RUN] 未写入任何文件/数据库")
        return 0

    try:
        # 先备份再写库：备份失败则中止，绝不留下部分迁移
        target = _backup(config_path, db_path, Path(args.backup_dir))
        print(f"[BACKUP] {target}")
        apply(config, db_path)
    except (OSError, sqlite3.Error) as exc:
        print(f"[FAIL] migration aborted, no marker written: {exc}")
        return 1

    config[MARKER] = True
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[APPLY] done; 回滚：恢复备份 config + 删除对应 user_preferences 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
