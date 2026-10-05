"""G-049：防膨胀门禁——`manager.py` 有效代码行 ≤ 340（`04-refactor-P.md` §3.1 P4 的判据）。

为什么需要单独一条门禁：G-010 只提供 400/500 两档**通用**线，无法表达"manager.py 降为
装配 + 薄门面后**不得回涨**"这一**专项**约束（`04-refactor-P.md` §3.1 P4 明确判据 ≤340）。

**口径与 G-010 保持一致**：直接复用其 `_count_logical_lines`（排除空行与纯注释行），
避免同一项目出现两套"有效行"定义（决策者提醒：不确定口径时先读既有实现保持一致）。

**不改被测文件**：本脚本只读 `manager.py`，不做任何写入（避免"门禁自触发"竞态）。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


TARGET = Path("pilotstd/core/notification/manager.py")
MAX_EFFECTIVE_LINES = 340


def main() -> int:
    """返回 0=PASS；1=FAIL（超限或目标缺失）。"""
    # 口径复用：函数内导入 G-010 的计数函数（避免 E402；且**不使用 noqa**，遵 P-104 禁绕过）
    from check_g_010_code_size import _count_logical_lines
    if not TARGET.is_file():
        print(f"❌ G-049: 目标文件不存在: {TARGET}")
        return 1
    effective = _count_logical_lines(TARGET.read_text(encoding="utf-8").splitlines(), ".py")
    if effective > MAX_EFFECTIVE_LINES:
        print(
            f"❌ G-049 防膨胀失败: {TARGET} 有效行 {effective} > {MAX_EFFECTIVE_LINES}"
            f"（超出 {effective - MAX_EFFECTIVE_LINES} 行）"
        )
        print(
            "   处置：把新增逻辑移入 `_dispatcher.py` / `_suppression_queue.py` 或新模块，"
            "保持 manager.py 为装配 + 薄门面"
        )
        return 1
    print(f"✅ G-049 防膨胀通过: {TARGET} 有效行 {effective} ≤ {MAX_EFFECTIVE_LINES}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
