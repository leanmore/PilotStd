# pytest 收集时忽略独立运行脚本
import json
import os
import shutil
import socket
import subprocess
import tempfile
from datetime import datetime, timezone

import pytest

from pilotstd.core.db import Database

# ── 自定义 markers ──
# e2e 模式下跳过插件注册，避免 PytestAssertRewriteWarning
if os.environ.get("PYTEST_RUNNING_MODE") == "e2e":
    pytest_plugins: list[str] = []
else:
    pytest_plugins = [
        "tests.fixtures.manager_core_fixture",
        "tests.fixtures.notification_fixture",
        "tests.fixtures.workspace_fixture",
    ]


def pytest_configure(config):
    # 标记 pytest 运行环境：查询引擎在测试中跳过真实请求间隔 sleep，避免超时
    os.environ["PYTEST_RUNNING"] = "1"
    config.addinivalue_line("markers", "integration: 集成测试标记（需要完整运行环境）")
    config.addinivalue_line("markers", "serial: 串行执行标记（避免并发权限竞争）")


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


@pytest.fixture(scope="session", autouse=True)
def ensure_data_dir():
    """预创建 data/ 目录和空配置文件，消除所有测试文件的 first-run 竞态。"""
    from pathlib import Path

    config_path = Path("data/config.json")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if not config_path.exists():
        config_path.write_text("{}", encoding="utf-8")


@pytest.fixture(autouse=True)
def _isolate_fernet_db(tmp_path, monkeypatch):
    """全局隔离 Fernet/数据库：get_db_path 指向每测试独立的临时空库。

    本地开发库 data/pilotstd.db 含加密旧凭证，_get_fernet 在 Key 缺失时会触发
    防呆 RuntimeError（CI 干净环境无此问题）；重定向到空库使其走"全新安装"
    分支自动生成 Key。测试内的局部 patch/注入会覆盖本值并自动还原，互不冲突。
    注意：不重写 ConfigManager.__init__ 等构造器，避免影响显式传参的测试。
    """
    monkeypatch.setattr("pilotstd.core.config.paths.get_db_path", lambda: str(tmp_path / "pilotstd.db"))


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


# ── BatchDispatcher 心跳线程清理 ──
# CI 中 Windows access violation 的根因：测试结束后 daemon 心跳线程
# 未正常退出，访问已销毁的 Qt 对象导致崩溃。session 级 fixture
# 在全部测试结束后调用 stop_heartbeat() 确保线程安全退出。
@pytest.fixture(scope="session", autouse=True)
def _cleanup_batch_dispatcher_heartbeat():
    """session 级兜底清理：测试异常中断时确保心跳线程退出。"""
    yield
    try:
        from pilotstd.query.engine._batch_dispatcher import BatchDispatcher

        instance = getattr(BatchDispatcher, "_instance", None)
        if instance is not None:
            instance.stop_heartbeat()
    except Exception:
        pass


# ── CI 离线网络兜底 ─────────────────────────────────────────────
# 主防线是 ci.yml 中的 iptables 硬阻断；本 fixture 是进程内兜底，
# 在 socket 层拦截非 localhost 的 connect，即使 iptables 失效也保证
# 测试绝不真实访问外部站点。不与 responses/respx 冲突：mock 框架
# 的请求不会真正走到 connect()。pytest-xdist 下每个 worker 独立生效。
@pytest.fixture(scope="session", autouse=True)
def _ci_network_guard():
    """CI 环境下 patch socket，阻断非 localhost 的真实连接。"""
    if os.environ.get("CI") != "true":
        yield
        return

    _orig_connect = socket.socket.connect

    def _guarded_connect(self, address):
        host = address[0] if address else ""
        if host not in ("127.0.0.1", "::1", "localhost", "0.0.0.0", ""):
            # 允许 pytest-httpserver 等本地服务
            if not host.startswith("127.") and not host.startswith("192.168."):
                raise ConnectionRefusedError(f"🔒 CI offline guard: blocked connection to {host}:{address[1]}")
        return _orig_connect(self, address)

    socket.socket.connect = _guarded_connect
    yield
    socket.socket.connect = _orig_connect
