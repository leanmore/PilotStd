# 适配器 Fixture 统一 Schema

> 版本 v1.0 | 2026-07-24 | 覆盖 4 个新适配器

## 一、设计原则

1. **一文件一记录**：每个 fixture 文件包含单条 API 响应记录（非数组），便于测试独立断言
2. **字段名与 API 响应一致**：不做任何翻译或重命名，确保 fixture 与线上数据可直接比对
3. **真实数据脱敏**：使用真实字段值但替换具体内容为通用示例

## 二、通用 Schema

```json
{
  "standardNumber": "标准编号",
  "standardName": "标准名称",
  "publishDate": "YYYY-MM-DD",
  "implementationDate": "YYYY-MM-DD",
  "status": "现行|废止|即将实施|未知",
  "replaces": "代替标准编号或空字符串"
}
```

推荐字段命名（按 API 原始名称）：

| 适配器 | 编号字段 | 名称字段 | 发布日期 | 实施日期 | 状态字段 |
|--------|---------|---------|---------|---------|---------|
| energy | `stdCode` | `stdName` | `issueDate` | `actDate` | `state` |
| tdpress | `standardNumber` | `standardName` | `publicationDate` | `implementDate` | `standardStatus` |
| ncha | `standardNum` | `standardName` | `publishingDate` | `executeDate` | `standardStatusName` |
| miit | `bpiBzno` | `piProjectname` | `createTime` | `bpiJysstime` | (无，固定"现行") |

**规定**：fixture 中字段名必须与 API 原始响应中的 key **完全一致**。不定义中间格式或通用格式——这是 fixture 的核心价值：作为 API 变更的哨兵，字段名变化时测试直接失败。

## 三、各适配器 Fixture 清单

| 适配器 | Fixture 文件 | 记录数 | 特征标注 |
|--------|-------------|--------|---------|
| energy | `energy_sample.json` | 3 | `state: "现行"`, 日期为字符串 |
| tdpress | `tdpress_sample.json` | 3 | `standardStatus: "TRUE"/"FALSE"`, 日期为毫秒时间戳 |
| ncha | `ncha_wwt_sample.json` | 1 | WW/T 行标，`publishingDate: "2023/12/6 0:00"` |
| ncha | `ncha_gbt_sample.json` | 1 | GB/T 国标，日期格式同上 |
| miit | `miit_sample.json` | 1 | 字段名 `bpiBzno`/`piProjectname`（非标准命名） |

## 四、Fixture 维护规则

- **API 字段变更时**：同步更新 fixture，测试自动检测字段缺失
- **新增适配器时**：按本 Schema 创建 fixture，确保 `test_parse_result_*` 有数据源
- **Fixture 文件位置**：统一放在 `tests/fixtures/`，命名为 `<adapter>_<type>_sample.json`
- **禁止行为**：不应在 fixture 中嵌入 QueryResult 字段名（如 `standard_number`）——那是解析后的格式，fixture 保留原始格式以验证映射逻辑