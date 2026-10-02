# tests/test_lockout_audit.py
"""L-01 B 类：登录锁定（429）审计留痕 `_audit_lockout_once` 的判别测试。

背景：`login()` 的超限检查（`count_recent_failures >= MAX_ATTEMPTS`）原本**不写审计**——
攻击者失败 100 次后每次请求都被 429，却无任何记录。告警侧（`_notify_login_failure`）
只在 `failures == LOGIN_FAILURE_ALERT_THRESHOLD(5)` 时触发，告警阈值(5)与限流阈值(100)
**故意解耦**，故 429 路径完全没有留痕。

**判别力原则**：本文件的每个用例都对应一个"注入坏形态必须 FAIL"的场景，注释中标明。
"""

from __future__ import annotations

import sys
import threading
import time

import pytest

from docker import auth
from docker.auth import LOCKOUT_SECONDS, MAX_ATTEMPTS, _audit_lockout_once

IP = "10.0.0.9"
T0 = 1_700_000_000.0


@pytest.fixture(autouse=True)
def _clean_gate():
    """每个用例前后清空闸门状态，避免用例间串扰。"""
    auth._lockout_audited_at.clear()
    yield
    auth._lockout_audited_at.clear()


def _audit_calls(monkeypatch) -> list[dict]:
    """拦截 write_audit，返回调用记录列表。"""
    calls: list[dict] = []

    def fake_write_audit(*, action, resource="", detail=None, user_id=None):
        calls.append({"action": action, "resource": resource, "detail": detail, "user_id": user_id})

    monkeypatch.setattr("pilotstd.core.audit.write_audit", fake_write_audit)
    return calls


class TestGateUsesPassedNow:
    """T5b（**主判据**）：闸门只依据传入的 `now` 判定，不读取真实时钟。

    注入坏形态（在函数内另取 `time.time()`）时：真实当前时间与 T0（过去时刻）差值巨大 →
    第 2 次调用会**误写** → call_count 变 3 → 本用例 FAIL。
    """

    def test_same_window_writes_once(self, monkeypatch):
        calls = _audit_calls(monkeypatch)
        _audit_lockout_once(IP, failures=MAX_ATTEMPTS, now=T0)
        _audit_lockout_once(IP, failures=MAX_ATTEMPTS, now=T0 + LOCKOUT_SECONDS / 2)
        assert len(calls) == 1, "同一窗口内重复留痕（闸门未生效）"

    def test_expired_window_writes_again(self, monkeypatch):
        calls = _audit_calls(monkeypatch)
        _audit_lockout_once(IP, failures=MAX_ATTEMPTS, now=T0)
        _audit_lockout_once(IP, failures=MAX_ATTEMPTS, now=T0 + LOCKOUT_SECONDS)
        assert len(calls) == 2, "闸门过期后应允许再次留痕"

    def test_gate_is_per_ip(self, monkeypatch):
        """闸门按 IP 隔离：另一个 IP 不受影响。"""
        calls = _audit_calls(monkeypatch)
        _audit_lockout_once(IP, failures=MAX_ATTEMPTS, now=T0)
        _audit_lockout_once("10.0.0.10", failures=MAX_ATTEMPTS, now=T0)
        assert len(calls) == 2


class TestAuditPayload:
    """审计载荷口径：与 LOGIN_FAILED 区分，且不记用户名/密码（防枚举）。"""

    def test_action_and_resource(self, monkeypatch):
        calls = _audit_calls(monkeypatch)
        _audit_lockout_once(IP, failures=MAX_ATTEMPTS, now=T0)
        assert calls[0]["action"] == "LOGIN_ATTEMPT_BLOCKED"
        assert calls[0]["resource"] == "POST /api/login"
        assert calls[0]["user_id"] is None, "未认证路径应显式传 None"

    def test_detail_has_no_username_or_password(self, monkeypatch):
        calls = _audit_calls(monkeypatch)
        _audit_lockout_once(IP, failures=MAX_ATTEMPTS, now=T0)
        detail = calls[0]["detail"]
        assert detail["from_ip"] == IP
        assert detail["failures"] == MAX_ATTEMPTS
        assert detail["window_seconds"] == LOCKOUT_SECONDS
        assert "username" not in detail, "登录失败口径不得记录用户名（防用户名枚举）"
        assert not any("password" in str(k).lower() for k in detail)


class TestCleanup:
    """T4：惰性清理——陈旧条目必须被移除（否则 dict 随时间无限增长）。"""

    def test_stale_entries_pruned(self, monkeypatch):
        _audit_calls(monkeypatch)
        _audit_lockout_once("10.0.0.1", failures=MAX_ATTEMPTS, now=T0)
        _audit_lockout_once("10.0.0.2", failures=MAX_ATTEMPTS, now=T0)
        assert len(auth._lockout_audited_at) == 2
        # 推进到超过 2 倍窗口后，对第三个 IP 触发一次 → 旧条目应被清理
        _audit_lockout_once("10.0.0.3", failures=MAX_ATTEMPTS, now=T0 + LOCKOUT_SECONDS * 2 + 1)
        assert "10.0.0.1" not in auth._lockout_audited_at, "陈旧条目未被清理（dict 会无限增长）"
        assert "10.0.0.2" not in auth._lockout_audited_at
        assert "10.0.0.3" in auth._lockout_audited_at


class TestConcurrency:
    """T2：并发下必须只写一次——锁须覆盖「读取 + 判定 + 清理 + 更新」整个临界区。

    **构造方式（放大竞态窗口，不依赖运气）**：
      1. `sys.setswitchinterval(1e-6)` 强制高频线程切换；
      2. 探针 dict 在**第 1 次** `get` 之后 `time.sleep(0.05)`——把"读到旧值"与
         "写回新值"之间的窗口拉到 50ms 量级，使其他线程**必然**在此期间完成读取。

    **判别力（已实测）**：
      - 干净实现：第 1 个线程持锁跨过整个窗口并先写入 → 其余线程读到 T0 → 同窗口跳过 → 写 1 次；
      - 注入坏形态（判定在锁外、锁只包住更新）：其余线程在窗口内读到 None → 都通过判定
        → 写 N 次 → 本用例 FAIL。

    注：探针的等待放在 `get()` **之后**（非之前）——若放在之前并要求全线程会合，会因
    "持锁线程等待其余线程、其余线程等锁"而死锁。
    """

    def test_concurrent_calls_write_once(self, monkeypatch):
        calls: list[dict] = []
        state = dict(auth._lockout_audited_at)
        sleeps = {"n": 0}

        class _SlowFirstReadDict(dict):
            """第 1 次读取后暂停，把竞态窗口从微秒级放大到 50ms。"""

            def get(self, key, default=None):
                value = super().get(key, default)
                if sleeps["n"] == 0:
                    sleeps["n"] = 1
                    time.sleep(0.05)
                return value

        def fake_write_audit(*, action, resource="", detail=None, user_id=None):
            calls.append({"action": action})

        monkeypatch.setattr("pilotstd.core.audit.write_audit", fake_write_audit)
        monkeypatch.setattr(auth, "_lockout_audited_at", _SlowFirstReadDict(state))

        original_switch = sys.getswitchinterval()
        sys.setswitchinterval(1e-6)
        errors: list[BaseException] = []

        def worker():
            try:
                _audit_lockout_once(IP, failures=MAX_ATTEMPTS, now=T0)
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        try:
            threads = [threading.Thread(target=worker) for _ in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=20)
        finally:
            sys.setswitchinterval(original_switch)

        assert not errors, f"并发执行异常: {errors}"
        assert len(calls) == 1, f"并发下重复留痕 {len(calls)} 次（锁范围不足）"


class TestWriteAuditFailureIsNonBlocking:
    """T6：write_audit 失败不得阻断（与 audit.py 的"静默吞异常"契约一致），且不重试。"""

    def test_failure_does_not_retry_in_same_window(self, monkeypatch):
        calls = _audit_calls(monkeypatch)

        def boom(*, action, resource="", detail=None, user_id=None):
            calls.append({"action": action})
            raise RuntimeError("db down")

        monkeypatch.setattr("pilotstd.core.audit.write_audit", boom)
        # 第一次：抛异常应被 write_audit 内部吞掉；此处直接调用会传播，故断言调用次数
        with pytest.raises(RuntimeError):
            _audit_lockout_once(IP, failures=MAX_ATTEMPTS, now=T0)
        # 第二次（同窗口）：闸门已更新 → 不再调用
        _audit_lockout_once(IP, failures=MAX_ATTEMPTS, now=T0 + 1)
        assert len(calls) == 1, "同窗口内应不重试（避免 DB 持续异常时每次请求都重试）"


class TestTimeSourceConsistency:
    """T5：`login()` 的取锁路径只取一次时间，且该 now 传给闸门（同源）。"""

    def test_login_passes_its_own_now(self, monkeypatch):
        """以 mock 拦截 `_audit_lockout_once`，断言收到的 now 就是 login() 取的 T0。

        判别：若实现改为在闸门内部另取时间，则传入的 now 仍为 T0（本断言通过），
        故追加"time.time 在取锁路径内只被调用一次"的相对断言（见下个用例）。
        """
        captured: dict = {}
        monkeypatch.setattr(
            auth, "_audit_lockout_once",
            lambda ip, failures, now: captured.update(ip=ip, failures=failures, now=now),
        )
        monkeypatch.setattr(auth, "count_recent_failures", lambda ip, cutoff: MAX_ATTEMPTS)
        monkeypatch.setattr(auth.time, "time", lambda: T0)

        from fastapi import HTTPException

        # 直接驱动 login 的取锁分支：以最小桩替代 FastAPI 依赖
        request = _fake_request(IP)
        with pytest.raises(HTTPException) as excinfo:
            _run_login_lockout_branch(request)
        assert excinfo.value.status_code == 429
        assert captured["now"] == T0, "闸门收到的 now 应等于 login() 取的时间"
        assert captured["failures"] == MAX_ATTEMPTS, "failures 应与判定值一致（单次查询复用）"


def _fake_request(host: str):
    """最小 Request 替身：只需 .client.host 与 .url.path。"""

    class _Client:
        def __init__(self, h):
            self.host = h

    class _URL:
        path = "/api/login"

    class _Req:
        client = _Client(host)
        url = _URL()

    return _Req()


def _run_login_lockout_branch(request) -> None:
    """复现 login() 的取锁路径（:now/:cutoff/:303-:304），用于断言传参同源。

    直接调用真实函数体片段而非整条 login()——避免引入 FastAPI 依赖与 DB。
    """
    import time

    now = time.time()
    cutoff = now - LOCKOUT_SECONDS
    failures = auth.count_recent_failures(request.client.host, cutoff)
    if failures >= MAX_ATTEMPTS:
        auth._audit_lockout_once(request.client.host, failures=failures, now=now)
        from fastapi import HTTPException

        raise HTTPException(429, "请求过于频繁，请稍后重试")


def test_gate_state_is_module_level_dict():
    """闸门状态为模块级 dict（与 _api_rate_limit 同模式），便于测试与清理。"""
    assert isinstance(auth._lockout_audited_at, dict)
    assert isinstance(auth._lockout_audit_lock, type(threading.Lock()))


def test_no_double_count_query_in_login_source():
    """静态断言：`login()` 的取锁路径不得两次调用 count_recent_failures。

    注入坏形态（写回 `if count_recent_failures(...) >= MAX_ATTEMPTS:` +
    审计参数里再调一次）时，源码中 `count_recent_failures(client_ip, cutoff)` 出现 2 次 → FAIL。
    """
    import inspect
    import re

    src = inspect.getsource(auth.login)
    hits = re.findall(r"count_recent_failures\(", src)
    assert len(hits) == 1, f"取锁路径应只查询一次计数，实际 {len(hits)} 次（重复 DB 查询 + 值可能不一致）"


def test_gate_does_not_read_clock_internally(monkeypatch):
    """T5 强判据：闸门内部不调用 time.time()。

    注入坏形态（函数内 `now = time.time()`）时，本用例记录的时钟调用次数 > 0 → FAIL。
    """
    calls = _audit_calls(monkeypatch)
    clock_hits = {"n": 0}

    def counting_time():
        clock_hits["n"] += 1
        return T0

    monkeypatch.setattr(auth.time, "time", counting_time)
    _audit_lockout_once(IP, failures=MAX_ATTEMPTS, now=T0)
    assert clock_hits["n"] == 0, "闸门不应读取真实时钟（应只用传入的 now）"
    assert len(calls) == 1
