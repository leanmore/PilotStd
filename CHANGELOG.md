# CHANGELOG

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
