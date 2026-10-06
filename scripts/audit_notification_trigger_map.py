#!/usr/bin/env python
"""按需运行时校验：事件触发点地图（P6/P7 甲案，2026-10-06）。

**定位：开发/诊断工具，不进快闸、不进 CI 阻断链**——用户裁定"防漂移门禁必须是**声明式**
（注册时必填字段）而非**过程式**（每次跑一遍全量插桩）"。因此：

- **门禁**由 `EventSpec.verify`（注册期必填，漏填即 `TypeError`）+ 覆盖审计的静态闭集校验承担；
- **本工具**只在"想核对声明与真实触发点是否一致"时**手动**运行，输出地图与差异，**默认不阻断**。

用法（仓库根目录）：
    python scripts/audit_notification_trigger_map.py            # 精简场景集（约 90 秒）
    python scripts/audit_notification_trigger_map.py --full     # 全量 tests/（约 13 分钟）
    python scripts/audit_notification_trigger_map.py --full --strict   # 声明 e2e 却未观测到 ⇒ 退出码 1

口径说明：`verify="e2e"` 的含义是"**全量套件可观测**"（分类依据即 `--full` 的实测地图）；
因此 `--strict` 应与 `--full` 搭配使用——精简模式本就会漏掉多数事件的驱动用例。

插桩点（三层，覆盖动态触发与门面转发）：
    ① `NotificationManager.send_event`（业务规范入口）
    ② `NotificationAggregator.push`（聚合入口，含桌面端直构消息）
    ③ `_dispatcher.send_now`（最终投递，附带渠道上下文）
"""

from __future__ import annotations

import argparse
import functools
import inspect
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 精简场景集：覆盖各条业务链路的代表用例（含真链路 e2e 与聚合时序）
FOCUSED = (
    "tests/test_notification_e2e.py",
    "tests/integration/test_favorite_download_chain_e2e.py",
    "tests/test_notification_phase3_e2e_loop.py",
    "tests/test_aggregate_buffer.py",
    "tests/test_notification_desktop_toast.py",
)

# 记录时跳过的帧：通知包内部（插桩点自身）、本工具、pytest 与标准库
_SKIP = ("/pilotstd/core/notification/", "/audit_notification_trigger_map.py", "/_pytest/", "/unittest/",
         "/site-packages/")


def _caller() -> str:
    """首个位于 `pilotstd|docker|tests` 的调用方 `相对路径:行号`。

    跳过通知包内部与本工具自身（否则会把插桩点记成"触发点"——实测踩过）；
    **保留 `tests/` 帧**：它代表驱动该事件的用例，是有效信息。
    """
    for frame in inspect.stack()[2:]:
        fn = frame.filename.replace("\\", "/")
        if any(s in fn for s in _SKIP):
            continue
        for marker in ("/pilotstd/", "/docker/", "/tests/"):
            if marker in fn:
                rel = marker.strip("/") + "/" + fn.split(marker, 1)[1]
                return f"{rel}:{frame.lineno}"
    return "<未定位>"


def collect(targets: list[str]) -> dict[str, list[dict]]:
    """插桩并在进程内跑测试，返回 `事件 -> [站点记录]`。

    插桩采用**替换类属性**的方式（而非包装实例），因为生产代码里的调用全部是
    调用期属性查找（`_dispatcher.send_now(...)` / `self.send_event(...)`），
    替换类属性即可覆盖"动态触发 + 门面转发"两类路径。
    """
    records: dict[str, list[dict]] = {}

    def note(event_type: str, via: str) -> None:
        """记录一次触发（同 `(方式, 站点)` 去重，避免同一处触发把地图刷爆）。"""
        if not event_type:
            return
        rec = {"via": via, "site": _caller(), "test": os.environ.get("PYTEST_CURRENT_TEST", "")}
        bucket = records.setdefault(event_type, [])
        if not any(r["via"] == via and r["site"] == rec["site"] for r in bucket):
            bucket.append(rec)

    from pilotstd.core.notification import _dispatcher
    from pilotstd.core.notification.aggregate_buffer import NotificationAggregator
    from pilotstd.core.notification.manager import NotificationManager

    orig_send_event = NotificationManager.send_event
    orig_push = NotificationAggregator.push
    orig_send_now = _dispatcher.send_now

    @functools.wraps(orig_send_event)  # 保签名：测试会断言 `send_event` 的参数名
    def send_event(self, event_type, *a, **k):  # noqa: ANN001
        """① 业务规范入口：绝大多数事件的触发点。"""
        note(str(event_type), "manager.send_event")
        return orig_send_event(self, event_type, *a, **k)

    @functools.wraps(orig_push)
    def push(self, event_type, *a, **k):  # noqa: ANN001
        """② 聚合入口：覆盖"绕过管理者、直接构造消息"的路径（如桌面端气泡）。"""
        note(str(event_type), "aggregator.push")
        return orig_push(self, event_type, *a, **k)

    @functools.wraps(orig_send_now)
    def send_now(host, msg, target_channels):  # noqa: ANN001
        """③ 最终投递：补上渠道上下文，用于核对"事件 → 渠道"的实际走向。"""
        note(str(getattr(msg, "event_type", "")), "dispatcher.send_now")
        return orig_send_now(host, msg, target_channels)

    NotificationManager.send_event = send_event  # type: ignore[method-assign]
    NotificationAggregator.push = push  # type: ignore[method-assign]
    _dispatcher.send_now = send_now  # type: ignore[assignment]

    import pytest

    # 进程内跑测试：插桩只在本次进程生效，测试结束后随进程退出，无需还原。
    pytest.main(["-q", "-p", "no:cacheprovider", "--no-header", *targets])
    return records


def main() -> int:
    """命令行入口：跑一档场景集，打印"声明 vs 观测"地图，并按 `--strict` 决定退出码。"""
    parser = argparse.ArgumentParser(description="事件触发点运行时地图（按需校验，非门禁）")
    parser.add_argument("--full", action="store_true", help="跑全量 tests/（排除 tests/gui）")
    parser.add_argument("--strict", action="store_true", help="声明 e2e 却未观测到 ⇒ 退出码 1")
    parser.add_argument("--json", default="", help="把地图写入该 JSON 路径")
    args = parser.parse_args()

    targets = ["tests", "--ignore=tests/gui"] if args.full else [t for t in FOCUSED if (ROOT / t).exists()]
    os.chdir(ROOT)
    records = collect(targets)

    from pilotstd.core.notification.event_spec import EVENT_SPECS

    missing = [
        s.key
        for s in EVENT_SPECS
        if s.verify == "e2e" and not records.get(s.key)
    ]
    print("\n==== 运行时地图（声明 vs 观测）====")
    print(f"{'事件':<34}{'声明':<10}{'观测站点'}")
    for spec in EVENT_SPECS:
        recs = records.get(spec.key, [])
        site = recs[0]["site"] if recs else "—"
        flag = "✅" if recs else ("⚠️" if spec.verify == "e2e" else "（已声明非 e2e，无需观测）")
        print(f"{spec.key:<34}{spec.verify:<10}{site}  {flag}")

    print(
        f"\n观测到 {len([1 for s in EVENT_SPECS if records.get(s.key)])}/{len(EVENT_SPECS)} 个已登记事件；"
        f"声明 e2e 但未观测到 {len(missing)} 个"
    )
    if missing:
        print("  未观测（声明 e2e）：", ", ".join(missing))
        print("  ⇒ 若属'极难触发'，请把该事件声明改为 manual/ui_only（**不要求** 42/42 覆盖）")
    if args.json:
        pathlib.Path(args.json).write_text(
            json.dumps({k: v for k, v in records.items()}, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"地图已写入 {args.json}")
    return 1 if (args.strict and missing) else 0


if __name__ == "__main__":
    raise SystemExit(main())
