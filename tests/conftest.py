# pytest 收集时忽略独立运行脚本
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone

import pytest

from pilotstd.core.db import Database

# ── 自定义 markers ──
pytest_plugins = [
    "tests.fixtures.manager_core_fixture",
    "tests.fixtures.notification_fixture",
    "tests.fixtures.workspace_fixture",
]


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: 集成测试标记（需要完整运行环境）")


collect_ignore = [
    "stress_selfcheck.py",
    "stress_web.py",
    "stress_docker.py",
    "stress_cli.py",
    "stress_runner.py",
    "gui",
    "stress_driver.py",  # 已废弃，由 stress_runner.py + stress_cli.py 替代
    "stress_winui.py",  # 由 stress_runner.py 显式调用，不走自动收集
]


@pytest.fixture(scope="session")
def shared_db():
    """会话级共享数据库（临时文件），所有测试复用同一个 Database 实例。"""
    tmp = tempfile.mkdtemp(prefix="pilotstd_shared_")
    db_path = f"{tmp}/shared_test.db"
    db = Database(db_path)
    yield db
    db.close_all()
    shutil.rmtree(tmp, ignore_errors=True)


# 需要每次测试前清理的用户数据表
_SHARED_CLEAN_TABLES = [
    "standard_info_cache",
    "file_index",
    "download_queue",
    "pending_lookup",
    "fetch_checkpoint",
    "announcement_match",
    "adapter_state",
    "daily_quota",
    "task_queue",
    "_concurrent_test",
]


@pytest.fixture(autouse=True)
def _clean_shared_db(shared_db):
    """每次测试前清理共享数据库的所有用户数据表，确保测试隔离。"""
    existing = {r["name"] for r in shared_db.fetchall("SELECT name FROM sqlite_master WHERE type='table'")}
    for table in _SHARED_CLEAN_TABLES:
        if table in existing:
            try:
                shared_db.execute(f"DELETE FROM {table}")
            except Exception:
                pass


def pytest_addoption(parser):
    """stress_winui.py 所需的自定义参数，由 stress_driver.py 传入。"""
    parser.addoption("--source", help="源目录路径")
    parser.addoption("--output", help="输出目录路径")
    parser.addoption("--step1", help="step1.json 路径")
    parser.addoption("--step2", help="step2.json 输出路径")


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    """所有测试结束后自动写入 .test_pass 文件"""
    test_pass_path = os.path.join(session.config.rootdir, ".claude", ".test_pass")
    os.makedirs(os.path.dirname(test_pass_path), exist_ok=True)

    if exitstatus == 0:
        try:
            commit_hash = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True
            ).strip()
        except subprocess.CalledProcessError:
            commit_hash = "unknown"

        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_tests": session.testscollected,
            "passed_tests": session.testscollected,
            "exit_code": 0,
            "verification_type": "auto",
            "commit_hash": commit_hash,
        }
        with open(test_pass_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    else:
        if os.path.exists(test_pass_path):
            try:
                with open(test_pass_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                if existing.get("verification_type") == "auto":
                    os.remove(test_pass_path)
            except (json.JSONDecodeError, KeyError, UnicodeDecodeError):
                os.remove(test_pass_path)
