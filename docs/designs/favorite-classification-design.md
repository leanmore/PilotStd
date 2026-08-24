# 收藏分类数据模型设计（favorite-classification）

> **版本**：v1.0（设计稿，待顾问审核）
> **关联**：Backlog P2-4（收藏分类 standard_type 字段）、P2-5（收藏去重机制）、P2-6（收藏列表按分类导出）
> **状态**：设计阶段——**不修改任何代码**；审核通过后经 `_migrate_v57.py` 实施

---

## 一、现状分析

### 1.1 收藏相关表结构（实测 SQLite DDL）

| 表 | 关键字段 | 现状 |
|----|---------|------|
| `user_favorites` | `id, user_id, record_id, status, local_path, error_message, created_at, updated_at, publish_date, last_archive_attempt, archive_retry_count` | 唯一约束 `UNIQUE(user_id, record_id)`；`record_id` → `announcement_record.id` |
| `favorite_downloads` | `id, favorite_id, record_id, status, local_path, error_message, retry_count, last_attempt, created_at, updated_at, user_id, standard_no, standard_name` | 唯一约束 `UNIQUE(favorite_id, record_id)`；`favorite_id` → `user_favorites.id`（ON DELETE CASCADE） |
| `download_queue` | `id, standard_number, standard_name, publish_date, expected_available, created_at, retry_count, status` | 无 user_id / 无类型字段 |
| `announcement_record` | `id, source_site, pid, announce_no, standard_number, std_name, ...` | `source_site ∈ {announcement_gb, announcement_hb, announcement_db}`（`constants/announce_types.py:8-13`） |

### 1.2 现有去重逻辑痛点

- **去重粒度**：`(user_id, record_id)`（`docker/api/favorites.py:84-93`）——按"公告记录行"去重，**非标准号维度**。同一标准号出现在不同公告（如 gb 与 hb 站各发一次）会创建两条收藏
- **无类型字段**：`user_favorites` / `favorite_downloads` / `download_queue` 均无 `standard_type`，无法按国/行/地标筛选或导出
- **类型可推导但未落库**：`pilotstd/core/std_utils.py:15-60` `classify_std_code()` 已实现七类分类（`gb/industry/db/iso_iec/foreign/group/enterprise`），基于标准号前缀 + `industry_lookup.build_code_mapping()`；`announcement_record.source_site` 也携带 gb/hb/db 桶信息——但均未持久化到收藏表

### 1.3 导出功能现状

- 仅有 `GET /api/export/standards`（`docker/api/export.py:16`，导出标准库文件清单，csv/json）
- **无收藏列表导出**；无按类型筛选

---

## 二、数据模型设计

### 2.1 表结构变更（`_migrate_v57.py` 实施）

**新增 `standard_type` 列**（三张表同步加，保持查询路径一致）：

```sql
-- user_favorites：收藏主表（SSOT 落库点）
ALTER TABLE user_favorites ADD COLUMN standard_type TEXT NOT NULL DEFAULT 'unknown';

-- favorite_downloads：收藏下载记录（冗余同步，便于下载链筛选）
ALTER TABLE favorite_downloads ADD COLUMN standard_type TEXT NOT NULL DEFAULT 'unknown';

-- download_queue：下载队列（冗余同步，队列筛选/排序用）
ALTER TABLE download_queue ADD COLUMN standard_type TEXT NOT NULL DEFAULT 'unknown';
```

> **设计决策**：三表都加列——`user_favorites` 是 SSOT 权威；`favorite_downloads`/`download_queue` 为**冗余缓存列**（见 2.3 SSOT 决策），避免下载/队列路径频繁 JOIN。

### 2.2 枚举定义

**取值采用语义化命名**（拒绝 gb/hb/db 缩写，避免 hb 歧义）：

| 枚举值 | 含义 | 映射来源 |
|--------|------|---------|
| `national` | 国家标准（GB/GB/T/GB/Z/GSB） | `classify_std_code` → `gb`；`source_site=announcement_gb` |
| `industry` | 行业标准（SH/HG/JB/... 全行业统称桶） | `classify_std_code` → `industry`；`source_site=announcement_hb` |
| `local` | 地方标准（DB + 行政区划码） | `classify_std_code` → `db`；`source_site=announcement_db` |
| `enterprise` | 企业标准（SG 等） | `classify_std_code` → `enterprise` |
| `group` | 团体标准（T/ 开头） | `classify_std_code` → `group` |
| `foreign` | 国外标准（ISO/IEC/BS/EN 等） | `classify_std_code` → `iso_iec`/`foreign` |
| `unknown` | 推断失败默认值（**禁止强行猜测**） | 兜底 |

> **hb 桶定义**：映射自 `announcement_hb` 源的值统一落为 `industry`——语义为"**所有行业标准的统称桶**"（覆盖 SH/HG/JB/TB 等全部行业代号），由 `industry_lookup.INDUSTRY_MAP` 提供前缀全集。

**前缀映射表**（回填用正则，源自 `classify_std_code` + `INDUSTRY_MAP`）：

```python
# 推断优先级（自上而下，命中即止）
PATTERNS = [
    (r'^(GB/T|GB/Z|GB|GSB)\s', 'national'),           # 国标
    (r'^DB\s?\d{2,4}(/T)?', 'local'),                  # 地方标准
    (r'^T/[A-Z]', 'group'),                            # 团体标准（T/ 前缀）
    (r'^(SG)\s', 'enterprise'),                        # 企业标准
    (r'^(SH|HG|JB|TB|YB|QB|JC|DL|SY|MT|HJ|CJ|JG|LD|GA|YY|WS|JTG|SL|NB|FZ|QC|JT)\s', 'industry'),
    # 其余行业代号走 build_code_mapping() 全表匹配（industry_lookup.INDUSTRY_MAP）
]
# 国外标准：FOREIGN_CODE_SET / ISO_IEC_SET 前缀匹配（std_utils.py:32-40）
```

### 2.3 SSOT 决策

**`standard_type` 是"反范式缓存字段"**（非 JOIN 计算字段）：

- **权威源**：`announcement_record.source_site`（采集时确定，gb/hb/db 三桶）+ 标准号前缀（补充 enterprise/group/foreign 等非公告源类型）
- **缓存策略**：收藏动作落库时**一次性写入**（`favorites.py` add 流程），后续不改
- **最终一致性保证**：
  1. 收藏写入时从 `announcement_record.source_site` 映射（`SOURCE_SITE_TO_TYPE`，gb→national、hb→industry、db→local），映射不到的用 `classify_std_code(standard_number)` 兜底
  2. 两者都失败 → `unknown`
  3. **无定时重算**——`standard_type` 在收藏创建时冻结（公告源类型是采集时事实，不随标准号变化）；`favorite_downloads`/`download_queue` 从 `user_favorites` 复制，三者通过 `favorite_id`/`standard_number` 关联可追溯
  4. 若未来公告源重分类（罕见），提供一次性 `_migrate_v5X` 重算迁移（不在本设计范围）

### 2.4 存量回填策略

**推断逻辑**（按优先级）：
1. `source_site` 映射：`announcement_record.source_site` → `SOURCE_SITE_TO_TYPE`（gb/hb/db 三桶，最高置信）
2. `classify_std_code(standard_number)`：非公告源收藏（手动/查询收藏）用标准号前缀正则 + INDUSTRY_MAP
3. 两者均失败 → `unknown`

**正则示例**（见 2.2 `PATTERNS`）：`^GB/T\s` → national、`^DB\s?\d{2}` → local、`^SH\s` → industry。

**置信度处理**：
- 推断命中 source_site 映射 → 高置信（公告采集事实）
- 仅前缀正则命中 → 中置信（标准号格式规范时可靠）
- 无命中 → **`unknown`，禁止强行猜测**（避免 HG 误判为 GB 等）
- 回填日志记录每条的推断来源（`source_site` / `prefix` / `unknown`），供审计

**性能控制**（分批回填，避免长事务锁表）：

```sql
-- 每批 1000 条（chunk_size=1000），逐批 UPDATE + COMMIT
-- 伪代码：
while rows_remaining:
    rows = SELECT id, standard_number, record_id
           FROM user_favorites
           WHERE standard_type = 'unknown'
           LIMIT 1000
    for row in rows:
        st = infer_type(row)          # source_site → classify_std_code → unknown
        UPDATE user_favorites SET standard_type = st WHERE id = row.id
    # 同步 favorite_downloads / download_queue（按 standard_no 匹配）
    COMMIT
    sleep(0.1)   -- 节流，避免 IO 峰值
```

**迁移幂等性**（`_migrate_v57.py` 设计）：

```python
@migration(57)
def _migrate_v57_favorite_standard_type(db):
    """幂等补列 + 存量回填（chunked）。"""
    # 1) PRAGMA 检查三表列存在性，缺失才 ALTER（幂等）
    # 2) 回填仅处理 standard_type = 'unknown' 的行（可重跑）
    # 3) 失败逐条记录日志并 continue（不中断整批）
    # 4) 版本推进由迁移框架自动处理
```

---

## 三、去重逻辑设计

### 3.1 去重粒度

**`(user_id, standard_number, standard_type)` 联合唯一**：

```sql
-- 迁移中为 user_favorites 建唯一索引（先清洗存量冲突，见 3.4）
CREATE UNIQUE INDEX IF NOT EXISTS uq_fav_user_std_type
  ON user_favorites(user_id, standard_number, standard_type);
```

### 3.2 同标准号跨类型处理

**允许同时收藏**（如 GB/T 1234 与 HG/T 1234 是不同标准）——但：
- 收藏时若 `(user_id, standard_number)` 已存在但 `standard_type` 不同 → **允许新增**，返回 `type_conflict` 提示，前端 UI 明确展示两个类型标签
- 若 `(user_id, standard_number, standard_type)` 完全相同 → 返回 `already_exists`（现有行为）

### 3.3 拦截时机

**收藏动作时拦截**（`favorites.py` add 流程内）：
- 现有 `(user_id, record_id)` 查重保留（公告记录级）
- **新增** `(user_id, standard_number, standard_type)` 查重（标准级）
- 理由：拦截在入口最直观、错误提示即时；入库去重会引入异步竞态且难给用户反馈

### 3.4 存量冲突清洗

现有数据 `UNIQUE(user_id, record_id)` 下**不可能存在**同 record_id 重复，但**可能**存在"同 standard_number 不同 record_id（不同公告来源）"：

| 冲突场景 | 清洗策略 |
|---------|---------|
| `(user_id, standard_number)` 重复且 standard_type 相同 | **保留最早**（created_at 最早者），删除其余；下载记录随 favorite 级联删除 |
| `(user_id, standard_number)` 重复但 standard_type 不同 | **保留全部**（合法场景，3.2 允许）——无需清洗 |
| 回填后 `standard_type=unknown` 的重复 | 保留最早，删除其余（unknown 视为同桶） |

> 清洗需在**建唯一索引前**执行；清洗操作记入审计日志（`audit_logs` 表），保留被删记录 id 清单供人工复核。

### 3.5 用户反馈机制

- 收藏成功：响应含 `standard_type`（前端标签展示）
- 重复收藏：`already_exists`（含现有类型）
- 跨类型重复：`type_conflict`（提示"已收藏同号不同类型"）
- `unknown` 类型：前端展示"类型待确认"样式（见 §六）

---

## 四、导出功能设计

### 4.1 格式与筛选

- **格式**：CSV / JSON（对齐现有 `export_standards` 风格）；Excel 不在首期（依赖重，CSV 可被 Excel 打开）
- **筛选**：`?standard_type=national|industry|local|unknown`（可选，缺省导出全部）

### 4.2 字段清单

```
favorite_id, standard_number, standard_name, standard_type, status,
local_path, publish_date, created_at, updated_at, source_site
```

### 4.3 API 设计

```http
GET /api/favorites/export?format=csv&standard_type=national
```

- **大数据量异步**：收藏量级（预估 <10 万行）**首期同步返回**；预留 `?async=true` 走 `task_queue`（现有任务队列）生成文件，前端轮询下载——量级达标后再启用，避免过度设计

---

## 五、事件通知联动

| 设计项 | 决策 |
|--------|------|
| 通知内容含 standard_type | ✅ `favorite_created` 事件 payload 增加 `standard_type` 字段；`_build_favorite_created_message` builder 追加"类型：行业标准"行（仅当非 unknown） |
| 细粒度事件 | 暂不新增（现有 `favorite_created`/`download_*` 够用）；`standard_type` 作为附加字段，避免事件爆炸 |

---

## 六、前端交互设计建议

| 设计项 | 建议 |
|--------|------|
| 收藏列表 UI | **Tab 切换**（全部/国家标准/行业标准/地方标准/其他）+ 保留现有列表；Tab 数固定 5 个，避免下拉筛选层级过深 |
| 类型标签 | 收藏项右侧小标签（national=蓝、industry=橙、local=绿、unknown=灰虚线） |
| unknown 呈现 | 灰色"类型待确认"徽标 + tooltip"来源无法识别，可在详情页手动标注"；**不阻塞收藏/下载** |
| 导出按钮 | 收藏列表页右上角"导出"按钮 → 弹窗选格式（CSV/JSON）+ 当前 Tab 类型筛选；交互流：点击 → 选择 → 触发下载 |

---

## 七、测试与验证策略

### 7.1 迁移 Dry-run

1. staging 环境执行迁移前备份 DB
2. `_migrate_v57.py` 支持 `--dry-run` 参数：仅输出影响行数报告（各表待回填行数、推断分布统计），**不实际写入**
3. 输出示例：`user_favorites: total=5231, national=3102, industry=1204, local=502, unknown=423 (8.1%)`

### 7.2 数据校验 SQL

```sql
-- 类型分布（unknown 占比 >10% 需人工审查）
SELECT standard_type, COUNT(*) FROM user_favorites GROUP BY standard_type;

-- 一致性：favorite_downloads.standard_type 应等于 user_favorites.standard_type
SELECT COUNT(*) FROM favorite_downloads f
JOIN user_favorites u ON f.favorite_id = u.id
WHERE f.standard_type != u.standard_type;
```

### 7.3 单元测试

- 迁移幂等（重复执行不报错、不回填已处理行）
- `infer_type` 纯函数测试（source_site 映射 / 正则 / unknown 兜底）
- 去重拦截（同类型重复 / 跨类型允许）
- 导出筛选（按类型过滤）

---

## 八、实施排期建议

| 阶段 | 内容 | 依赖 |
|------|------|------|
| 1. 迁移 | `_migrate_v57.py` 补列 + 回填 + 唯一索引 + Dry-run 验证 | 无 |
| 2. 后端 API | favorites add 写 standard_type、export 端点、去重拦截 | 阶段 1 |
| 3. 前端 UI | Tab 切换、类型标签、unknown 徽标、导出按钮 | 阶段 2 |
| 4. 数据清洗 | 存量冲突清洗脚本 + 审计 | 阶段 1 后独立 |

> **风险提示**：阶段 1 的唯一索引需先完成 3.4 清洗，否则建索引失败；unknown 占比过高（>10%）时应先人工审查推断规则再继续。

---

## 完成标准自查

- [x] 数据模型变更（含 DDL）明确，SSOT 决策记录（反范式缓存 + 一致性机制）
- [x] 枚举定义语义化（national/industry/local/enterprise/group/foreign/unknown），hb 桶明确定义
- [x] 存量回填含正则示例、置信度处理（unknown 禁猜）、分批方案（chunk=1000）
- [x] 去重逻辑含存量冲突清洗（保留最早/跨类型保留）
- [x] 导出功能含 API 设计（同步 + 异步预留）
- [x] 前端交互建议（Tab/标签/unknown/导出）
- [x] 测试验证策略（Dry-run + 校验 SQL + 单元测试）
- [x] 实施排期建议（四阶段）
