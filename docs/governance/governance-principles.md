# 治理体系原则

| 属性 | 值 |
|------|-----|
| 状态 | 已批准 |
| 版本 | v1.0 |
| 批准日期 | 2026-07-14 |

本文档记录 PilotStd 项目治理体系本身的元原则——为什么这样治理、如何决策、如何追踪。

## 一、治理三件套原则

PilotStd 治理体系基于三条不可分割的支柱：

| 支柱 | 含义 | 缺失后果 |
|------|------|---------|
| 自动化测试 | 核心功能有回归测试覆盖，CI 自动运行 | 功能退化静默发生 |
| 门禁检查 | CI 中自动化检查脚本，阻断不合规变更 | 过程产物混入仓库、测试覆盖遗漏 |
| 文档登记 | 设计决策、已知问题、入仓标准有书面记录 | 决策理由丢失、技术债不可见 |

**三者缺一不可**。代码变更必须同步更新对应测试、门禁规则和关联文档：

```
代码变更 → 测试更新（防止回归）
         → 门禁更新（如果变更触发新规则）
         → 文档更新（如果变更影响设计决策或已知问题）
```

## 二、本次治理决策链

**决策时间**：2026-07-14

**背景**：v0.67.0 发布后，发现 4 个功能退化问题（DIN EN 解析、团体标准路由、序号动态宽度、汇总弹窗），暴露了测试覆盖和门禁体系的缺口。

**决策顺序**（按优先级推进）：

| 阶段 | 优先级 | 内容 | 交付物 | Commit |
|------|--------|------|--------|--------|
| P0 | 修复 | 修复 4 个功能退化 + 补充回归测试 | `tests/test_scanner.py`、`test_query.py`、`test_table.py` | `9c483137`、`13c324f7` |
| P1 | 文档 | 记录已知问题（技术债） | `docs/testing/known-issues.md` | `75a607e2` |
| P2 | 决策 | ADR-001 记录 ModalDialogAutoClicker 方案 | `docs/adr/ADR-001-*.md` | `d3eca1f3` |
| P3 | 门禁 | G-029 核心模块变更 → 测试同步检查 | `scripts/check_g_029_test_coverage.py` | `d551e3cf` |
| — | 元文档 | 本文档 + 入口索引 | `docs/governance/governance-principles.md` | 当前 |

## 三、门禁设计原则

### 3.1 历史违规不追溯

门禁仅检查**本次变更**中新增或修改的内容，不对历史代码进行全量扫描。理由：

- 全量扫描产生大量噪音，掩盖真正需要关注的新问题
- 历史代码的合规性通过渐进式重构逐步改善
- 门禁的目标是"防止恶化"而非"一次性修复所有问题"

### 3.2 结构合规 ≠ 功能正确

门禁保证的是**结构层面的最低标准**（文件放对位置、测试文件存在、没有硬编码敏感信息），而非功能正确性。功能正确性由测试套件保证。

### 3.3 分层设计

| 层级 | Job | 检查内容 |
|------|-----|---------|
| L1 — 文件入仓 | `repo-compliance` | 白名单/黑名单/文件名模式/根目录/G-019 |
| L2 — 测试覆盖 | G-029 | 核心模块变更 ↔ 测试文件同步 |
| L3 — 安全扫描 | `security-scan` | 密钥泄露、依赖漏洞 |
| L4 — 代码质量 | Ruff + Mypy | 格式、类型、死代码 |

## 四、承诺追踪机制

当决策者说"先记住，下次处理"时，方案进入追踪清单。追踪清单的形式：

- 短期（当次会话）：TODO 列表或会话上下文
- 中期（跨会话）：`docs/testing/known-issues.md` 或 `docs/architecture/technical-debt-registry.md`
- 长期（跨版本）：GitHub Issue

**执行者要求**：每次输出新指令前，强制检查追踪清单中是否有待处理项。

## 五、关联分析机制

多问题并发时，执行者必须先分析关联性再输出指令：

1. **识别关联**：问题 A 的修复是否影响问题 B 的根因？
2. **确定顺序**：如果 A 修复后 B 的根因改变，先修 A 再重新分析 B
3. **合并测试**：关联问题的回归测试应合并或交叉验证

示例：本次 P0 中，"DIN EN 解析"修复影响了"汇总弹窗"的 `_suppress_dialogs` 机制——两者都涉及 `std_utils.py` 的 `parse_std_number`。必须先修解析，再在修复弹窗时考虑解析变更的影响。

## 六、相关文档索引

| 文档 | 用途 |
|------|------|
| [file-inclusion-criteria.md](file-inclusion-criteria.md) | 文件入仓五条规则 |
| [capabilities_registry.md](capabilities_registry.md) | 非功能性能力登记簿 |
| [../testing/known-issues.md](../testing/known-issues.md) | 已知问题及技术债追踪 |
| [../adr/ADR-001-modal-dialog-auto-clicker.md](../adr/ADR-001-modal-dialog-auto-clicker.md) | 模态对话框自动处理方案 |
| [../architecture/technical-debt-registry.md](../architecture/technical-debt-registry.md) | 技术债登记 |
| [../../CONTRIBUTING.md](../../CONTRIBUTING.md) | 贡献指南（含门禁脚本速查） |
| [../../scripts/check_g_029_test_coverage.py](../../scripts/check_g_029_test_coverage.py) | G-029 测试覆盖门禁 |
| [../../.github/scripts/check-repo-compliance.sh](../../.github/scripts/check-repo-compliance.sh) | 入仓合规门禁 |
