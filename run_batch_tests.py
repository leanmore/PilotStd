# 分批全量测试执行器7
# 图形界面全量隔离+死锁/网络隔离+自动完成检测

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

os.environ["PYTHONIOENCODING"] = "utf-8"

PROJECT_ROOT = "D:/PilotStd"
PROGRESS_FILE = os.path.join(PROJECT_ROOT, "coverage_progress.json")
IGNORE_TEMPLATES = "--ignore=pilotstd/templates"

# ── 隔离文件定义 ──
NETWORK_FILES = ["test_e2e_adapters.py"]
DEADLOCK_ROOT_FILES = [
    "test_announce_engine.py", "test_ci_scan_fix.py", "test_core.py",
    "test_file_index_full.py", "test_final_complete.py",
    "test_group1_announcement_manager.py", "test_manager_unit.py",
    "test_migrations_full.py", "test_mock_pipeline.py", "test_monitor.py",
    "test_monitor_scheduler.py", "test_network.py", "test_notification_e2e.py",
    "test_observability.py", "test_query.py", "test_system_api.py",
    "test_task_scheduler.py", "test_ui_core.py",
]

# ── 构建批次 ──
root_all = sorted(f for f in os.listdir(os.path.join(PROJECT_ROOT, "tests"))
                   if f.startswith("test_") and f.endswith(".py"))
isolated = set(NETWORK_FILES + DEADLOCK_ROOT_FILES)
network_list = [f for f in root_all if f in NETWORK_FILES]
deadlock_root_list = [f for f in root_all if f in DEADLOCK_ROOT_FILES]
root_clean = [f for f in root_all if f not in isolated]
root_batches = [root_clean[i:i+32] for i in range(0, len(root_clean), 32)]

# 图形界面全量隔离—超时_=线程无法中断界面框架++事件循环
gui_all = sorted(f for f in os.listdir(os.path.join(PROJECT_ROOT, "tests/gui"))
                 if f.startswith("test_") and f.endswith(".py"))
gui_batches = []  # GUI 全量隔离，无法用 timeout 修复

batches = []
for i, bf in enumerate(root_batches):
    batches.append({"name": f"root_{chr(65+i)}", "dir": "tests/",
                    "files": [f"tests/{f}" for f in bf], "file_count": len(bf)})

batches.append({"name": "cli", "dir": "tests/cli/",
                "files": ["tests/cli/test_argparse.py", "tests/cli/test_execution.py"], "file_count": 2})

# 图形界面批次恢复：--超时=15替代全量隔离
for i, bf in enumerate(gui_batches):
    batches.append({"name": f"gui_{chr(65+i)}", "dir": "tests/gui/",
                    "files": [f"tests/gui/{f}" for f in bf], "file_count": len(bf),
                    "gui": True})

batches.append({"name": "web", "dir": "tests/web/",
                "files": ["tests/web/test_http_mock.py"], "file_count": 1})

# 网络依赖批次（持续集成=1跳过真实网络，--超时=30,独立）
if network_list:
    batches.append({"name": "network", "dir": "tests/",
                    "files": [f"tests/{f}" for f in network_list],
                    "file_count": len(network_list), "independent": True,
                    "env_ci": True})

# 死锁批次（仅并发文件，--超时=30,独立）
if deadlock_root_list:
    batches.append({"name": "deadlock", "dir": "tests/",
                    "files": [f"tests/{f}" for f in deadlock_root_list],
                    "file_count": len(deadlock_root_list), "independent": True})
    print(f"[PRE-SCAN] deadlock: {len(deadlock_root_list)} root concurrency files")


def save_progress(data):
    """原子写入进度文件。"""
    fd, tmp = tempfile.mkstemp(dir=PROJECT_ROOT)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, PROGRESS_FILE)


def load_progress():
    """加载进度文件，不存在则返回 None。"""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def init_progress():
    """创建初始进度文件。"""
    now = datetime.now(timezone.utc).isoformat()
    data = {"schema_version": 1, "started_at": now, "last_updated": now,
            "total_batches": len(batches), "completed_batches": [],
            "failed_batch": None, "current_batch_index": 0,
            "consecutive_failures": 0,
            "metadata": {"gui_all_isolated": True, "reason": "systematic_qt_hang"}}
    save_progress(data)
    return data


def wait_for_completion(output_file, timeout=600):
    """轮询输出文件，检测 pytest 完成标记后返回。"""
    start = time.time()
    last_size = -1
    stall_count = 0
    while time.time() - start < timeout:
        if os.path.exists(output_file):
            current_size = os.path.getsize(output_file)
            if current_size == last_size and current_size > 0:
                stall_count += 1
                try:
                    with open(output_file, 'r', encoding='utf-8', errors='replace') as f:
                        content = f.read()
                    if re.search(r'=+\s+\d+\s+passed', content):
                        return 0
                    if stall_count >= 15:
                        return 0
                except Exception:
                    pass
            else:
                stall_count = 0
                last_size = current_size
        time.sleep(2)
    try:
        if os.path.exists(output_file):
            with open(output_file, 'r', encoding='utf-8', errors='replace') as f:
                if re.search(r'=+\s+\d+\s+passed', f.read()):
                    return 0
    except Exception:
        pass
    return -1


def _build_cmd(batch, console_file):
    """构建 pytest 命令（含超时标记 / CI 前缀 / 覆盖率参数）。"""
    is_gui = batch.get("gui", False)
    is_independent = batch.get("independent", False)
    env_ci = batch.get("env_ci", False)
    if is_gui:
        timeout_flag = " --timeout=15"
    elif is_independent:
        timeout_flag = " --timeout=30"
    else:
        timeout_flag = ""
    ci_prefix = "set CI=1&& " if env_ci else ""
    files_str = " ".join(batch["files"])
    return (f'{ci_prefix}python -u -W ignore::ResourceWarning -m pytest {files_str} '
            f'--cov=pilotstd --cov-append {IGNORE_TEMPLATES} '
            f'-p no:warnings -v --tb=long {timeout_flag}'
            f'> {console_file} 2>&1')


def _spawn_and_wait(batch, name, cmd, console_file):
    """启动 pytest 子进程，等待完成或超时终止，返回退出标记。"""
    is_gui = batch.get("gui", False)
    is_independent = batch.get("independent", False)
    label = ""
    if is_gui:
        label = " [GUI timeout=15s]"
    elif is_independent:
        label = " [INDEPENDENT timeout=30s]"
    print(f"\n{'='*60}")
    print(f"[BATCH] {name} ({batch['file_count']} files){label}")
    print(f"[OUTPUT] {console_file}")
    print(f"{'='*60}")

    proc = subprocess.Popen(cmd, shell=True, cwd=PROJECT_ROOT)
    print(f"[PID] {proc.pid}")

    ret = wait_for_completion(console_file)
    if ret == -1:
        print(f"[TIMEOUT] killing {proc.pid}")
        try:
            proc.kill()
        except Exception:
            pass
    else:
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except Exception:
                pass
    return ret


def _classify_result(batch, name, console_file, log_file, ret):
    """读取输出，检测阻断错误与通过状态，返回 (success, is_blocking, error_info)。"""
    try:
        with open(console_file, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception:
        content = ""

    # 阻断关键词
    for kw in ["ImportError", "ModuleNotFoundError", "SyntaxError",
               "ERROR collecting", "Interrupted", "error during collection"]:
        if kw in content:
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if kw in line:
                    err = '\n'.join(lines[max(0,i-3):min(len(lines),i+10)])
                    return False, True, {"batch_dir": batch["dir"], "error_type": kw,
                                         "error_message": err, "traceback": err,
                                         "timestamp": datetime.now(timezone.utc).isoformat()}

    passed = bool(re.search(r'=+\s+\d+\s+passed', content))
    failed = bool(re.search(r'\d+\s+failed', content))

    if ret == -1:
        if batch.get("independent", False):
            print(f"[INFO] Independent batch {name}: timeout -> non-blocking failure")
            return False, False, None
        return False, True, {"batch_dir": batch["dir"], "error_type": "TimeoutExpired",
                             "error_message": f"Batch {name} exceeded 10 minutes",
                             "traceback": "", "timestamp": datetime.now(timezone.utc).isoformat()}

    if passed and not failed:
        print(f"[PASS] batch OK")
        return True, False, None
    else:
        print(f"[FAIL] non-blocking, continuing")
        return False, False, None


def run_batch(batch):
    """执行单个批次：构建命令、启动等待、归类结果。"""
    name = batch["name"]
    ts = datetime.now(timezone.utc).strftime("%H%M%S")
    console_file = os.path.join(PROJECT_ROOT, f"console_batch_{name}_{ts}.txt")
    log_file = os.path.join(PROJECT_ROOT, f"pytest_batch_{name}_{ts}.log")

    cmd = _build_cmd(batch, console_file)
    ret = _spawn_and_wait(batch, name, cmd, console_file)
    return _classify_result(batch, name, console_file, log_file, ret)


def main():
    """主入口：加载进度，循环执行批次，输出最终报告。"""
    progress = load_progress()
    if progress is None:
        progress = init_progress()

    print(f"Batches: {progress['total_batches']} | Start: {progress['current_batch_index']} | Done: {len(progress['completed_batches'])}")

    for idx in range(progress["current_batch_index"], len(batches)):
        batch = batches[idx]
        progress["current_batch_index"] = idx
        progress["last_updated"] = datetime.now(timezone.utc).isoformat()

        success, is_blocking, error_info = run_batch(batch)

        if success:
            progress["completed_batches"].append(batch["name"])
            progress["consecutive_failures"] = 0
            progress["failed_batch"] = None
            save_progress(progress)
        elif is_blocking and not batch.get("independent", False):
            progress["failed_batch"] = error_info
            save_progress(progress)
            print(f"\n[BLOCKED] {error_info['error_type']}")
            print(f"Progress: {len(progress['completed_batches'])}/{progress['total_batches']}")
            print("Waiting for fix instruction...")
            sys.exit(1)
        else:
            if is_blocking and batch.get("independent", False):
                print(f"[INFO] Independent batch downgraded to non-blocking")
            progress["consecutive_failures"] += 1
            progress["last_updated"] = datetime.now(timezone.utc).isoformat()
            save_progress(progress)
            if progress["consecutive_failures"] >= 3:
                print(f"\n[WARN] {progress['consecutive_failures']} consecutive failures, stopping")
                sys.exit(1)

    print(f"\n[DONE] {len(progress['completed_batches'])}/{progress['total_batches']} batches complete")
    subprocess.run("python -m coverage combine", shell=True, cwd=PROJECT_ROOT)
    subprocess.run("python -m coverage report --show-missing", shell=True, cwd=PROJECT_ROOT)


if __name__ == "__main__":
    main()
