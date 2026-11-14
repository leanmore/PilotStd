# A-33 查证：20 个 `_get_*_adapter` 懒加载函数（只读，2026-11-14）

> 触发：用户要求"先查清楚，不要直接删或留"，结论只允许三种（①有明确用途 / ②逆向分析产物 / ③确无来源无引用无对应）。
> 方法：`git log -S` 追引入点；逐条 `git grep -w` 统计引用；对照 `adapters/registry.py` 与模板 hook 测试。

## 一、清单与来源

- **位置**：全部在 `pilotstd/query/__init__.py`（162 行），共 **20 个** `def _get_<x>_adapter() -> Type[Any]`。
- **来源**：该文件由 **Initial commit `9256b383`**（"Initial commit: PilotStd - 标准文件管理工具"）引入；
  `git log -S _get_std_gov_adapter -- pilotstd/query/__init__.py` 只命中这一个提交，**此后无新增/修改**。
- **commit 上下文**：初始提交，message 无"逆向/分析/适配器清单"字样；同批没有"分析报告/清单"类文件可对应。
  ⇒ **②（逆向/分析产物）无证据，不成立。**

## 二、对应关系（对照 `pilotstd/query/adapters/registry.py`）

`registry.py` 是 #44/#48 确立的**单一真相源**：直接 `from .xxx import XxxAdapter` 导入全部适配器，并维护
`ALL_ADAPTERS: dict[str, type[BaseAdapter]]`。对照结果：

| 项 | 结果 |
|---|---|
| 适配器模块数 | 22（`ahbz/ccsn/csres/cssn/dbba/energy/gongbiaoku/hbba/iso_gov/jjg/jtst/mee/miit/ncha/njbz365/nrsis/sppt/sppt_local/std_gov/tdpress/ttbz/mock`） |
| getter 数 | 20 |
| 一一对应 | **否**：缺 `ahbz`、`dbba` 两个（二者在 registry 中存在，但无对应 getter） |
| 命名/返回类型 | 与 registry 条目一致（返回对应 `XxxAdapter` 类，`Type[Any]`） |
| 模板 hook | `tests/test_adapter_hook_anchors.py::test_hook_drops_dead_lazy_getter` 断言脚手架**不再生成** `def _get_{ADAPTER_NAME}_adapter` ⇒ 该模式已停止新增 |

## 三、引用面（逐条 `git grep -w`，含 `.py` 与 `.md`）

| 分组 | getter | 引用 |
|---|---|---|
| 有引用（9） | `csres / std_gov / njbz365 / hbba / iso_gov / mock / ttbz / mee / energy` | **仅** `tests/test_query_init.py`（文件自述"补测 懒加载适配器函数"），每处 2 行：import + 断言返回类名 |
| 零引用（11） | `nrsis / jtst / ccsn / jjg / sppt / gongbiaoku / sppt_local / tdpress / ncha / miit / cssn` | **0 处**（生产、测试、脚本、文档全无） |

补充核查：
- 无 `__getattr__` / `globals()[...]` 之类的动态取名（query 包内无命中）；
- 无字符串反射注册（registry 用的是显式 import，不是按名字 `getattr` 取 getter）；
- 无文档引用（`docs/` 下 0 命中）。

## 四、按三分法判定

| 结论 | 是否成立 | 理由 |
|---|---|---|
| ② 逆向/分析产物 | **不成立** | 来源是 Initial commit，无分析上下文、无对应清单文件 |
| ③ 确无来源无引用无对应 | **不成立** | "无对应"不满足：20 个 getter 与 registry 里的适配器同类同名（只缺 2 个） |
| ① 有明确用途 | **成立，但用途很窄** | 唯一消费者是 `tests/test_query_init.py`：把"包级导出 `_get_x_adapter` 返回正确类"当作契约锁定；生产侧 0 调用（registry 直接 import） |

**结论：归 ①（保留），不是 ②/③，因此本轮不删。** 但必须注明它是"历史懒加载导出面"：

- 新增适配器一律走 `adapters/registry.py`，**不要再加 getter**（模板 hook 已据此收紧）；
- 若未来要删：属于"删除一个仅被测试锁定的包导出契约"，需要同时改 `tests/test_query_init.py`，不在本次三分法覆盖范围内，应单独裁定。

## 五、给文档的落地建议（未执行，等确认）

在 `pilotstd/query/__init__.py` 顶部加一句注释：
`# 历史懒加载导出（A-33）：新增适配器请登记 adapters/registry.py；本组函数仅保留包导出兼容，勿新增。`
