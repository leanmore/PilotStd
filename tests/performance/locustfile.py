# tests/performance/locustfile.py
# PilotStd 全链路压测：查询 → 下载
#
# 启动方式（单机）:
#   cd tests/performance
#   locust -f locustfile.py --host=http://192.168.1.18:9028
#
# 分布式模式（1 master + N workers）:
#   locust -f locustfile.py --master --host=http://192.168.1.18:9028
#   locust -f locustfile.py --worker --master-host=<master_ip>   (在每台 worker 上)
#
# Web UI: http://localhost:8089
#
# 注意：服务端有 60 req/min/IP 限流，压测时控制并发数 ≤ 10。

import random
import time

from locust import HttpUser, between, task

# ── 预设标准号样本（15 个，覆盖国标/行标/地标/国际）────────────────
SAMPLE_NUMBERS = [
    "GB/T 19001-2016",
    "GB/T 1.1-2020",
    "GB 50016-2014",
    "SH/T 1610-2011",
    "NB/T 47013-2015",
    "JB/T 4730-2005",
    "HG/T 20592-2009",
    "SY/T 0048-2016",
    "DB11/T 1190-2015",
    "DB31/T 987-2016",
    "ISO 9001:2015",
    "ISO 14001:2015",
    "ASTM A370-2020",
    "ASME BPVC VIII-2021",
    "API 610-2010",
]

# ── 默认凭据 ───────────────────────────────────────────────
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin"


class PilotStdUser(HttpUser):
    """模拟用户：登录 → 查询 → 下载。

    httpx 客户端自动管理 Cookie：登录后服务端 set_cookie 的
    pilotstd_token 和 csrf_token 会在后续请求自动携带。
    """

    # 服务端限流 60 req/min/IP，用较长间隔避免触发
    wait_time = between(10, 20)

    def on_start(self):
        """登录并提取 CSRF Token。服务端要求所有 POST 请求
        携带 X-CSRF-Token 头，值必须与 csrf_token Cookie 一致。
        """
        # 并发登录可能触发 SQLite 表初始化竞态（500），重试 3 次
        for attempt in range(3):
            resp = self.client.post(
                "/api/login",
                data={"username": DEFAULT_USERNAME, "password": DEFAULT_PASSWORD},
                name="/api/login",
            )
            if resp.status_code == 200:
                break
            time.sleep(2)

    def _csrf_header(self) -> dict:
        """从客户端 Cookie Jar 中提取 csrf_token，构建 X-CSRF-Token 请求头。"""
        csrf = self.client.cookies.get("csrf_token", "")
        if csrf:
            return {"X-CSRF-Token": csrf}
        return {}

    # ── 任务 ──────────────────────────────────────────────────

    @task(2)
    def query_only(self):
        """仅查询：随机取 3-5 个标准号。"""
        numbers = random.sample(
            SAMPLE_NUMBERS, min(len(SAMPLE_NUMBERS), random.randint(3, 5))
        )
        with self.client.post(
            "/api/query",
            json={"numbers": numbers},
            headers=self._csrf_header(),
            name="/api/query",
            catch_response=True,
        ) as resp:
            if resp.status_code == 401 or resp.status_code == 403:
                resp.failure(f"认证失败({resp.status_code}): {resp.text[:150]}")
            elif resp.status_code >= 500:
                resp.failure(f"服务端错误({resp.status_code}): {resp.text[:150]}")
            elif resp.status_code != 200:
                resp.failure(f"查询失败({resp.status_code}): {resp.text[:150]}")

    @task(1)
    def query_then_download(self):
        """全链路：查询 → 下载可下载结果。"""
        numbers = random.sample(
            SAMPLE_NUMBERS, min(len(SAMPLE_NUMBERS), random.randint(4, 6))
        )
        # 第一步：查询
        with self.client.post(
            "/api/query",
            json={"numbers": numbers},
            headers=self._csrf_header(),
            name="/api/query",
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"查询失败({resp.status_code})")
                return
            query_data = resp.json()

        # 第二步：提取可下载标准号（非采标 + 精确匹配）
        downloadable = [
            r["standard_number"]
            for r in query_data.get("results", [])
            if not r.get("is_adopted")
            and r.get("match_status") == "exact"
            and r.get("standard_number")
        ]
        if not downloadable:
            return

        # 第三步：下载（上限 3 个，控制服务端负载）
        dl_numbers = downloadable[:3]
        with self.client.post(
            "/api/download",
            json={"numbers": dl_numbers},
            headers=self._csrf_header(),
            name="/api/download",
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"下载失败({resp.status_code})")

    @task(1)
    def health_check(self):
        """轻量健康检查（白名单放行，不消耗限流配额）。"""
        self.client.get("/api/health", name="/api/health")
