# pilotstd/wechat_ip/browser.py
# pragma: no cover — 需浏览器环境，暂不纳入单元测试覆盖率考核
# 详见 docs/testing/known-issues.md
"""企业微信可信 IP 更新——浏览器自动化。

优先使用 CloakBrowser（源码级反指纹），不可用时回退 Playwright。
"""

import logging
import os

from .logic import merge_ip_list, parse_cookie_string

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = os.environ.get("CLOAKBROWSER_CACHE", "/app/browser_cache")

# XPath 定位器（来自 weworkip v2.5 参考）
XPATH_SET_IP = '//div[contains(@class, "app_card_operate") and contains(@class, "js_show_ipConfig_dialog")]'
XPATH_TEXTAREA = '//textarea[@class="js_ipConfig_textarea"]'
XPATH_CONFIRM = '//a[@class="qui_btn ww_btn ww_btn_Blue js_ipConfig_confirmBtn"]'
LOGIN_CLASS = "login_stage_title_text"


class BrowserError(Exception):
    """浏览器操作异常。"""

    pass


class WechatIPUpdater:
    """企业微信可信 IP 更新器。

    Args:
        headless: 无头模式（生产环境必须 True）
        cache_dir: 浏览器缓存目录（挂载到宿主机持久化）
        engine: 引擎选择 'auto' | 'cloakbrowser' | 'playwright'
    """

    def __init__(
        self,
        headless: bool = True,
        cache_dir: str = DEFAULT_CACHE_DIR,
        engine: str = "auto",
    ):
        self.headless = headless
        self.cache_dir = cache_dir
        self.engine = engine
        self._browser = None
        self._context = None
        self._page = None

    def _launch(self):
        """启动浏览器。优先 CloakBrowser，不可用则 Playwright。"""
        os.makedirs(self.cache_dir, exist_ok=True)

        if self.engine in ("auto", "cloakbrowser"):
            try:
                self._launch_cloakbrowser()
                return
            except ImportError:
                logger.info("CloakBrowser 不可用，尝试 Playwright 备选")
            except Exception as e:
                logger.warning("CloakBrowser 启动失败: %s，回退 Playwright", e)

        if self.engine in ("auto", "playwright"):
            self._launch_playwright()
            return

        raise BrowserError(f"无法启动浏览器引擎 (engine={self.engine})")

    def _launch_cloakbrowser(self):
        """启动 CloakBrowser（反指纹 Chromium）。"""
        from cloakbrowser import launch  # type: ignore[import-not-found]

        self._browser = launch(
            headless=self.headless,
            humanize=True,
            user_data_dir=self.cache_dir,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        self._context = self._browser.new_context()
        self._page = self._context.new_page()
        logger.info("CloakBrowser 已启动 (headless=%s, cache=%s)", self.headless, self.cache_dir)

    def _launch_playwright(self):
        """启动 Playwright（备选方案）。"""
        from playwright.sync_api import sync_playwright  # type: ignore[import-untyped]

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch_persistent_context(
            user_data_dir=self.cache_dir,
            headless=self.headless,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        self._context = self._browser
        self._page = self._context.new_page()
        logger.info("Playwright 已启动 (headless=%s, cache=%s)", self.headless, self.cache_dir)

    def close(self):
        """关闭浏览器。"""
        try:
            if self._browser:
                self._browser.close()
                self._browser = None
        except Exception:
            pass

    def _parse_cookie(self, cookie_str: str) -> list[dict]:
        """将 HeaderString 格式 Cookie 转为浏览器格式。委托给 logic.parse_cookie_string。"""
        return parse_cookie_string(cookie_str)

    def _check_login_page(self) -> bool:
        """检查是否在登录页面。返回 True 表示需要登录。"""
        if self._page is None:
            return False
        try:
            el = self._page.query_selector(f".{LOGIN_CLASS}")
            return el is not None
        except Exception:
            return False

    def update_trusted_ip(
        self,
        app_url: str,
        ip_addr: str,
        cookie_str: str,
        mode: str = "append",
    ) -> bool:
        """更新单个应用的可信 IP——通过 Playwright/CloakBrowser 浏览器自动化。

        .. note:: E2E-Scope
           Pure logic (cookie parsing, IP merge) tested in tests/unit/test_wechat_ip_logic.py.
           This function's Playwright interaction chain requires integration/E2E testing.
           See: docs/testing/playbook.md §UI-layer skip rule #3

        Args:
            app_url: 应用管理页完整 URL
            ip_addr: 新公网 IP
            cookie_str: Cookie (HeaderString 格式)
            mode: 'append' 追加 | 'replace' 覆盖

        Returns: 是否成功
        """
        try:
            self._launch()
            assert self._page is not None, "浏览器启动失败"
            page = self._page

            # 1. 设置 Cookie
            cookies = self._parse_cookie(cookie_str)
            page.context.add_cookies(cookies)

            # 2. 访问应用管理页面
            page.goto(app_url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(1000)

            # 3. 检测 Cookie 是否有效
            if self._check_login_page():
                raise BrowserError("Cookie 已失效——检测到登录页面")

            # 4. 点击"配置IP"按钮
            btn = page.wait_for_selector(XPATH_SET_IP, timeout=10000)
            if not btn:
                raise BrowserError("未找到「配置IP」按钮——可能页面结构已变更")
            btn.click()
            page.wait_for_timeout(500)

            # 5. 定位文本域并输入 IP
            textarea = page.wait_for_selector(XPATH_TEXTAREA, timeout=5000)
            if not textarea:
                raise BrowserError("未找到 IP 文本域")

            if mode == "replace":
                textarea.fill(ip_addr)
            else:
                current = textarea.input_value()
                merged, skipped = merge_ip_list(current, ip_addr)
                if skipped:
                    logger.info("IP %s 已在列表中，跳过", ip_addr)
                    return True
                textarea.fill(merged)

            # 6. 点击确认
            confirm = page.wait_for_selector(XPATH_CONFIRM, timeout=5000)
            if not confirm:
                raise BrowserError("未找到确认按钮")
            confirm.click()
            page.wait_for_timeout(2000)

            logger.info("可信 IP 更新成功: %s → %s", app_url[-20:], ip_addr)
            return True

        except BrowserError:
            raise
        except Exception as e:
            raise BrowserError(f"浏览器操作异常: {e}")
        finally:
            self.close()

    def update_multiple(
        self,
        app_urls: list[str],
        ip_addr: str,
        cookie_str: str,
        mode: str = "append",
    ) -> dict[str, bool]:
        """批量更新多个应用。

        Returns: {app_url: success}
        """
        results = {}
        for i, url in enumerate(app_urls):
            url = url.strip()
            if not url:
                continue
            try:
                ok = self.update_trusted_ip(url, ip_addr, cookie_str, mode)
                results[url] = ok
                logger.info("第 %d/%d 个应用: %s", i + 1, len(app_urls), "OK" if ok else "FAIL")
            except BrowserError as e:
                logger.error("第 %d/%d 个应用失败: %s", i + 1, len(app_urls), e)
                results[url] = False
        return results


def validate_cookie(cookie_str: str, app_url: str, cache_dir: str = DEFAULT_CACHE_DIR) -> bool:
    """快速验证 Cookie 有效性——打开页面检查是否跳转登录页。"""
    updater = WechatIPUpdater(headless=True, cache_dir=cache_dir)
    try:
        updater._launch()
        assert updater._page is not None
        page = updater._page

        cookies = updater._parse_cookie(cookie_str)
        page.context.add_cookies(cookies)
        page.goto(app_url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(1000)

        return not updater._check_login_page()
    except Exception:
        return False
    finally:
        updater.close()
