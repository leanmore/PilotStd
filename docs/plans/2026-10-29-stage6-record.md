# 阶段六执行记录（2026-10-29）

## 隔离构建

- **本地干净 clone + docker build：未执行**——本机无 `docker` CLI（`docker ps` 即 "无法识别"），无法访问 daemon。
- **已做**：干净 clone 到临时目录并核对可导入（`python -c "import pilotstd"`，PYTHONPATH 指向 clone）。
- **标注**：不是真正隔离（同机、同 Python、同环境变量）；**无法发现"依赖本机环境"的问题**；真隔离待 CI 或第二台机器。

## README 命令逐条

| 命令 | 结果 |
|---|---|
| `pip install -r requirements-dev.txt` | 未重跑（当前环境已装；隔离环境待 CI） |
| `python -m pytest tests/ -k "not gui"` | 已实跑（全量 5827+） |
| `python main.py` | **需桌面环境，未验证** |
| `docker compose up -d` | **无 docker CLI，未验证** |
| `uvicorn docker.app:app --port 9028` | 未验证（会与现有 9028 冲突） |

## 应用级冒烟

新增 `scripts/smoke_app.py`（health → login → notification test；`--full` 预留扫描/查询）。
实跑（验证环境 `192.168.1.18:9028`）：

```
health 200 ok
login 200
config 200 enabled=True
notification_test 200 {"ok":true}
SMOKE PASS
```

扫描/查询未纳入默认（有副作用），待专用 staging 数据。
