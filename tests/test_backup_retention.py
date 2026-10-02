# tests/test_backup_retention.py
"""定时备份的**保留逻辑**测试（数据安全 P0）。

## 被修复的缺陷（生产实测）

`docker/scheduler.py::_backup_database` 原保留逻辑：

```python
all_backups = sorted([f for f in os.listdir(backup_dir) if f.endswith(".bak")], reverse=True)
for old in all_backups[4:]:
    os.remove(os.path.join(backup_dir, old))
```

按**文件名字典序**排序。迁移快照 `pre_migration_*.bak` 的字典序**大于**
`pilotstd_*.bak`（`'r' > 'i'`），逆序后排在前面 → 它们被当作"最近的 4 个"保留，
而**刚创建**的 `pilotstd_<时间戳>.bak` 落到第 5 位**被自己删掉**。

**生产证据**（日志，2026-09-28 03:00:01）：
```
数据库已备份至: /app/data/backups/pilotstd_20260928_030000.bak
已清理旧备份: pilotstd_20260928_030000.bak      ← 刚创建的备份被删
已清理旧备份: pre_migration_v55_to_v57.bak
```
`GET /api/backup/list` 实测只剩 5 个 `pre_migration_*`，**没有任何定时备份文件**
→ "备份在跑、日志显示成功，但**备份文件不留存**"。

## 修复后的契约

1. **刚创建的备份必须存活**（核心）；
2. 只对定时备份（`pilotstd_*.bak`）做数量裁剪，**迁移快照不被删**；
3. 排序按 **mtime**，不再依赖文件名字典序；
4. 只保留最近 `keep`（默认 4）个定时备份。
"""

from __future__ import annotations

import os
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from docker.scheduler import _BACKUP_KEEP, _BACKUP_MIGRATION_PREFIX, _prune_old_backups  # noqa: E402


def _touch(d: Path, name: str, mtime: float) -> Path:
    p = d / name
    p.write_bytes(b"x")
    os.utime(p, (mtime, mtime))
    return p


class TestBackupRetention(unittest.TestCase):
    def setUp(self):
        import tempfile

        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.base = time.time() - 86400 * 30  # 30 天前为基准，避免与真实时钟耦合

    def tearDown(self):
        self.tmp.cleanup()

    def _names(self) -> set[str]:
        return {p.name for p in self.dir.iterdir() if p.is_file()}

    # ── 核心回归 ────────────────────────────────────────────────────────────

    def test_newly_created_backup_survives(self):
        """★ 核心：刚创建的备份**必须存活**（原实现会把它删掉）。

        复现生产现场：5 个迁移快照 + 刚创建的定时备份。
        旧实现删除了 `pilotstd_<最新时间戳>.bak`；新实现必须保留它。
        """
        for i, v in enumerate(("v55_to_v57", "v57_to_v58", "v58_to_v59", "v59_to_v60", "v60_to_v61")):
            _touch(self.dir, f"{_BACKUP_MIGRATION_PREFIX}{v}.bak", self.base + i)
        newest = _touch(self.dir, "pilotstd_20260928_030000.bak", self.base + 100)

        _prune_old_backups(str(self.dir))

        self.assertIn(newest.name, self._names(), "刚创建的定时备份被删除了——这正是被修复的缺陷")

    def test_migration_snapshots_never_deleted(self):
        """★ 迁移快照必须**一个都不少**（它们不是定时备份，不该被定时任务清）。"""
        snaps = [f"{_BACKUP_MIGRATION_PREFIX}{v}.bak"
                 for v in ("v55_to_v57", "v57_to_v58", "v58_to_v59", "v59_to_v60", "v60_to_v61")]
        for i, nm in enumerate(snaps):
            _touch(self.dir, nm, self.base + i)
        _touch(self.dir, "pilotstd_20260101_030000.bak", self.base + 100)

        _prune_old_backups(str(self.dir))

        for nm in snaps:
            self.assertIn(nm, self._names(), f"迁移快照 {nm} 被删除")

    def test_only_keeps_n_scheduled_backups(self):
        """只保留最近 `keep` 个定时备份，更旧的被删。"""
        names = [f"pilotstd_202601{i:02d}_030000.bak" for i in range(1, 8)]  # 7 个
        for i, nm in enumerate(names):
            _touch(self.dir, nm, self.base + i)

        _prune_old_backups(str(self.dir), keep=4)

        left = sorted(n for n in self._names() if n.startswith("pilotstd_"))
        self.assertEqual(len(left), 4, f"应保留 4 个，实际 {left}")
        self.assertEqual(left, names[-4:], "保留的应是最新的 4 个（按 mtime）")

    def test_mtime_not_filename_decides(self):
        """★ 判据是 **mtime**，不是文件名字典序。

        构造"文件名最新但 mtime 最旧"的定时备份 —— 它应被删；
        以及"文件名最旧但 mtime 最新"的 —— 它应被留。
        判别力：把实现改回按文件名排序 → 本用例 FAIL。
        """
        old_name_new_time = _touch(self.dir, "pilotstd_20200101_000000.bak", self.base + 500)
        new_name_old_time = _touch(self.dir, "pilotstd_20991231_235959.bak", self.base + 1)
        for i in range(3):
            _touch(self.dir, f"pilotstd_2025060{i}_000000.bak", self.base + 10 + i)

        _prune_old_backups(str(self.dir), keep=4)

        self.assertIn(old_name_new_time.name, self._names(), "mtime 最新的应保留（与文件名无关）")
        self.assertNotIn(new_name_old_time.name, self._names(), "mtime 最旧的应被删（与文件名无关）")

    def test_keep_newest_including_just_created(self):
        """已有 4 个定时备份时，新备份进来 → 删最旧 1 个，新的与其余 3 个存活。"""
        existing = [f"pilotstd_2026010{i}_030000.bak" for i in range(1, 5)]
        for i, nm in enumerate(existing):
            _touch(self.dir, nm, self.base + i)
        newest = _touch(self.dir, "pilotstd_20260928_030000.bak", self.base + 100)

        _prune_old_backups(str(self.dir), keep=4)

        left = self._names()
        self.assertIn(newest.name, left)
        self.assertNotIn(existing[0], left, "mtime 最旧的那个应被删")
        self.assertEqual(len([n for n in left if n.startswith("pilotstd_")]), 4)

    # ── 边界 ────────────────────────────────────────────────────────────────

    def test_fewer_than_keep_deletes_nothing(self):
        _touch(self.dir, "pilotstd_20260101_030000.bak", self.base)
        _touch(self.dir, "pilotstd_20260102_030000.bak", self.base + 1)
        self.assertEqual(_prune_old_backups(str(self.dir), keep=4), [])
        self.assertEqual(len(self._names()), 2)

    def test_empty_dir_is_safe(self):
        self.assertEqual(_prune_old_backups(str(self.dir)), [])

    def test_missing_dir_is_safe(self):
        """目录不存在 → 不抛异常。"""
        self.assertEqual(_prune_old_backups(str(self.dir / "nope")), [])

    def test_returns_removed_names(self):
        for i in range(6):
            _touch(self.dir, f"pilotstd_2026010{i}_030000.bak", self.base + i)
        removed = _prune_old_backups(str(self.dir), keep=4)
        self.assertEqual(len(removed), 2)
        for nm in removed:
            self.assertNotIn(nm, self._names())

    def test_non_bak_files_ignored(self):
        (self.dir / "readme.txt").write_text("keep me", encoding="utf-8")
        for i in range(6):
            _touch(self.dir, f"pilotstd_2026010{i}_030000.bak", self.base + i)
        _prune_old_backups(str(self.dir), keep=4)
        self.assertTrue((self.dir / "readme.txt").exists(), "非 .bak 文件不应被删")

    def test_keep_constant_is_four(self):
        """保留数量契约：4（与 docstring 一致）。"""
        self.assertEqual(_BACKUP_KEEP, 4)

    def test_migration_prefix_constant(self):
        self.assertEqual(_BACKUP_MIGRATION_PREFIX, "pre_migration_")


class TestBackupNotificationOrder(unittest.TestCase):
    """★ 顺序回归：`getsize` 必须在保留清理**之前**取值。

    生产实测（2026-09-14 / 09-21 / 09-28 三条日志）：
    ```
    自动备份成功通知发送失败: [Errno 2] No such file or directory:
      '/app/data/backups/pilotstd_20260928_030000.bak'
    ```
    成因：清理逻辑（旧实现的缺陷）删掉了**刚创建**的备份文件，随后 `getsize` 抛异常、
    被外层 `except` 吞掉 → **通知从未发出**（这也是 `auto_backup` 在通知日志里 0 条的原因）。

    判别力：把 `_prune_old_backups` 调回 `getsize` 之前 → 本用例 FAIL。
    """

    def setUp(self):
        self.base = time.time() - 86400 * 30

    def _run_backup(self, existing_scheduled: int) -> dict:
        """构造临时备份目录，跑真实的 `_backup_database`，返回 send_event 的载荷。"""
        import tempfile
        from unittest.mock import MagicMock, patch

        import docker.scheduler as sched

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        backup_dir = Path(tmp.name) / "backups"
        backup_dir.mkdir()

        # 先放若干"旧的定时备份"，使清理必然触发
        for i in range(existing_scheduled):
            _touch(backup_dir, f"pilotstd_2026010{i + 1}_030000.bak", self.base + i)
        # 再放迁移快照（旧缺陷会把它们当"最新"保留，从而删掉定时备份）
        for i, v in enumerate(("v55_to_v57", "v57_to_v58", "v58_to_v59", "v59_to_v60")):
            _touch(backup_dir, f"{_BACKUP_MIGRATION_PREFIX}{v}.bak", self.base + 10 + i)

        db = MagicMock()
        db.path = str(backup_dir / "pilotstd.db")

        def _fake_backup(path: str) -> str:
            """模拟 `Database.backup()`：在**给定路径**上创建文件并返回该路径。"""
            target = Path(path)
            target.write_bytes(b"x" * 1024)
            os.utime(target, (self.base + 500, self.base + 500))
            return target.as_posix()

        db.backup.side_effect = _fake_backup
        mgr = MagicMock()

        with patch.object(sched, "_get_db", return_value=db):
            sched._backup_database(notification_mgr=mgr)

        self.assertTrue(mgr.send_event.called, "备份成功后必须发送通知")
        args, _kwargs = mgr.send_event.call_args
        self.assertEqual(args[0], "auto_backup")
        return args[1]

    def test_notification_size_is_positive(self):
        """★ 通知里的 size_mb 必须 > 0（即取值时文件还在）。"""
        payload = self._run_backup(existing_scheduled=4)
        self.assertTrue(payload["success"])
        self.assertGreater(payload["size_mb"], 0, "size_mb 为 0 说明取值时文件已不存在（顺序缺陷）")

    def test_notification_sent_even_when_pruning_removes_files(self):
        """清理会删文件时，通知仍必须发出成功载荷（不得被清理影响）。"""
        payload = self._run_backup(existing_scheduled=6)
        self.assertTrue(payload["success"])

    def test_notification_backup_path_still_exists(self):
        """通知里给出的备份路径，在通知发出时**必须仍然存在**。"""
        payload = self._run_backup(existing_scheduled=4)
        self.assertTrue(
            Path(payload["backup_path"]).exists(),
            f"通知指向的备份已被删除: {payload['backup_path']}",
        )

