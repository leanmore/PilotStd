# pytest 收集时忽略独立运行脚本
import shutil
import tempfile

import pytest

from pilotstd.core.db import Database

# ── 注册 fixtures 插件 ──
pytest_plugins = [
    "tests.fixtures.manager_core_fixture",
    "tests.fixtures.notification_fixture",
    "tests.fixtures.workspace_fixture",
]

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
