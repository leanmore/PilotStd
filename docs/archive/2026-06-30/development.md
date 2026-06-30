# PilotStd 开发指南

## 环境搭建

```bash
# 1. 克隆仓库
git clone <repo-url>
cd PilotStd

# 2. 创建虚拟环境（Python 3.14）
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt  # 含测试工具
```

## 运行测试

```bash
# 全部测试（441 个用例）
python -m pytest tests/ -v

# 冷热双轮压力测试（需真实网络 + 源目录）
python -m pytest tests/stress_two_round.py -v -s --source D:\标准 --output E:\标准

# 全量压力测试（CLI 驱动，21 阶段 79 项）
python tests/stress_01_pipeline.py --source D:\标准 --output E:\标准

# 单元测试
python -m pytest tests/test_core.py tests/test_scanner.py tests/test_query.py -v

# GUI 测试（需显示器）
python -m pytest tests/gui/ -v

# 安全测试
python -m pytest tests/test_security.py -v
```

## 运行应用

```bash
# GUI 模式
python main.py

# CLI 模式
python main.py --cli

# Docker API 模式
cd docker
uvicorn app:app --reload
```

## 项目结构

```
pilotstd/
├── manager.py          # 业务门面
├── models.py           # 数据模型
├── core/               # 核心基础设施
│   ├── config.py       # 配置管理
│   ├── db.py           # 数据库（WAL + 版本迁移）
│   ├── file_utils.py   # 文件工具
│   └── file_index.py   # 文件索引
├── scan/               # 扫描与解析
│   ├── scanner.py      # 文件扫描器
│   └── parser.py       # 标准号解析器
├── query/              # 在线查询
│   ├── engine.py       # 查询引擎
│   ├── cache.py        # 缓存
│   └── adapters/       # 站点适配器 (6个)
├── download/           # 文件下载
│   ├── engine.py       # 下载引擎
│   └── adapters/       # 下载适配器
├── organizer/          # 文件归档
│   ├── mover.py        # 文件移动
│   └── dir_builder.py  # 目录构建
├── task/               # 任务队列
├── announcement/       # 公告监测
├── ui/                 # PyQt6 GUI
│   ├── main_window.py  # 主窗口
│   └── controllers/    # Mixin 控制器 (15个)
├── manager/            # 业务门面 + 服务层
│   ├── facade.py       # StandardManager 统一入口
│   ├── classifier.py   # 查询后分类路由
│   ├── pending_service.py
│   ├── scheduled_service.py
│   └── organizer_service.py  # 归档 + 内容去重
├── pipeline/           # 流水线路由
├── i18n/               # 三语言国际化
├── cli/                # 命令行接口
│   └── commands.py     # 10 子命令(scan/query/download/auto/...)
└── docker/             # Docker API + Web
```

## 代码规范

- 遵循 PEP 8
- 所有代码加中文注释（说明"为什么"而非"是什么"）
- 类名 PascalCase，函数/变量 snake_case，常量 UPPER_SNAKE_CASE
- 提交使用 Conventional Commits：`feat:`, `fix:`, `refactor:`, `doc:`, `test:`

## 核心架构

详见 `C:\Users\王杨\.claude\plans\elegant-finding-newt.md`（本地知识库架构设计 v4）。要点：

- **三表联动**：`standard_info_cache`（网络查询结果，仅 exact）→ `file_index`（文件 SHA 身份）→ `announcement_cache`（公告变更）
- **缓存策略**：仅 exact 写入，无 TTL，公告触发→网络复核→更新
- **文件名清洗**：`normalize_std_filename()` 统一入口（U+2215 斜杠、缺斜杠还原、垃圾后缀截断）

## SQL 安全规则

动态表名须为同文件全大写常量定义。SQLite 不支持表名参数化，f-string 构建 SQL 时表名必须来自 `TABLE_NAME = "xxx"` 形式的同文件常量。值参数一律用 `?` 占位符。

## 数据库迁移

在 `pilotstd/core/db.py` 中：
1. `CURRENT_SCHEMA_VERSION` 加 1
2. 添加 `@migration(N)` 装饰的函数
3. 迁移函数需幂等（列已存在时忽略错误）
