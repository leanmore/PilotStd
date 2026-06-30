# 剩余中难度函数拆分分析报告

## 汇总表

| # | 函数 | 文件 | 行数 | 内部阶段数 | 建议子函数数 | 难度 |
|---|------|------|------|-----------|-------------|------|
| 1 | `_on_download` | `ui/controllers/download_mixin.py` | 133 | 7 | 7 | 中 |
| 2 | `__init__` | `ui/pending_query_dialog.py` | 85 | 5 | 5 | 低 |
| 3 | `query_with_strategy` | `query/adapters/base.py` | 123 | 5 | 2 | 低 |
| 4 | `organize_skipped_dirs` | `manager/organize/mirror.py` | 82 | 3 | 5 | 中 |
| 5 | `update_container` | `docker/api/system.py` | 93 | 5 | 5 | 低 |
| 6 | `_build_message` | `core/notification/manager.py` | 169 | 15 | 16（字典分发） | 低 |
| 7 | `classify` | `manager/classifier.py` | 86 | 5 | 4 | 中 |
| 8 | `match_result` | `query/search_strategy.py` | 85 | 3 | 2 | 低 |
| 9 | `_csres_worker` | `query/engine/_batch.py` | 81 | 5 | 2 | 中 |
| 10 | `organize` | `manager/organize/organizer.py` | 130 | 4 | 4 | 中 |

---

## 低难度（5 个，可立即执行）

### 1. `__init__` — `ui/pending_query_dialog.py:32` (85 行)

**阶段分段：**

| 行号 | 行数 | 职责 |
|------|------|------|
| 34-41 | 8 | 基类构造 + 成员变量初始化 |
| 43-45 | 3 | 窗口标题 + 最小尺寸 + QVBoxLayout |
| 47-50 | 4 | 信息栏 QLabel |
| 52-76 | 25 | 站点选择区域：QGroupBox + QGridLayout + 单选按钮 |
| 78-93 | 16 | 本地数据库选项（条件显示） |
| 96-99 | 4 | 进度条 QProgressBar |
| 101-108 | 8 | 按钮行：开始查询 + 取消 |
| 110-116 | 7 | 信号连接 + 定时器启动 |

**依赖项：** QDialog, QLabel, QGroupBox, QRadioButton, QProgressBar, QPushButton, QTimer; `_()`, `QueryWorker`

**拆分方案：**

| 子方法 | 行数 | 职责 |
|--------|------|------|
| `_init_fields()` | 8 | 基类构造 + 成员变量初始化 |
| `_build_info_label()` | 4 | 信息栏 QLabel |
| `_build_site_selection_group()` | 42 | 站点单选按钮组 + 本地数据库选项 |
| `_build_progress_and_buttons()` | 12 | 进度条 + 按钮行 |
| `_connect_signals_and_timer()` | 7 | 信号连接 + 定时器启动 |

**风险点：** `_radio_group` 和 `_cooldown_labels` 字典在 `_build_site_selection_group` 中被填充，提取后需确保在 `_refresh_cooldown`（由定时器触发）访问前已完成初始化。

---

### 2. `query_with_strategy` — `query/adapters/base.py:51` (123 行)

**阶段分段：**

| 行号 | 行数 | 职责 |
|------|------|------|
| 62-63 | 2 | 构造目标标准号字符串 |
| 65-79 | 15 | Step 1: 横杠格式完整号搜索 |
| 81-97 | 17 | Step 2: 空格格式回退 |
| 99-115 | 17 | Step 3: 去除 num_prefix 回退 |
| 117-132 | 16 | Step 4: 去年份回退 |
| 134-167 | 34 | Step 5: 代号变体遍历搜索 |
| 169-173 | 5 | 兜底 |

**核心发现：Step 1-4 模式完全重复**（构造字符串→`_search`→`match_result`→判断→`_post_process_result`→return），累计 65 行可消除。

**拆分方案：**

| 子方法 | 行数 | 职责 |
|--------|------|------|
| `_try_exact_search(search_term, accepted_statuses={"exact"})` | 10 | 通用搜索+匹配，Step 1-4 全部调用此函数 |
| `_search_code_variants(...)` | 34 | Step 5：构建变体+多候选评分搜索 |

**风险点：** 无。纯函数逻辑，不依赖 self 副作用。Step 4 接受 `exact/newer/older`，通过 `accepted_statuses` 参数覆盖。

---

### 3. `update_container` — `docker/api/system.py:65` (93 行)

**阶段分段：**

| 行号 | 行数 | 职责 |
|------|------|------|
| 76-78 | 3 | 获取容器 ID |
| 81-90 | 10 | Step 1: docker inspect 获取当前镜像 digest |
| 92-94 | 3 | Step 2: docker pull 拉取最新镜像 |
| 96-106 | 11 | Step 3: 比对新旧 digest |
| 108-135 | 28 | Step 4: docker compose up -d |
| 137-149 | 13 | 构造返回体 |
| 151-157 | 7 | 异常处理 |

**依赖项：** 独立 async 函数，无 self；`_get_container_id()`, `_run_docker()`, `IMAGE_LATEST`

**拆分方案：**

| 子函数 | 行数 | 职责 |
|--------|------|------|
| `_get_current_digest(cid)` | 10 | inspect→提取旧 digest |
| `_pull_and_compare()` | 14 | pull + 比对 digest，返回是否需更新 |
| `_restart_via_compose()` | 28 | docker compose up -d |
| `_build_update_response(...)` | 13 | 构造成功返回体 |

**风险点：** `_run_docker` 调用集中在同一个 try 块中，需统一异常类型和错误码（504/503/500）。

---

### 4. `_build_message` — `core/notification/manager.py:96` (169 行)

**阶段分段：**

| 行号 | 行数 | 职责 |
|------|------|------|
| 98-106 | 9 | `archive_complete` 分支 |
| 107-116 | 10 | `standard_status_changed` 分支 |
| 117-124 | 8 | `standard_expired` 分支 |
| 125-132 | 8 | `standard_first_registered` 分支 |
| 133-141 | 9 | `check_batch_complete` 分支 |
| 142-149 | 8 | `announcement_fetch_complete` 分支 |
| 150-167 | 18 | `auto_backup` 分支 |
| 168-184 | 17 | `announcement_check_complete` 分支 |
| 185-202 | 18 | `batch_download_complete` 分支 |
| 203-211 | 9 | `auto_scan_failed` 分支 |
| 212-223 | 12 | `validity_batch_report` 分支 |
| 224-240 | 17 | `validity_round_summary` 分支 |
| 241-249 | 9 | `validity_standard_failed` 分支 |
| 250-257 | 8 | `validity_system_failed` 分支 |
| 258-264 | 7 | else 回退分支 |

**拆分方案：** 整个函数是纯 if-elif-else 链，每个分支职责正交。最直接用 **字典分发表** 替代：

```python
_EVENT_BUILDERS: dict[str, Callable] = {
    "archive_complete": _build_archive_complete,
    "standard_status_changed": _build_status_changed,
    ...
}

def _build_message(self, event_type, data):
    builder = self._EVENT_BUILDERS.get(event_type)
    if builder:
        return builder(data)
    return _build_fallback(data)
```

| 子函数 | 行数 | 职责 |
|--------|------|------|
| 15 个 `_build_<事件名>(data)` | 各 6-18 | 每个事件类型一个函数 |
| `_build_message()` 残部 | 8 | 查表+调用 |

**风险点：** 字典分发表需在类初始化时构建或定义为类属性。`auto_backup` 等有子分支（success/failure）的，提取时保留内部条件。

---

### 5. `match_result` — `query/search_strategy.py:76` (85 行)

**阶段分段：**

| 行号 | 行数 | 职责 |
|------|------|------|
| 96-97 | 2 | 空值守卫 |
| 98-99 | 2 | 清理本地代号 |
| 101-136 | 36 | 精确解析路径 |
| 138-158 | 21 | 模糊回退路径 |
| 160 | 1 | fallback mismatch |

**依赖项：** 纯函数，无 self；`_parse_result_number()`, `_is_code_variant()`, `re`

**拆分方案：**

| 子函数 | 行数 | 职责 |
|--------|------|------|
| `_exact_parse_match(...)` | 36 | 精确解析：结构化标准编号对比 |
| `_fuzzy_text_match(...)` | 21 | 模糊回退：正则匹配 |
| `match_result()` 残部 | 10 | 空守卫 + 调用两条路径 |

**风险点：** 两条路径共享 `local_code_clean` 变量，提取时作为参数传递。

---

## 中难度（5 个，需注意副作用）

### 6. `_on_download` — `ui/controllers/download_mixin.py:20` (133 行)

**阶段分段：**

| 行号 | 行数 | 职责 |
|------|------|------|
| 22-23 | 2 | Guard: `_mgr_ready` |
| 24-33 | 10 | 获取 download_list + prereq 对话框 |
| 35-38 | 4 | 切换到下载队列视图 |
| 44-56 | 13 | 筛选"发布不满 20 个工作日"的标准 |
| 58-66 | 8 | 发射 UI 状态信号 + 清空填入表格 |
| 68-70 | 3 | 创建 DownloadWorker + 连接进度信号 |
| 72-141 | 70 | **嵌套闭包 `on_dl_finished`**：恢复按钮→统计→通知→汇总弹窗 |
| 143-148 | 6 | **嵌套闭包 `on_dl_error`**：恢复按钮+发射错误 |
| 150-152 | 3 | 连接 finished/error 信号 + 启动 Worker |

**拆分方案：**

| 子方法 | 行数 | 职责 |
|--------|------|------|
| `_prepare_download()` | 12 | guard + download_list 获取 + prereq 对话框 |
| `_filter_too_new_standards()` | 13 | 筛选太新的标准并弹信息框 |
| `_reset_ui_for_download()` | 8 | 禁用按钮/发射状态/清空表格 |
| `_on_download_finished(to_download, too_new_set, total)` | 70 | 闭包提取为实例方法 |
| `_on_download_error()` | 6 | 闭包提取为实例方法 |

**核心风险：** 两个内部闭包捕获了大量外层局部变量（`to_download`, `too_new_set`, `total`, `download_list`），提取为实例方法时需转为显式传参或 self 属性。

---

### 7. `organize_skipped_dirs` — `manager/organize/mirror.py:23` (82 行)

**阶段分段：**

| 行号 | 行数 | 职责 |
|------|------|------|
| 25-34 | 10 | 获取 root + 初始化 result 字典 |
| 35-53 | 19 | 遍历 skipped_dirs：路径清理 + relpath 计算 + 行业路径解析 + 越界校验 |
| 54-102 | 49 | 主分支：目标存在 vs 不存在的文件/目录移动 |

**拆分方案：**

| 子方法 | 行数 | 职责 |
|--------|------|------|
| `_resolve_skipped_relative(dirpath, root)` | 11 | 路径清理 + relpath + 行业路径替换 |
| `_check_path_traversal(dst, root, dirpath)` | 5 | 校验目标路径不越界 |
| `_mirror_into_existing_dst(dst, dirpath, result)` | 31 | 目标已存在→逐文件移动 |
| `_mirror_whole_directory(dst, dirpath, result)` | 13 | 目标不存在→整体移动 |

**核心风险：** `_mirror_into_existing_dst` 两级嵌套遍历较深；`_clear_readonly_tree` 重复出现 2 次可提取；`result["moved"]`/`result["details"]` 多处更新位置需一致。

---

### 8. `classify` — `manager/classifier.py:56` (86 行)

**阶段分段：**

| 行号 | 行数 | 职责 |
|------|------|------|
| 82-94 | 13 | 回写阶段：QueryResult 字段写入 ParsedStdInfo |
| 96-114 | 19 | 跨站补查：废止+无替代+GB 调用 resolve_replaces |
| 116-123 | 8 | 路由分堆：`_router.apply_actions()` 分发到三个列表 |
| 125-136 | 12 | stage_status 回写 |
| 138-141 | 4 | 过期同步：下载桶废止项追加到过期列表 |

**拆分方案：**

| 子方法 | 行数 | 职责 |
|--------|------|------|
| `_write_back_results(items, results)` | 13 | 将 QueryResult 字段平铺到 ParsedStdInfo |
| `_resolve_cross_site_replaces(items, results)` | 19 | 跨站补查替代关系 |
| `_dispatch_by_router(items, download_list, expire_list, pending_list)` | 12 | 路由分堆+stage_status 回写 |
| `_sync_expired_downloads(download_list, expire_list)` | 4 | 过期同步 |

**核心风险：** Step 2 修改了 `r.replaces`（QueryResult 对象的隐式副作用），会影响 Step 3 路由行为。提取后需显式标注副作用。

---

### 9. `_csres_worker` — `query/engine/_batch.py:167` (81 行，嵌套闭包)

**阶段分段：**

| 行号 | 行数 | 职责 |
|------|------|------|
| 171-173 | 3 | 无 csres 适配器则提前返回 |
| 177-183 | 7 | 计算池子（GB 60% + 行业 40%）+ 设置活跃标志 |
| 184-245 | 62 | 主循环：熔断检查→执行查询→结果处理→限速休眠 |

**拆分方案：**

| 子方法 | 行数 | 职责 |
|--------|------|------|
| `_build_csres_pool(gb_items, industry_items)` | 7 | 计算 GB/行业各取多少条 |
| `_csres_single_query(adapter, idx, item)` | 20 | 单次查询+rotator记录+结果处理+熔断 |
| `_rate_limit_sleep(t0, last_ts)` | 12 | 计算并执行限速休眠 |
| `_csres_worker(...)` 残部 | 25 | 编排上述子函数 |

**提取为实例方法的关键：** 闭包捕获的 `csres_results` 和 `csres_failures` 需转为显式参数：

```python
def _run_csres_worker(
    self, gb_items, industry_items,
    csres_results: dict, csres_failures: list[int],
) -> None:
```

**核心风险：** 熔断计数器以 list 包裹绕开 nonlocal，提取后可选改为普通 int 并返回新值；`_last_ts` 是循环内状态变量，跨循环时序依赖；当前日志行有已有 bug（`item[0]` 输出两次），建议顺便修正。

---

### 10. `organize` — `manager/organize/organizer.py:40` (130 行)

**阶段分段：**

| 行号 | 行数 | 职责 |
|------|------|------|
| 40-58 | 19 | 签名+别名+result 字典初始化 |
| 62-69 | 8 | **第一次循环**：仅打进度日志（每 50 条或最后一笔） |
| 71-159 | 89 | **第二次循环**：主处理逻辑 |
| 74-120 | 47 | Word 文件→镜像归档 |
| 121-157 | 37 | 非 Word 文件→去重+移动+索引 |
| 160-168 | 9 | 最终汇总日志 |

**拆分方案：**

| 子方法 | 行数 | 职责 |
|--------|------|------|
| `_organize_word_item(p, root, word_source_root, result)` | 47 | Word 文件镜像归档+索引 |
| `_organize_nonword_item(p, mover, root, result, content_hashes)` | 37 | 非 Word 文件去重+移动+索引 |
| `_log_organize_summary(result)` | 9 | 汇总日志 |

**关键建议：** 当前两次 O(n) 全量遍历可合并为一次——第一次循环只打日志不做数据修改，可在第二次循环开头加 `if _org_count % 50 == 0` 判断替代。

**核心风险：** `_content_hashes` 字典在循环中累积，Word/非 Word 分支需正确跳过；`_org_t0` 首条时间戳需重置为循环开始前；`_skipped_source_files` 是类 set 属性，两分支均有追加。

---

## 执行优先级建议

| 优先级 | 函数 | 理由 |
|--------|------|------|
| P0 | `_build_message` | 169 行最大，字典分发风险最低，收益最大 |
| P1 | `query_with_strategy` | 65 行重复代码消除后可达 <40 行 |
| P1 | `match_result` | 纯函数无副作用，2 条路径提取即可 |
| P2 | `update_container` | 5 步异步流水线直接切 |
| P2 | `__init__` | 纯 UI 构建，5 段直接提取 |
| P3 | `classify` | 4 步线性流水线，副作用可控 |
| P3 | `organize_skipped_dirs` | 44 行分支提取后编排器 <20 行 |
| P4 | `_on_download` | 133 行最大 UI 函数，闭包提取需重传参数 |
| P4 | `organize` | 双循环合并+Word/非 Word 分支正交 |
| P5 | `_csres_worker` | 嵌套闭包，需修改调用方 query_batch_parsed 传参 |
