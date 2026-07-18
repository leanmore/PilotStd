# CHANGELOG
## v0.77.1 (2026-07-18)

### Fixed
- 版本号自动同步（CI 更新）

## v0.77.0 (2026-07-18)

### Fixed
- 版本号自动同步（CI 更新）

## v0.76.0 (2026-07-18)

### Fixed
- 版本号自动同步（CI 更新）

## v0.75.2 (2026-07-18)

### Fixed
- 版本号自动同步（CI 更新）

## v0.75.1 (2026-07-18)

### Fixed
- 版本号自动同步（CI 更新）

## v0.75.0 (2026-07-18)

### Fixed
- 版本号自动同步（CI 更新）

## v0.74.1 (2026-07-18)

### Fixed
- 版本号自动同步（CI 更新）

## v0.74.0 (2026-07-17)

### Fixed
- 版本号自动同步（CI 更新）

## v0.73.0 (2026-07-17)

### Fixed
- 版本号自动同步（CI 更新）

## v0.72.2 (2026-07-17)

### Fixed
- 版本号自动同步（CI 更新）

## v0.72.1 (2026-07-17)

### Fixed
- 版本号自动同步（CI 更新）

## v0.72.0 (2026-07-17)

### Fixed
- 版本号自动同步（CI 更新）

## v0.71.1 (2026-07-17)

### Fixed
- 版本号自动同步（CI 更新）

## v0.71.0 (2026-07-16)

### Fixed
- 版本号自动同步（CI 更新）

## v0.70.0 (2026-07-16)

### Fixed
- 版本号自动同步（CI 更新）

## v0.69.0 (2026-07-16)

### Fixed
- 版本号自动同步（CI 更新）

## v0.68.2 (2026-07-14)

### Fixed
- 版本号自动同步（CI 更新）

## v0.68.1 (2026-07-14)

### Fixed
- 版本号自动同步（CI 更新）

## v0.68.0 (2026-07-14)

### Fixed
- 版本号自动同步（CI 更新）

## v0.67.0 (2026-07-14)

### Fixed
- 版本号自动同步（CI 更新）

## v0.67.0 (2026-07-13)

### Changed — 破坏性变更 (Breaking Changes)
- **密码哈希升级为 bcrypt**：`docker/users.py` 的 `verify_user`/`add_user`/`change_password`/`_ensure_superuser` 改用 bcrypt 存储密码；旧 PBKDF2 密码在用户登录时自动惰性升级
- **用户偏好 API 重构**：`GET /api/user-preference?key=xxx` 和 `POST /api/user-preference?key=xxx&value=yyy` 已删除。替代端点：
  - `GET /api/user-preference` — 读取全部偏好（JSON 聚合格式）
  - `PATCH /api/user-preference` — 增量更新偏好（body: `{"updates": {...}}`）
  - `DELETE /api/user-preference` — 重置为默认值
  - **所有新端点需要登录认证**（Cookie/Token），旧端点无认证

### Added
- `pilotstd/core/security.py` — 密码安全模块（bcrypt + PBKDF2/SHA256 三格式兼容）
- `pilotstd/manager/settings_manager.py` — 用户偏好管理器（JSON 聚合存储 + 内存缓存）
- `pilotstd/core/config/priority.py` — 配置优先级管理器（ENV > FILE > FACTORY）
- 数据库迁移 v38 — 新增 `user_settings` 表（JSON 聚合存储），与现有 `user_preferences`（KV）并存
- 新增依赖：`passlib[bcrypt]>=1.7,<2`（bcrypt 需 <5.0 以兼容 passlib）

### Fixed
- 前端 `stores/preferences.ts` 适配新 JSON 聚合 API
- 前端 `AnnounceView.vue` 旧 API 调用迁移至 preferences store
- JWT SECRET 恢复为自动生成（移除硬编码默认值）
- 测试补充：`TestPasswordSecurity`（9 个用例）+ 迁移测试更新预期表清单

## v0.66.0 (2026-07-12)

### Fixed
- 版本号自动同步（CI 更新）

## v0.65.3 (2026-07-12)

### Fixed
- 版本号自动同步（CI 更新）

## v0.65.2 (2026-07-12)

### Fixed
- 版本号自动同步（CI 更新）

## v0.65.1 (2026-07-12)

### Fixed
- Handler 构造参数错配修复：ScanUIHandler 删除 3 个不存在参数 + 补 2 个缺失；QueryUIHandler 补充 `__init__` 委托给 `__init_tr` + 调用方补 3 删 1；DownloadUIHandler 补 `progress_callback`/`question_dlg`
- 全量审查 14 个 Handler 实例化，其余 10 个签名与调用一致
- 版本号自动同步（CI 更新）

## v0.65.0 (2026-07-12)

### Fixed
- 版本号自动同步（CI 更新）

## v0.64.9 (2026-07-12)

### Fixed
- 版本号自动同步（CI 更新）

## v0.64.8 (2026-07-10)

### Fixed
- 版本号自动同步（CI 更新）

## v0.64.8 (2026-07-10)

### Fixed
- 版本号自动同步（CI 更新）

## v0.64.7 (2026-07-10)

### Fixed
- 版本号自动同步（CI 更新）

## v0.64.6 (2026-07-10)

### Fixed
- 版本号自动同步（CI 更新）

## v0.64.5 (2026-07-10)

### Fixed
- 版本号自动同步（CI 更新）

## v0.64.4 (2026-07-10)

### Fixed
- 版本号自动同步（CI 更新）

## v0.64.3 (2026-07-10)

### Fixed
- 版本号自动同步（CI 更新）

## v0.64.2 (2026-07-10)

### Fixed
- 版本号自动同步（CI 更新）

## v0.64.1 (2026-07-10)

### Fixed
- 版本号自动同步（CI 更新）

## v0.64.0 (2026-07-09)

### Fixed
- 版本号自动同步（CI 更新）

## v0.63.0 (2026-07-09)

### Changed
- 待确认列表导出统一：汇总弹窗"保存待确认CSV"改为从 pending_lookup 表直接读取，不再依赖界面过滤
- 删除 3 个死方法：_build_pending_table、_save_pending_csv、_show_pending_dialog（均无调用方）
- PyInstaller 打包改为 --noconsole (console=False)，双击 exe 不再弹出命令行窗口

### Fixed
- 版本号自动同步（CI 更新）

## v0.62.1 (2026-07-09)

### Changed
- 公告检查完成通知数据源重写：从 matched 计数改为 announcement_record 表分类统计（国标/行标/地标的公告数和标准数）
- 聚合器改为固定窗口 + 首次延时（60s 触发 / 300s 最大窗口），分组 key 简化
- 标准废止事件合并到 standard_status_changed（is_expired 标记），消息模板增加废止专用标题
- validity_batch_report 零数据时显示"开始有效性检查"而非"共 0 条标准"
- validity_round_summary 新增 round 字段（自动递增计数器）
- 行号生成改为 rowCount()+1，消除追加模式下行号冲突
- _organize_word_item 新增标准号解析：有标准号分类归档，无标准号保持镜像
- ParsedStdInfo 新增 is_valid_standard 属性，CSV 导出时过滤无效数据
- 通知消息增加 changed_at 时间字段

### Fixed
- DatePicker 月份面板英文：primevueLocale 补全字段 + AppCalendar onMounted 写入全局 locale
- useToast 残留导致 QuickActionsCard/SystemLogCard/SettingsTabUsers 卡片黑屏
- 静音时段不生效：user preferences API 同步写入 config.json
- 静音时段补发未执行：_release_suppressed_notifications 注册为调度任务
- announcement_check_complete 通知始终显示"共 0 条"：键名 count/new_count 不匹配
- Win 弹窗右下角像素方块残留：setSizeGripEnabled(False) + QMenu/QMessageBox parent 修正
- WinUI crash_log 写入和 CMD 窗口 Safestream 已禁用

## v0.57.0 (2026-07-07)

### Fixed
- 版本号自动同步（CI 更新）

## v0.56.14 (2026-07-07)

### Fixed
- 版本号自动同步（CI 更新）

## v0.56.13 (2026-07-06)

### Fixed
- 版本号自动同步（CI 更新）

## v0.56.12 (2026-07-06)

### Fixed
- 版本号自动同步（CI 更新）

## v0.56.11 (2026-07-06)

### Fixed
- 版本号自动同步（CI 更新）

## v0.56.10 (2026-07-06)

### Fixed
- 版本号自动同步（CI 更新）

## v0.56.9 (2026-07-06)

### Fixed
- 版本号自动同步（CI 更新）

## v0.56.8 (2026-07-06)

### Fixed
- 版本号自动同步（CI 更新）

## v0.56.7 (2026-07-06)

### Fixed
- 版本号自动同步（CI 更新）

## v0.56.6 (2026-07-06)

### Fixed
- 版本号自动同步（CI 更新）

## v0.56.5 (2026-07-06)

### Fixed
- 版本号自动同步（CI 更新）

## v0.56.4 (2026-07-06)

### Fixed
- 版本号自动同步（CI 更新）

## v0.56.3 (2026-07-06)

### Fixed
- 版本号自动同步（CI 更新）

## v0.56.2 (2026-07-06)

### Fixed
- 版本号自动同步（CI 更新）

## v0.56.1 (2026-07-06)

### Fixed
- 版本号自动同步（CI 更新）

## v0.56.0 (2026-07-06)

### Fixed
- 版本号自动同步（CI 更新）

## v0.55.39 (2026-07-05)

### Fixed
- 版本号自动同步（CI 更新）

## v0.55.38 (2026-07-05)

### Fixed
- 版本号自动同步（CI 更新）

## v0.55.37 (2026-07-05)

### Fixed
- 版本号自动同步（CI 更新）

## v0.55.36 (2026-07-05)

### Fixed
- 版本号自动同步（CI 更新）

## v0.55.35 (2026-07-05)

### Fixed
- 版本号自动同步（CI 更新）


## v0.55.34 (2026-07-04)

### Fixed
- WinUI：公告互斥逻辑从 `setEnabled` 改为 `setChecked` 自动互切，修复双 True 脏数据导致双复选框锁死
- Web：Select/Dropdown 选中态样式修复（PrimeVue 4 使用 `data-p-selected` 属性而非 `.p-highlight` 类名）

### Changed
- Web：首页控制栏改为右侧固定侧边栏，解锁布局按钮移至重置按钮上方
- Web：查询适配器卡片尺寸加大（6×8→8×10），新增中文名称显示

## v0.55.33 (2026-07-03)

### Fixed
- 版本号自动同步（CI 更新）


## v0.55.32 (2026-07-03)

### Fixed
- 版本号自动同步（CI 更新）


## v0.55.31 (2026-07-03)

### Fixed
- 版本号自动同步（CI 更新）


## v0.55.30 (2026-07-03)

### Fixed
- 版本号自动同步（CI 更新）


## v0.55.29 (2026-07-03)

### Fixed
- 版本号自动同步（CI 更新）


## v0.55.28 (2026-07-03)

### Fixed
- 版本号自动同步（CI 更新）


## v0.55.27 (2026-07-03)

### Fixed
- 版本号自动同步（CI 更新）


## v0.55.26 (2026-07-03)

### Fixed
- 版本号自动同步（CI 更新）


## v0.55.25 (2026-07-03)

### Fixed
- 版本号自动同步（CI 更新）


## v0.55.24 (2026-07-03)

### Fixed
- 版本号自动同步（CI 更新）


## v0.55.23 (2026-07-03)

### Fixed
- 版本号自动同步（CI 更新）


## v0.55.21 (2026-07-02)

### Fixed
- 版本号自动同步（CI 更新）


## v0.55.20 (2026-07-02)

### Fixed
- 版本号自动同步（CI 更新）


## v0.55.19 (2026-07-02)

### Fixed
- 版本号自动同步（CI 更新）


## v0.55.18 (2026-07-02)

### Fixed
- 版本号自动同步（CI 更新）


## v0.55.17 (2026-07-02)

### Fixed
- 版本号自动同步（CI 更新）


## v0.55.16 (2026-07-02)

### Fixed
- 版本号自动同步（CI 更新）


## v0.55.15 (2026-07-02)

### Fixed
- 版本号自动同步（CI 更新）


## v0.55.14 (2026-07-02)

### Fixed
- 版本号自动同步（CI 更新）


## v0.55.13 (2026-07-02)

### Fixed
- 版本号自动同步（CI 更新）


## v0.55.12 (2026-07-02)

### Fixed
- 版本号自动同步（CI 更新）


## v0.55.11 (2026-07-01)

### Fixed
- 版本号自动同步（CI 更新）


## v0.55.10 (2026-07-01)

### Fixed
- 版本号自动同步（CI 更新）


## v0.55.9 (2026-07-01)

### Fixed
- 版本号自动同步（CI 更新）


## v0.55.8 (2026-07-01)

### Fixed
- 版本号自动同步（CI 更新）


## v0.55.7 (2026-07-01)

### Fixed
- 版本号自动同步（CI 更新）


## v0.55.6 (2026-07-01)

### Fixed
- 版本号自动同步（CI 更新）


## v0.55.5 (2026-07-01)

### Fixed
- 版本号自动同步（CI 更新）


## v0.55.4 (2026-07-01)

### Fixed
- 版本号自动同步（CI 更新）


## v0.55.3 (2026-07-01)

### Fixed
- 版本号自动同步（CI 更新）


## v0.55.2 (2026-07-01)

### Fixed
- 版本号自动同步（CI 更新）


## v0.55.1 (2026-07-01)

### Fixed
- 版本号自动同步（CI 更新）


## v0.55.0 (2026-07-01)

### Fixed
- 版本号自动同步（CI 更新）


## v0.54.9 (2026-07-01)

### Fixed
- 版本号自动同步（CI 更新）


## v0.54.8 (2026-06-30)

### Fixed
- 版本号自动同步（CI 更新）


## v0.54.7 (2026-06-30)

### Fixed
- 版本号自动同步（CI 更新）


## v0.54.6 (2026-06-30)

### Fixed
- 版本号自动同步（CI 更新）


## v0.54.5 (2026-06-30)

### Fixed
- 版本号自动同步（CI 更新）


## v0.54.4 (2026-06-30)

### Fixed
- 版本号自动同步（CI 更新）


## v0.54.3 (2026-06-30)

### Fixed
- 版本号自动同步（CI 更新）


## v0.54.1 (2026-06-30)

### Fixed
- 版本号自动同步（CI 更新）


## v0.54.0 (2026-06-30) — GATE-15 治理清零

### Added
- 服务端会话存储 (`docker/session_store.py`) — JWT token 主动登出失效 + 定期清理
- JWT_SECRET 固定默认值 (环境变量优先，不再随机生成)
- 通知系统 P1 补全 — `GET /api/notification/unread-count` 端点
- 通知 WebSocket 实时推送 (`/api/notification/ws`)
- 引擎模块拆分：`_csres.py`、`_mini_bucket.py`、`_report.py` 三个新 mixin
- 通知消息构建器提取：`core/notification/_message_builders.py`

### Changed
- **GATE-15 违规清零** — 11 个大文件包化为目录，32 个大函数拆分
- `query/engine/_batch.py`: 782→424 行 (提取 CsresMixin + MiniBucketMixin + ReportMixin)
- `core/notification/manager.py`: 543→288 行 (提取 MessageBuildersMixin)
- `core/validity_checker.py`: `run_validity_check` 170→28 行 (提取 3 个辅助函数)
- `pipeline/router.py`: `classify_after_query` 150→23 行 (提取 `_route_by_status`)

### Fixed
- P0: `_routing.py` 3 处相对导入路径错误 (`..core` → `...core`)
- P0: `_batch.py` 1 处相对导入路径错误
- P0: `cli/commands/__init__.py` CLI 类丢失 (新增适配类)
- 数据库迁移 v7 守卫 (CREATE INDEX 增加 try/except)
- 测试 `test_migration_runs_pending` patch 路径修正
- 测试 `test_v18_migration_adds_is_read_column` 导入路径修正
- E2E `test_gb_exact_match` 标记 skip (外部 API 依赖)

### Tests
- 615 PASS / 6 SKIP / 0 FAIL (100% 通过率)


## v0.52.6 (2026-06-29)


### Fixed
- 版本号自动同步（CI 更新）


## v0.52.5 (2026-06-29)

### Fixed
- 版本号自动同步（CI 更新）


## v0.52.4 (2026-06-29)

### Fixed
- 版本号自动同步（CI 更新）


## v0.52.3 (2026-06-29)

### Fixed
- 版本号自动同步（CI 更新）


## v0.52.2 (2026-06-29)

### Fixed
- 版本号自动同步（CI 更新）


## v0.52.1 (2026-06-29)

### Fixed
- 版本号自动同步（CI 更新）


## v0.52.0 (2026-06-29)

### Fixed
- 版本号自动同步（CI 更新）


## v0.51.0 (2026-06-29)

### Fixed
- 版本号自动同步（CI 更新）


## v0.50.0 (2026-06-29)

### Fixed
- 版本号自动同步（CI 更新）


## v0.49.0 (2026-06-29)

### Fixed
- 版本号自动同步（CI 更新）


## v0.48.0 (2026-06-29)

### Fixed
- 版本号自动同步（CI 更新）


## v0.47.0 (2026-06-29)

### Fixed
- 版本号自动同步（CI 更新）


## v0.46.0 (2026-06-29)

### Fixed
- 版本号自动同步（CI 更新）


## v0.45.0 (2026-06-29)

### Fixed
- 版本号自动同步（CI 更新）


## v0.44.0 (2026-06-29)

### Fixed
- 版本号自动同步（CI 更新）


## v0.43.0 (2026-06-28)

### Fixed
- 版本号自动同步（CI 更新）


## v0.42.0 (2026-06-28)

### Fixed
- 版本号自动同步（CI 更新）


## v0.41.0 (2026-06-28)

### Fixed
- 版本号自动同步（CI 更新）


## v0.40.0 (2026-06-28)

### Fixed
- 版本号自动同步（CI 更新）


## v0.39.0 (2026-06-28)

### Fixed
- 版本号自动同步（CI 更新）


## v0.38.0 (2026-06-28)

### Fixed
- 版本号自动同步（CI 更新）


## v0.37.35 (2026-06-28)

### Fixed
- 版本号自动同步（CI 更新）


## v0.37.34 (2026-06-28)

### Fixed
- 版本号自动同步（CI 更新）


## v0.37.33 (2026-06-28)

### Fixed
- 版本号自动同步（CI 更新）


## v0.37.32 (2026-06-28)

### Fixed
- 版本号自动同步（CI 更新）


## v0.37.31 (2026-06-28)

### Fixed
- 版本号自动同步（CI 更新）


## v0.37.30 (2026-06-28)

### Fixed
- 版本号自动同步（CI 更新）


## v0.37.29 (2026-06-28)

### Fixed
- 版本号自动同步（CI 更新）


## v0.37.28 (2026-06-28)

### Fixed
- 版本号自动同步（CI 更新）


## v0.37.27 (2026-06-28)

### Fixed
- 版本号自动同步（CI 更新）


## v0.37.26 (2026-06-28)

### Fixed
- 版本号自动同步（CI 更新）


## v0.37.25 (2026-06-28)

### Fixed
- 版本号自动同步（CI 更新）


## v0.37.24 (2026-06-28)

### Fixed
- 版本号自动同步（CI 更新）


## v0.37.23 (2026-06-28)

### Added
- feat: 新增GATE-13门禁—禁止前端代码硬编码admin作为超级用户标识

### Fixed
- fix: SUPERUSER_USERNAME从硬编码admin改为VITE_SUPERUSER_NAME环境变量，默认回退SUPERUSER

### Changed
- refactor: main.ts全局注册24个PrimeVue组件，消除各文件重复import

## v0.37.22 (2026-06-28)

### Fixed
- fix: Vue组件添加defineOptions防止生产构建中组件名被压缩器删除+GATE-12门禁

## v0.37.19 (2026-06-27)

### Changed
- chore: bump version to v0.37.19

## v0.37.20 (2026-06-27)

### Changed
- chore: bump version to v0.37.20

## v0.37.21 (2026-06-27)

### Changed
- chore: bump version to v0.37.21

## v0.4.1 (2026-06-10)

### Changed
- chore: bump version to v0.4.1

## v0.4.2 (2026-06-10)

### Changed
- chore: bump version to v0.4.2

## v0.4.3 (2026-06-10)

### Changed
- chore: bump version to v0.4.3

## v0.4.4 (2026-06-11)

### Changed
- chore: bump version to v0.4.4

## v0.4.5 (2026-06-12)

### Changed
- chore: bump version to v0.4.5

## v0.4.6 (2026-06-12)

### Changed
- chore: bump version to v0.4.6

## v0.4.7 (2026-06-13)

### Changed
- chore: bump version to v0.4.7

## v0.5.0 (2026-06-14)

### Changed
- chore: bump version to v0.5.0

## v0.5.1 (2026-06-14)

### Changed
- chore: bump version to v0.5.1

## v0.5.2 (2026-06-14)

### Changed
- chore: bump version to v0.5.2

## v0.5.3 (2026-06-14)

### Changed
- chore: bump version to v0.5.3

## v0.5.4 (2026-06-14)

### Changed
- chore: bump version to v0.5.4

## v0.5.5 (2026-06-14)

### Changed
- chore: bump version to v0.5.5

## v0.5.6 (2026-06-14)

### Changed
- chore: bump version to v0.5.6

## v0.5.7 (2026-06-14)

### Changed
- chore: bump version to v0.5.7

## v0.5.8 (2026-06-14)

### Changed
- chore: bump version to v0.5.8

## v0.5.9 (2026-06-14)

### Changed
- chore: bump version to v0.5.9

## v0.5.10 (2026-06-14)

### Changed
- chore: bump version to v0.5.10

## v0.5.11 (2026-06-14)

### Changed
- chore: bump version to v0.5.11

## v0.5.12 (2026-06-15)

### Changed
- chore: bump version to v0.5.12

## v0.5.13 (2026-06-15)

### Changed
- chore: bump version to v0.5.13

## v0.5.14 (2026-06-15)

### Changed
- chore: bump version to v0.5.14

## v0.5.15 (2026-06-15)

### Changed
- chore: bump version to v0.5.15

## v0.5.16 (2026-06-15)

### Changed
- chore: bump version to v0.5.16

## v0.5.17 (2026-06-15)

### Changed
- chore: bump version to v0.5.17

## v0.5.18 (2026-06-15)

### Changed
- chore: bump version to v0.5.18

## v0.5.19 (2026-06-15)

### Changed
- chore: bump version to v0.5.19

## v0.5.20 (2026-06-15)

### Changed
- chore: bump version to v0.5.20

## v0.5.21 (2026-06-16)

### Changed
- chore: bump version to v0.5.21

## v0.5.22 (2026-06-16)

### Changed
- chore: bump version to v0.5.22

## v0.5.23 (2026-06-16)

### Changed
- chore: bump version to v0.5.23

## v0.5.24 (2026-06-16)

### Changed
- chore: bump version to v0.5.24

## v0.5.25 (2026-06-17)

### Changed
- chore: bump version to v0.5.25

## v0.5.26 (2026-06-17)

### Changed
- chore: bump version to v0.5.26

## v0.5.27 (2026-06-17)

### Changed
- chore: bump version to v0.5.27

## v0.6.0 (2026-06-17)

### Changed
- chore: bump version to v0.6.0

## v0.7.0 (2026-06-17)

### Changed
- chore: bump version to v0.7.0

## v0.8.0 (2026-06-18)

### Changed
- chore: bump version to v0.8.0

## v0.8.1 (2026-06-18)

### Changed
- chore: bump version to v0.8.1

## v0.8.2 (2026-06-18)

### Changed
- chore: bump version to v0.8.2

## v0.8.3 (2026-06-19)

### Changed
- chore: bump version to v0.8.3

## v0.9.0 (2026-06-19)

### Changed
- chore: bump version to v0.9.0

## v0.37.2 (2026-06-27)

### Changed
- chore: bump version to v0.37.2

## v0.37.3 (2026-06-27)

### Changed
- chore: bump version to v0.37.3

## v0.37.4 (2026-06-27)

### Changed
- chore: bump version to v0.37.4

## v0.37.5 (2026-06-27)

### Changed
- chore: bump version to v0.37.5

## v0.37.6 (2026-06-27)

### Changed
- chore: bump version to v0.37.6

## v0.37.7 (2026-06-27)

### Changed
- chore: bump version to v0.37.7

## v0.37.8 (2026-06-27)

### Changed
- chore: bump version to v0.37.8

## v0.37.9 (2026-06-27)

### Changed
- chore: bump version to v0.37.9

## v0.37.18 (2026-06-27)

### Changed
- chore: bump version to v0.37.18

## v0.37.16 (2026-06-27)

### Changed
- chore: bump version to v0.37.16

## v0.37.17 (2026-06-27)

### Changed
- chore: bump version to v0.37.17

## v0.37.18 (2026-06-27)

### Changed
- chore: bump version to v0.37.18

## v0.37.1

### Added
- GATE-11: 禁止硬编码 admin 作为超级管理员标识，权限判断统一使用 ADMIN_ROLE 常量
- 新增 ADMIN_ROLE 常量定义 (pilotstd/__init__.py)，统一后端权限判断
 (2026-06-27)

### Changed
- chore: bump version to v0.37.14

## v0.37.15 (2026-06-27)

### Fixed
- 补 v25 迁移脚本，创建 announcement_match 表（v5 迁移可能因版本跳号被跳过，兜底修复）


### Changed
- chore: bump version to v0.37.15

## v0.37.14 (2026-06-27)

### Fixed
- @ feat: 首页三问题修复—适配器并排+StatsCard多值+待确认/系统信息卡片 @
## v0.37.15 (2026-06-27)

### Fixed
- @ fix: GATE-10重命名为check_ui_sensitive_fields.py纳入run-gates自动触发 @
- @ docs: CHANGELOG补全v0.37.11~v0.37.13缺失条目 @
## v0.37.1

### Changed
- 回退 APScheduler 从 4.x 到 3.10.4（4.0.0/4.0.1 在 PyPI 被 yanked，阻塞 Docker 构建）
- 技术债：待 APScheduler 发布 4.0.2+ 稳定版本后重新评估升级

 (2026-06-27)

### Fixed
- @ feat: 首页三问题修复—适配器并排+StatsCard多值+待确认/系统信息卡片 @
## v0.37.11 (2026-06-27)

### Fixed
- @ feat: CHANGELOG历史补全+GATE-09版本一致性+GATE-10敏感字段保护门禁 @
## v0.37.12 (2026-06-27)

### Fixed
- @ fix: GATE-10修复—NotificationConfig中bot_token/secret改用Password组件 @
## v0.37.13 (2026-06-27)

### Fixed
- @ feat: APScheduler升级至4.x并移除setuptools<82约束 @
- @ feat: 系统Tab拆分为独立Card容器-文件监控/缓存管理/任务管理各自独立 @
- @ feat: 通知渠道卡片+可信IP卡片改用Accordion折叠，默认全部折叠 @
## v0.37.11 (2026-06-27)

### Fixed
- @ feat: CHANGELOG历史补全+GATE-09版本一致性+GATE-10敏感字段保护门禁 @
## v0.37.12 (2026-06-27)

### Fixed
- @ fix: GATE-10修复—NotificationConfig中bot_token/secret改用Password组件 @
## v0.37.13 (2026-06-27)

### Fixed
- @ feat: APScheduler升级至4.x并移除setuptools<82约束 @
- @ feat: 系统Tab拆分为独立Card容器-文件监控/缓存管理/任务管理各自独立 @
- @ feat: 通知渠道卡片+可信IP卡片改用Accordion折叠，默认全部折叠 @
## v0.37.11 (2026-06-27)

### Fixed
- @ feat: CHANGELOG历史补全+GATE-09版本一致性+GATE-10敏感字段保护门禁 @
## v0.37.12 (2026-06-27)

### Fixed
- @ fix: GATE-10修复—NotificationConfig中bot_token/secret改用Password组件 @
## v0.37.13 (2026-06-27)

### Fixed
- @ feat: APScheduler升级至4.x并移除setuptools<82约束 @
- @ feat: 系统Tab拆分为独立Card容器-文件监控/缓存管理/任务管理各自独立 @
- @ feat: 通知渠道卡片+可信IP卡片改用Accordion折叠，默认全部折叠 @
## v0.6.0 (2026-06-17)

### Added
- feat: 压测判定接入逐桶指标——pending/cooldown/elapsed自动对比基线
- feat: 临时桶微批——每批20条+批次间2-5s随机抖动防惊群
- feat: 压测报告加逐桶指标——冷却计数+漏斗数据+基线对比行
- feat: 逐桶日志18项全覆盖——CSRES_INTERVAL实际间隔+BASELINE新旧对比基线
- feat: 逐桶日志补全——COOLDOWN冷却归因+RECOVERY恢复延迟
- feat: 逐桶日志全覆盖——BUCKET/QUOTA/SCORE/CHAIN/PENDING/CSRES/OVERFLOW/WATER/FUNNEL/TIMELINE
- feat: 逐桶日志完善——BUCKET含done/overflow，QUOTA站点用量，TIMELINE桶耗时
- feat: 逐桶查询日志输出[BUCKET][FUNNEL][TIMELINE]+压测解析

### Fixed
- fix: Docker镜像tag跟随版本号——IMAGE_VERSIONED返回v0.5.27，IMAGE_LATEST用于自更新
- fix: test_system_api模块级mock污染全局os.path.exists导致合跑失败
- fix: 代码审核14项修复——逐桶查询+公告透传+键名统一+死代码清理+版本号同步+更新测试

### Changed
- docs: 压测方案补全——执行方式+判定方式+用例矩阵8项
- test: 逐桶并发4用例——溢出隔离/csres链移除/链耗尽/大桶拆子桶
- test: 逐桶查询单元测试——分组/链隔离/临时桶8用例

## v0.7.0 (2026-06-17)

### Added
- feat: OCR密钥支持环境变量注入+stress_driver透传OCR_*环境变量

## v0.8.0 (2026-06-18)

### Added
- feat: v0.8.0 — 统一查询链路、合并解析器、冷却策略优化
- feat: 压测配置JSON支持——--config读Docker账密+OCR注入子进程+分析点

### Fixed
- fix: __version__ 同步到 v0.7.0 匹配最新 git tag
- fix: docker login用repository_owner替代actor
- fix: CI docker login改用PAT_TOKEN替代GITHUB_TOKEN

### Changed
- perf: CI test-backend 加 pytest-xdist 多核并行
- chore: Docker镜像名 pilotstd-app 改为 pilotstd
- refactor: 统一查询链路、合并解析器、优化冷却策略
- chore: 触发CI重建Docker镜像
- chore: 孤儿包已删除，触发CI重建ghcr包
- chore: 触发CI构建
- chore: 触发CI重新构建Docker镜像

## v0.8.1 (2026-06-18)

### Fixed
- fix: release流程版本回写移到tag创建之前，tag指向正确commit

### Changed

## v0.8.2 (2026-06-18)

### Added
- feat: 重建质量检查工具—陈旧引用检测+Runner+测试，修复test_manager残留引用

### Fixed
- fix: 代码审查修复—恢复plan_batch+num_prefix传递+去重tearDown+stress归档陈旧引用
- fix: TestBucketConcurrency回退setUpClass，并发测试需per-method隔离
- fix: 修复e2e+stress归档文件中已删除API的陈旧引用
- fix: test_query重写—BuildSearchTerms→ProgressiveSearch+NetworkError+引擎API+DB优化
- fix: test_regressions query_single→query_with_strategy匹配新API
- fix: test_adapters三处修复—target_number修正+query_with_strategy+hbba mock request方法

### Changed
- refactor: scheduled_service改用query_parsed/query_batch_parsed替代已删除的薄壳
- refactor: 删除engine死代码—query_single/query_batch薄壳+v1+_run_site_batch+_plan_batch

## v0.8.3 (2026-06-19)

### Fixed
- fix: 全链路类型安全+逻辑下沉+前端打包瘦身+测试DB共享

### Changed
- chore: 添加pyproject.toml项目配置+gitignore诊断文件
- chore: /self_review通过—ruff format全量格式化+lint修复+mypy零错误
- chore: 代码风格统一—导入排序+类型注解+删除过期stress归档
- chore: 验证pre-commit类型检查-v2
- chore: 前端pre-commit类型检查—husky+lint-staged+vue-tsc

## v0.9.0 (2026-06-19)

### Added
- feat: 查询调度优化—ADAPTER_TYPE_MAP按类型路由+ahbz承接GB主力

### Fixed
- fix: Dockerfile补COPY web/dist/—前端产物进入镜像
- fix: locustfile更新Docker凭据为实际压测账号
- fix: init_users_table INSERT→INSERT OR IGNORE消除并发唯一约束冲突500
- fix: locustfile补CSRF Token头+并发登录重试+适配60req/min限流

### Changed
- chore: 压测放宽限流—MAX_ATTEMPTS 5→100, API_RATE_LIMIT 60→1000
- chore: CI启用Buildx+Registry Cache加速Docker构建
- chore: gitignore加web/stats.html构建产物
- chore: 前端依赖更新—DataView+Paginator替代DataTable+Column

## v0.10.0 (2026-06-19)

### Added
- feat: 动态评分查询调度—实时配额+类型匹配+冷却感知替代固定优先级

### Changed

## v0.11.0 (2026-06-19)

### Added
- feat: 适配器查询成功率持久化—adapter_stats表+动态评分接入

### Changed

## v0.12.0 (2026-06-19)

### Added
- feat: adapter_stats扩展响应时间+冷却统计+get_adapter_report报告

### Changed

## v0.12.1 (2026-06-19)

### Fixed
- fix: query_batch类型收窄—result is not None直接判断消除mypy union-attr

### Changed

## v0.12.2 (2026-06-19)

### Fixed
- fix: adapter_stats数据链路打通+压测凭证脱敏+确认点修复+补充验证

### Changed

## v0.12.3 (2026-06-20)

### Fixed
- fix: TCCSAS/TZZB/TCED归入group分类+新增--stop-after=cli参数

### Changed
- chore: 日志回归+名称决策+版本统一+双Bug修复—24文件335行增量
- chore: pre-commit自动修复—ruff-format格式化+文件末尾换行
- chore: tests+UI目录mypy零错误—配置压制attr-defined+定向修复类型+F401清理
- chore: 死代码清理+前后端契约修复+CLI决策表+recheck修复+rotator_state钩子
- chore: 压测脚本7项优化—凭证传递+step3报告+skip-cli+容差+解析健壮性

## v0.12.4 (2026-06-21)

### Fixed
- fix: 国外标准路由修复+双主站+二次分桶+日志统一+pending修复+UI实时更新—19文件472行

### Changed

## v0.12.5 (2026-06-21)

### Fixed
- fix: StreamHandler恢复stderr避免日志混入stdout导致scan→query数据传递失败

### Changed
- chore: gitignore增加*.db排除数据库文件

## v0.12.6 (2026-06-21)

### Fixed
- fix: HTML标签剥离+精确匹配口径+hbba回退+csres间隔+Docker分批+overflow恢复+pending过滤—12文件311行

### Changed

## v0.12.7 (2026-06-22)

### Changed

## v0.12.8 (2026-06-22)

### Added
- feat: 支持WinUI通过Web端公告缓存查询

### Fixed
- fix: /api/announce/lookup 加入公开路径白名单
- fix: correct import path in moved mock_download.py
- fix: remove unused mock import to resolve PyInstaller ModuleNotFoundError

### Changed
- docs: update README directory structure - add quality module and fix adapter count
- chore: ignore capture_*.png and remove tracked screenshot from repo
- refactor: isolate mock adapters to tests/ + version governance + CI gates + pre-commit

## v0.13.0 (2026-06-22)

### Added
- feat: API Key 认证方案 —— 管理接口 + 前端页面 + WinUI 集成

### Fixed
- fix: ci.yml 新增 version-bump job + 移除 concurrency 锁 + build 依赖版本号产出
- fix: 原子化版本治理 —— 合并release.yml到ci.yml的version_bump job

### Changed

## v0.13.1 (2026-06-22)

### Fixed
- fix: ci.yml 增加 pyinstaller job（Windows exe + Release），依赖 version-bump 产出
- fix: PyInstaller job 移入 ci.yml 作为 version-bump 下游，避免 GITHUB_TOKEN 递归触发限制
- fix: 恢复 PyInstaller 打包 —— 独立 workflow，由 tag 推送触发

### Changed

## v0.13.2 (2026-06-22)

### Fixed
- fix: 移除 ApiKeys.vue 中未使用的 store 导入，修复前端构建

### Changed

## v0.13.3 (2026-06-22)

### Added
- feat: WinUI热启分两轮——甲轮本地回归+乙轮Web缓存验证
- feat: 压测v3.0 —— 7项改造（版本校验+API Key+缓存路由+顺序调整+5新测试+指标+清理）

### Fixed
- Merge branch 'feature/web-announce-cache'
- fix: 修复ci.yml中pyinstaller触发条件 + 恢复concurrency + version-bump增加tag输出

### Changed

## v0.13.4 (2026-06-22)

### Added
- feat(governance): complete capability heritage framework — Phase 1+2+3
- feat(progress): unified 60s heartbeat at engine layer for CLI/WinUI/Docker

### Fixed
- fix(ci): use env var for commit message to avoid shell injection from parentheses
- refactor(auth): simplify API token to static scheme (PILOTSTD_API_TOKEN)
- fix(rotator): trigger cooldown in record_success when max_requests reached
- docs(governance): add README and team announcement for governance framework

### Changed
- ci: integrate observability self-check into CI and PR template

## v0.14.0 (2026-06-22)

### Added
- feat(settings): add API token display/refresh tab, deprecate old api-keys page

### Changed

## v0.15.0 (2026-06-22)

### Added
- feat(api): deprecate old api-keys endpoints with 410 Gone

### Changed

## v0.15.1 (2026-06-22)

### Fixed
- fix: remove announce/lookup from auth whitelist + fix BIZ-12 NoneType error

### Changed

## v0.15.2 (2026-06-22)

### Fixed
- fix: strip pst_ prefix before hashing in verify_api_key

### Changed

## v0.15.3 (2026-06-22)

### Fixed
- fix: add pst_ prefix to API token in stress_web.py auth tests

### Changed
- docs: update STATUS.md with AUTH-02/BIZ-12/verify_api_key fixes

## v0.15.4 (2026-06-22)

### Fixed
- i18n: translate all logger messages to Chinese across project

### Changed
- docs: add heartbeat mechanism verification (结论C — 正常工作)
- docs: add test output directory mapping, merge dedup verification
- docs: reclassify skipped_exists=21 as PASS (design verification)
- docs: condense WinUI QA deviation analysis per user review
- docs: add WinUI round A query_exact deviation analysis to STATUS.md
- docs: update BIZ-12 status per user verification report
- docs: update STATUS.md with Step 3 test results (35/37 PASS)

## v0.16.0 (2026-06-22)

### Added
- feat: switch log rotation from daily to 256KB size-based

### Changed
- docs: add log rotation and Chinese translation items to STATUS.md

## v0.17.0 (2026-06-22)

### Added
- feat: add QueryEngine idle detection + progress bar 90%→100% flow

### Changed
- docs: add progress bar improvement feasibility check (3.11)
- docs: add progress bar and background behavior analysis (3.10)

## v0.17.1 (2026-06-22)

### Fixed
- fix: progress bar now advances 90%→99% during query, not stuck at 90%

### Changed

## v0.18.0 (2026-06-22)

### Added
- feat: add .env file support via python-dotenv

### Changed
- docs: finalize progress bar section 3.12 per user review

## v0.18.1 (2026-06-22)

### Fixed
- fix: resolve all 5 mypy type errors across project

### Changed

## v0.18.2 (2026-06-22)

### Fixed
- fix: mypy --strict reduction from 950 to 265 errors (-72%)

### Changed
- docs: streamline type error fix summary per user review
- docs: add type error fix summary to STATUS.md (3.13)

## v0.18.3 (2026-06-22)

### Fixed
- fix: mypy --strict reduction from 950 to 280 errors (-70%)

### Changed

## v0.19.0 (2026-06-23)

### Added
- feat: stress test v8.0 — disband step0, 38 endpoints, announce sample, report format
- feat: capabilities_registry v2.1 (flat table + auto-update script + pre-commit hook)
- feat: stress test v7.0 — capability mapping, preconditions, assertions, P0/P1 code fixes
- feat: progress bar shows red failure state on auto_run exception
- feat: add Mixin governance (PR template checklist, tracking table, pre-commit hook)

### Fixed
- fix: clear all 29 remaining E501 errors (inline noqa + per-file-ignores)
- fix: complete mypy --strict cleanup (159→0 errors, all non-UI modules)
- fix: resolve 38 no-any-return errors with type: ignore annotations (Task 5/7)
- fix: add type arguments to generics, fix missing imports (Tasks 3/7, 4/7)
- fix: add type annotations for 39 untyped definitions (Task 2/7)
- fix: remove 37 unused type: ignore comments (Task 1/7)
- fix: ignore mypy errors for pilotstd.ui.* (PyQt6 mixin conflict)

### Changed
- docs: update capabilities_registry to v2.0 (43→54 records, 100% coverage)
- docs: add announcement sync trigger analysis (manual-only, no preheat)
- docs: add mypy --strict cleanup implementation plan
- docs: add mypy --strict final fix design spec
- docs: add mypy --strict fix summary to STATUS.md (3.14)

## v0.19.1 (2026-06-23)

### Fixed
- fix: replace [轮转器] with [ROTATOR] log marker in rotator.py

### Changed

## v0.19.2 (2026-06-23)

### Fixed
- fix: 4 fixes — db text_factory, cache write, token env, clipboard + std_name

### Changed

## v0.19.3 (2026-06-23)

### Fixed
- fix: CI build-and-push checkout bump后的tag，解决镜像版本号不一致

### Changed

## v0.20.0 (2026-06-23)

### Added
- feat: stress test v9.0 — modular split + directory precheck + revised plan

### Changed

## v0.21.0 (2026-06-24)

### Added
- feat: 公告抓取全量存储+去重前移+批量写入，任务页新增删除按钮

### Changed

## v0.21.1 (2026-06-24)

### Fixed
- fix: check_mixin 钩子仅检测新增文件，修复 ruff 格式化后已有 Mixin 误报
- fix: parser.py OCR 结果空值检查修复 mypy 类型错误

### Changed
- style: ruff format 全局格式化

## v0.22.0 (2026-06-24)

### Added
- feat: 测试代码与压测方案v9.1对齐——版本号更新+公告抓取量修正+WinUI乙轮+P2认证/端点自检

### Changed

## v0.23.0 (2026-06-24)

### Added
- feat: 统一三端调用链——归档/查询/缓存/配置四阶段收敛

### Changed

## v0.23.1 (2026-06-24)

### Fixed
- fix: test_archive_calls_organize mock 从 organize 迁移到 archive_standards

### Changed
- chore: .gitignore 新增 tests/.cache/ 排除压测缓存产物

## v0.23.2 (2026-06-24)

### Fixed
- fix: /api/announce/check 增加 sync 参数，压测同步执行公告抓取

### Changed

## v0.23.3 (2026-06-24)

### Fixed
- fix: 公告样本生成改为 sync=true 同步执行后直接读取 results

### Changed

## v0.24.0 (2026-06-24)

### Added
- feat: ValidityChecker 增加 get_due_standards+random_slice+28天调度
- feat: 标准时效性检查模块——v16迁移+ValidityChecker+archive_standards集成

### Changed

## v0.25.0 (2026-06-24)

### Added
- feat: 通知模块——v17迁移+三渠道+Manager+Web API+集成点

### Changed

## v0.26.0 (2026-06-24)

### Added
- feat: v18迁移——fetch_task异步抓取任务表+adapter_health适配器熔断表

### Changed

## v0.27.0 (2026-06-24)

### Added
- feat: 公告抓取异步API——/api/announcements/fetch+status+results, sync=true弃用

### Changed

## v0.28.0 (2026-06-24)

### Added
- feat: 适配器熔断监控Web页面——DashboardView+路由+菜单
- feat: 熔断管理API——GET/PUT /api/adapter/status+config
- feat: 适配器熔断核心逻辑——BaseAnnounceAdapter嵌入熔断+阶梯时长+24h归零

### Changed

## v0.28.1 (2026-06-24)

### Fixed
- fix: 配置热加载(@property)+daemon=False+僵尸任务清理

### Changed

## v0.28.2 (2026-06-24)

### Fixed
- fix: 侧边栏'适配器监控'改用中文

### Changed

## v0.28.3 (2026-06-24)

### Fixed
- fix: i18n nav.dashboard 翻译补充(zh-CN/en/zh-TW)

### Changed

## v0.29.0 (2026-06-25)

### Added
- feat: Web UI 四个管理页面 + 压测 v9.2 + OCR 凭据保护统一
- feat: Docker 重启即更新机制（PILOTSTD_AUTO_UPDATE）

### Changed

## v0.29.1 (2026-06-25)

### Fixed
- fix: 构建类型安全 — 判别联合类型 + 未使用变量修复 + 压测方案跨机说明

### Changed

## v0.30.0 (2026-06-25)

### Added
- feat: 简化自更新机制 + 修复公告 SQL 超限 + 压测方案同步

### Changed

## v0.30.1 (2026-06-25)

### Fixed
- fix: docker-compose.yml 统一硬编码写法，删除 Shell 变量语法

### Changed

## v0.31.0 (2026-06-25)

### Added
- feat: 参照MoviePilot实现超级用户初始化+git pull自更新

### Changed

## v0.31.1 (2026-06-25)

### Fixed
- fix: 统一 entrypoint.sh 路径到 /app/entrypoint.sh

### Changed
- chore: 清理 docker-compose.yml 和 .env.example 冗余变量

## v0.31.2 (2026-06-25)

### Fixed
- fix: entrypoint.sh 动态赋予 update.sh 执行权限

### Changed

## v0.31.3 (2026-06-25)

### Fixed
- fix: 删除旧ADMIN_USERNAME逻辑，超级用户初始化移至DB迁移之后

### Changed

## v0.31.4 (2026-06-25)

### Fixed
- fix: 修正超级用户初始化SQL匹配users表结构；追加v19迁移确保users表存在

### Changed

## v0.31.5 (2026-06-25)

### Fixed
- @ feat: Web仪表板6阶段改造 — 可拖拽首页+通知/时效性/熔断整合进设置页+钉钉渠道+用户管理完善+公告中文化+文件选择器

### Changed

## v0.31.6 (2026-06-25)

### Fixed
- @ fix: 压测脚本适配+缓存检查工具+进度条异常状态+Scheduler 定时任务更新

### Changed

## v0.31.7 (2026-06-26)

### Fixed
- fix: 前端CI修复 — AppLayout路由补全+Node22+主题迁移至@primeuix+vue-i18n升级v11

### Changed

## v0.32.0 (2026-06-26)

### Added
- feat: 方案C混合更新机制 — 版本比较+前端更新+依赖编译+Web触发重启

### Changed

## v0.32.1 (2026-06-26)

### Fixed
- fix: 路径白名单修复+设置页保存按钮重构+删除按钮可见性+筛选按钮布局

### Changed

## v0.32.2 (2026-06-26)

### Fixed
- fix: get_allowed_roots移除os.path.exists守卫，修复Windows测试环境白名单为空

### Changed

## v0.32.3 (2026-06-26)

### Fixed
- @ feat: 仪表板改造+8条UI/UX优化+四主题系统+测试双轨方案

### Changed

## v0.32.4 (2026-06-26)

### Fixed
- fix: CI构建修复 — tsconfig排除测试辅助文件+安装@types/jsdom@types/node

### Changed

## v0.33.0 (2026-06-26)

### Added
- feat: Web页面布局美化+Docker更新脚本优化 — 毛玻璃导航栏/渐变卡片/响应式优化/触摸设备适配

### Changed

## v0.34.0 (2026-06-26)

### Added
- feat: 日志标签i18n+PROGRESS常量化+6门禁脚本+三端日志统一+乙轮数据源修正+OCR掩码补全

### Changed

## v0.35.0 (2026-06-26)

### Added
- feat: 项目可安装化+死代码清理+CI包安装+观测规则修复

### Changed

## v0.36.0 (2026-06-27)

### Added
- feat: 数据库表重命名+布局后端存储+卡片管理+通知四渠道+Web四问题修复

### Changed
- style: Ruff格式化 — tests/ 目录行宽120字符约束

## v0.37.0 (2026-06-27)

### Added
- feat: 统一配置管理+缓存系统+文件监控+任务队列+可信IP+删除按钮修复

### Changed

## v0.37.1 (2026-06-27)

### Fixed
- fix: CI测试修复—前端Store适配+迁移空表防护+Node24环境变量

### Changed

## v0.37.2 (2026-06-27)

### Fixed
- @ feat: TS构建修复+死代码检测门禁—pre-commit/CI/文档三端联动 @

### Changed

## v0.37.3 (2026-06-27)

### Fixed
- @ fix: update.sh中set -e误杀compare_versions业务返回值导致更新中断 @

### Changed

## v0.37.4 (2026-06-27)

### Fixed
- @ fix: v23迁移last_accessed_at列DEFAULT改为NULL以兼容SQLite ALTER TABLE限制 @

### Changed

## v0.37.5 (2026-06-27)

### Fixed
- @ feat: update.sh重构为MoviePilot全量替换模式+GATE-08依赖完整性门禁+watchdog补全 @

### Changed

## v0.37.6 (2026-06-27)

### Fixed
- @ fix: pyinstaller job中bash语法步骤补全shell: bash避免Windows执行失败 @

### Changed

## v0.37.7 (2026-06-27)

### Fixed
- @ fix: pyinstaller job设置defaults.run.shell:bash固化Windows Shell规范 @

### Changed

## v0.37.8 (2026-06-27)

### Fixed
- @ fix: pyinstaller job中PowerShell步骤显式指定shell:pwsh避免defaults.bash冲突 @

### Changed

## v0.37.9 (2026-06-27)

### Fixed
- @ docs: 将 CI Shell 规范写入 capabilities_registry.md @

### Changed

## v0.37.10 (2026-06-27)

### Fixed
- @ fix: Database.execute()的conn.rollback()在SQLite自动提交下报no transaction active掩盖真实错误 @

### Changed

---

## v0.5.27 (2026-06-17)

### 修复
- 查询引擎多轮重分配进度超 100% 问题
- CLI 查询进度 stderr 不入日志，细粒度进度不可追溯
- 查询引擎冗余的 fallback 解析器（`_parse_standard_number_str_fallback`）
- 公告进度回调中间层未透传，CLI 看不到公告抓取进度
- 公告混合路由重复解析 HTML+附件
- `ui.*` 配置键统一迁移到 `appearance.*` 前缀
- 进度条孤儿 widget 残留
- `normalize_archive_name` 死代码清理
- Web OCR 设置腾讯云排版错位
- `test_quality_*` 引用已删除模块
- 版本号不一致（`web/package.json` / i18n locale / Docker image）
- Dockerfile COPY `web/dist/` 失败
- 桌面端更新权限检测 + API 限流频控
- `/api/system/version` 加鉴权白名单

### 新增
- `/api/system/update` 10 个测试场景覆盖
- 逐桶查询设计文档

---

## v0.5.26

### 修复
- `_classify_code` 保留 IEC TR/TS/PAS 类型前缀的 foreign 路由

---

## v0.5.25

### 修复
- `_ocr_pdf` 对 OcrScheduler 返回 str 做类型判断，避免 AttributeError
- 全链路补全 num_prefix/num_suffix，UI+driver 改用 get_full_number()

### 重构
- ahbz 结果匹配改为结构化比对，补提 replaceSd/expiryDate/executeDate
- facade + scan/parser 改用 classify_std_code()，消除重复分类逻辑
- ahbz 改用 classify_std_code()，补全 NBSHT/TCCSAS 等 8 个代号

### 新增
- classify_std_code() 公共分类方法到 std_utils

---

## v0.5.24

### 修复
- ahbz _STATUS_MAP A/W 映射对调，删除不存在的 D 状态
- test_scheduler_legacy_mode 用假凭据替代读配置，CI 环境无 OCR 密钥不再失败

---

## v0.5.23

### 修复
- announce 步骤消除重复造轮——monkey-patch _fetch_list，复用 fetch_announcements
- 公告 10 条限制——猴子补丁 _fetch_list 仅 1 次 API 调用拿 10 条，不翻页
- stress_driver 公告步骤 since_date 清空，纯靠 page_size=10+切片[:10] 限 10 条
- 压力测试公告步骤直连引擎各类型精确 10 条，不动生产代码
- 重建 Web 前端 dist (OCR 三云设置页) + config 默认值迁移
- i18n 翻译文件 OCR 键名同步——三云独立字段 + 保存不可复制提示
- WinUI 设置页 OCR 敏感字段保存后清空 + 加载时仅显占位符
- WinUI 设置页 OCR 三云独立字段 + 移除旧 provider 选择器
- Web 设置页 + API 层 OCR 配置键迁移到新键名，补腾讯云 SecretKey 字段

### 新增
- OCR 线程 THREAD_PRIORITY_IDLE 最低优先级
- OcrSlot 单槽位 + QPS 限速 + 错误应急 + OcrScheduler 双槽调度器
- OcrCounters 计数器 + ProviderCooling 冷却 + PDF 拆页工具
- OcrResult 结构化返回值 + 三 provider 适配 + 错误码分类

---

## v0.5.22

### 修复
- 腾讯云 OCR 补 IsPdf=True 参数
- OCR 配置键拆分——百度/腾讯/阿里各自独立键名
- 公告适配器 _fetch_detail 硬编码 GB URL + stress_driver 导入 + 版本号同步至 0.5.22
- 更新测试匹配规则 0 (非 exact→pending) + Docker 权限认证测试

---

## v0.5.21

### 修复
- 注册 pytest 自定义参数 --source --output --step1 --step2
- 回退非交互跳过 + winui-only 不再硬编码 skip_docker
- 采标文案改为'采标因版权原因，需自行查找下载'
- 压测 stdin 非交互跳过 + announce 全类型 + 交叉对比只比 exact
- 非 exact 匹配结果统一归入 pending + 采标统计词去受限
- 路径安全校验 + pending 不进 auto 归档 + 进度条右边距
- Docker 权限隔离 + Web 登录去除默认 admin

### 新增
- 公告失败汇报(本地文件+弹窗) + 公告后台异步低优先级
