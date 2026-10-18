"""G-049：防膨胀门禁——通知模块 6 个热点文件 + `manager.py` 有效代码行上限。

为什么需要单独一条门禁：G-010 只提供 400/500 两档**通用**线，无法表达"manager.py 降为
装配 + 薄门面后**不得回涨**"以及通知模块其他热点文件的**专项**约束。

**口径与 G-010 保持一致**：直接复用其 `_count_logical_lines`（排除空行与纯注释行），
避免同一项目出现两套"有效行"定义。

**覆盖范围（A-2，2026-10-18）**：从只锁 `manager.py` 扩展到通知模块 6 个热点文件；
`event_spec_data.py` / `channel_spec_data.py` 是静态规格数据表（增长属业务预期），
不纳入本门禁，避免"每加一个渠道就红"。

**不改被测文件**：本脚本只读，不做任何写入（避免"门禁自触发"竞态）。
"""

import sys
from pathlib import Path

# 控制台编码兼容（与同目录其它门禁脚本同口径）：Windows 的 GBK 控制台无法编码 ✅，
# 不加这段会在**判定其实通过**时抛 UnicodeEncodeError → 假性 exit 1（pre-commit 红）。
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

sys.path.insert(0, str(Path(__file__).resolve().parent))


# (文件, 有效行上限)；上限 = 当前有效行 + 约 5% 余量，回涨即红。
TARGETS: list[tuple[Path, int]] = [
    (Path("pilotstd/core/notification/manager.py"), 340),
    (Path("pilotstd/core/notification/aggregate_buffer.py"), 400),
    (Path("pilotstd/core/notification/_builders_batch.py"), 380),
    (Path("pilotstd/core/notification/callback_service.py"), 350),
    (Path("pilotstd/core/notification/_builders_system.py"), 350),
    (Path("pilotstd/core/notification/_manager_ops.py"), 350),
    (Path("pilotstd/core/notification/renderer.py"), 300),
]


def check_file(path: Path, max_effective: int) -> tuple[bool, int]:
    """返回 (是否通过, 有效行数)；目标缺失视为失败（有效行 0）。"""
    from check_g_010_code_size import _count_logical_lines

    if not path.is_file():
        return False, 0
    effective = _count_logical_lines(path.read_text(encoding="utf-8").splitlines(), ".py")
    return effective <= max_effective, effective


def main() -> int:
    """返回 0=PASS；1=FAIL（任一目标超限或缺失）。"""
    failed: list[str] = []
    for path, cap in TARGETS:
        ok, effective = check_file(path, cap)
        if not ok:
            failed.append(f"{path} 有效行 {effective} > {cap}" if effective else f"{path} 不存在")
        else:
            print(f"✅ {path.name} 有效行 {effective} ≤ {cap}")
    if failed:
        print("❌ G-049 防膨胀失败：")
        for item in failed:
            print(f"   {item}")
        print(
            "   处置：把新增逻辑移入独立模块（如 `_dispatcher.py` / `_suppression_queue.py`），"
            "保持热点文件为装配/薄门面"
        )
        return 1
    print(f"✅ G-049 通过：{len(TARGETS)} 个通知模块热点文件均未超限")
    return 0


if __name__ == "__main__":
    sys.exit(main())
