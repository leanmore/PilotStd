#!/usr/bin/env python3
"""门禁共享：变更范围「不可知」必须 FAIL，不得静默跳过（U34 假绿修复）。

背景
----
G-013 / G-030 / G-031 / G-033 原先在「git 不可用 / 超时 / 命令非零退出」时返回空列表，
调用方把「空」解释成「本次无变更」→ 直接 PASS。于是门禁在**根本拿不到变更范围**时假绿，
而且是静默的：一次漏报会覆盖之后所有提交。

本模块只做两件事：
1. 把「基础设施失败」（git 缺失 / 超时 / OSError）立即翻译成 `ChangeSetUnavailable`；
2. 把「单条来源失败」记入账本，供调用方在**所有来源都失败**时统一判为不可知。

「范围为空」与「范围不可知」必须区分
------------------------------------
- 某条 git 命令成功返回 0、输出为空 → 合法结论「本次无变更」，门禁可以跳过；
- 所有来源都失败 → 不可知 → 必须 FAIL（否则就是假绿）。

若只把「结果为空」一律判 FAIL，干净仓库的每次提交都会失败，门禁会被迫绕过——那是另一种假绿。
部分来源不可用时本模块会显式打印（`report_partial`），不做静默退化。
"""

from __future__ import annotations

import subprocess
from pathlib import Path


class ChangeSetUnavailable(RuntimeError):
    """无法确定本次变更范围（git 不可用 / 超时 / 所有来源均失败）。"""


# 统一记账：一次门禁里的每条 git 查询都登记成功/失败，
# 由 require() 在「全军覆没」时抛错，避免调用方各自判断漏掉。
class ChangeScope:
    """一次门禁执行内的 git 查询账本。

    Args:
        cwd: 执行 git 命令的工作目录（应固定为仓库根，避免受调用方 cwd 影响）。
        timeout: 单条命令超时秒数。
    """

    def __init__(self, cwd: Path | str, timeout: int = 10) -> None:
        # 固定工作目录：调用方可能在任意 cwd 下运行门禁
        self._cwd = str(cwd)
        self._timeout = timeout
        # 成功次数与失败描述分开记，供 require()/report_partial() 使用
        self._successes = 0
        self._failures: list[str] = []

    @property
    def successes(self) -> int:
        """成功执行的来源条数（含「成功但结果为空」）。"""
        return self._successes

    @property
    def failures(self) -> list[str]:
        """失败来源的描述，供调用方显式打印（不静默）。"""
        return list(self._failures)

    def query(self, args: list[str]) -> str | None:
        """执行一条 git 查询。

        Args:
            args: 完整命令 argv，例如 ``["git", "diff", "--cached", "--name-only"]``。

        Returns:
            命令成功时返回 stdout（可能为空串）；命令非零退出时返回 None 并记账。

        Raises:
            ChangeSetUnavailable: git 无法执行（缺失 / 超时 / OS 错误）。
        """
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=self._cwd,
                timeout=self._timeout,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
            raise ChangeSetUnavailable(f"`{' '.join(args)}` 无法执行: {exc}") from exc

        if result.returncode != 0:
            stderr_lines = (result.stderr or "").strip().splitlines()
            hint = stderr_lines[-1] if stderr_lines else ""
            suffix = f" ({hint[:120]})" if hint else ""
            self._failures.append(f"`{' '.join(args)}` exit={result.returncode}{suffix}")
            return None

        self._successes += 1
        return result.stdout or ""

    def require(self, what: str) -> None:
        """校验「范围可知」；全部来源失败时抛错。

        Args:
            what: 人类可读的对象名，用于错误信息（如「本次变更文件范围」）。

        Raises:
            ChangeSetUnavailable: 没有任何来源成功。
        """
        if self._successes == 0:
            detail = "；".join(self._failures) or "没有任何 git 来源可用"
            raise ChangeSetUnavailable(f"无法获取{what}：{detail}")

    def report_partial(self, label: str = "变更范围") -> None:
        """部分来源不可用时显式打印，避免「悄悄退化」。"""
        if self._failures and self._successes:
            print(f"   ⚠️  {label}：{len(self._failures)} 个来源不可用，已用其余来源判定")
            for item in self._failures:
                print(f"      - {item}")
