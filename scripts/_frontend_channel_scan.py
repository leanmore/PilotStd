# 模块：脚本/门禁公共/前端渠道字面量扫描脚本
"""前端「硬编码渠道键」扫描（G-045 的 B4 与三层一致性测试**共用**）。

存在理由：B4（门禁）与三层一致性（测试）需要**同一口径**判定"前端是否仍硬编码渠道键"，
两处各写一份正则必然漂移，故抽为公共模块——**只负责扫描，不负责判定成败**
（键集、基线与阻断策略由调用方决定）。

**键集必须由调用方传入**（通常是 `channel_spec` 的声明）：早期版本把 4 个渠道键写死在
正则里，导致**新增第 5 个渠道时本扫描完全看不见它在前端是否被硬编码**——这是"盲区"，不是
"简化"。传入键集后，扫描范围随声明自动扩张。

判定口径（两处必须一致）：
1. 只认"**渠道键作为独立字符串字面量**"（`'wechat'` / `"wechat"`），不匹配子串
   （否则 `notification.channel.wechat` 这类 i18n 键会被误报）；
2. **先剥离 i18n 键字符串再匹配**——不用"整行白名单"。行级放行会漏报同一行里的真实硬编码，
   实测反例：`{ label: t('notification.channel.wechat'), value: 'wechat' }` 中
   `value: 'wechat'` 是真硬编码，却会被"含 i18n 键即整行放行"放过；
3. 跳过整行注释（模板 `<!--`、JS `//`/`/*`/`*`）——注释里的渠道名不构成可执行硬编码。
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from pathlib import Path

# 需扫描的前端文件（渠道声明/渲染的两处落点）
FRONTEND_FILES: tuple[str, ...] = (
    "web/src/components/NotificationConfig.vue",
    "web/src/views/NotificationLogsView.vue",
)

# i18n 键命名空间：`notification.channel.*` / `notification.config.*` 的**字符串本体**
_I18N_KEY_RE = re.compile(r"""['"]notification\.(?:channel|config)\.[A-Za-z0-9_.]*['"]""")
# 整行注释（模板注释 / JS 行注释 / 块注释续行）
_COMMENT_RE = re.compile(r"^\s*(?:<!--|//|/\*|\*)")
# "结构位"字面量：对象字面量里的 `key: 'x'` / `value: 'x'`（**与键集无关**）。
# 前一个字符不许是标识符字符，故 `labelKey:` 不会被误命中。
_STRUCT_RE = re.compile(r"""(?<![\w])(?:key|value)\s*:\s*['"]([a-z][a-z0-9_]*)['"]""")
# **渠道列表字面量**块起始锚点：结构位扫描只在块内进行。
# 为什么必须限定块：同一文件里 `value: 'success'` / `'failed'` 是**日志状态**选项
# （`statusOptions`），不是渠道键——实测若不限定块，会把它们误判成"未知渠道键"。
_BLOCK_ANCHORS: dict[str, str] = {
    "web/src/components/NotificationConfig.vue": r"const CHANNELS = \[",
    "web/src/views/NotificationLogsView.vue": r"const channelOptions = computed\(\(\) => \[",
}


def _channel_block_lines(text: str, anchor: str) -> list[str]:
    """取出锚点数组字面量的行范围（从锚点行到首个以 `]` 开头的行）。"""
    lines = text.splitlines()
    pattern = re.compile(anchor)
    for start, line in enumerate(lines):
        if pattern.search(line):
            for end in range(start, len(lines)):
                if lines[end].lstrip().startswith("]"):
                    return lines[start : end + 1]
            return lines[start:]
    return []


def literal_re(keys: Iterable[str]) -> re.Pattern[str]:
    """按渠道键集构造"独立字符串字面量"正则（长键优先，避免前缀互相吃掉）。"""
    ordered = sorted({re.escape(k) for k in keys}, key=len, reverse=True)
    return re.compile(rf"""(?<![\w.])['"]({"|".join(ordered)})['"](?![\w])""")


def strip_i18n_keys(line: str) -> str:
    """移除行内的 i18n 键字符串本体，返回用于字面量匹配的剩余文本。"""
    return _I18N_KEY_RE.sub("''", line)


def scan_file(path: Path, keys: Sequence[str]) -> list[tuple[int, str, str]]:
    """扫描单个文件，返回**未豁免**的硬编码清单：`(行号, 渠道键, 原行文本)`。"""
    pattern = literal_re(keys)
    hits: list[tuple[int, str, str]] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if _COMMENT_RE.match(raw):
            continue
        match = pattern.search(strip_i18n_keys(raw))
        if match:
            hits.append((lineno, match.group(1), raw.strip()))
    return hits


def scan(
    root: Path, keys: Sequence[str], files: tuple[str, ...] = FRONTEND_FILES
) -> list[tuple[str, int, str, str]]:
    """扫描全部目标文件，返回 `(相对路径, 行号, 渠道键, 原行文本)` 清单。"""
    out: list[tuple[str, int, str, str]] = []
    for rel in files:
        for lineno, key, text in scan_file(root / rel, keys):
            out.append((rel, lineno, key, text))
    return out


def found_keys(
    root: Path, keys: Sequence[str], files: tuple[str, ...] = FRONTEND_FILES
) -> set[str]:
    """扫描得到的渠道键集合（供"前端集合 vs spec 集合"的一致性判定）。"""
    return {key for _, _, key, _ in scan(root, keys, files)}


def structural_keys(root: Path, files: tuple[str, ...] = FRONTEND_FILES) -> set[str]:
    """扫"渠道列表字面量"块内（`key:` / `value:` 的值），**与调用方传入的键集无关**。

    为什么需要它：`found_keys` 只能看见"传入的键"——若前端声明了一个 spec 未包含的
    **新键**（如把 `'gamma'` 写进渠道列表），键集扫描**完全看不见**（"已知键的子集"
    约束恒真）。结构位扫描不看键集，故能发现未知键。

    为什么限定块：同文件里还有别的 `value:` 字面量（如日志状态 `success`/`failed`），
    不限定范围会把它们误判成未知渠道键（实测）。
    """
    out: set[str] = set()
    for rel in files:
        anchor = _BLOCK_ANCHORS.get(rel)
        if not anchor:
            continue
        block = _channel_block_lines((root / rel).read_text(encoding="utf-8"), anchor)
        for raw in block:
            if _COMMENT_RE.match(raw):
                continue
            out.update(_STRUCT_RE.findall(strip_i18n_keys(raw)))
    return out
