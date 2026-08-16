import { test, expect } from '@playwright/test';

// 路由取消机制回归测试（第 3 层防复发）
// 验证 routeTag 迁移后：跨路由切换 + 同路由 Tab 切换均无 abort 误杀、无红字错误。
// 凭证通过环境变量注入，默认使用测试环境默认账密（与 quick-actions.spec.ts 一致）。
const USERNAME = process.env.E2E_USERNAME || 'admin';
const PASSWORD = process.env.E2E_PASSWORD || 'Admin@123';

test.describe('路由取消机制回归', () => {
  test.beforeEach(async ({ page }) => {
    const pageErrors: string[] = [];
    page.on('pageerror', (err) => pageErrors.push(err.message));

    await page.goto('/login');
    await page.waitForSelector('input[name="username"]');
    await page.fill('input[name="username"]', USERNAME);
    await page.fill('input[name="password"]', PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForURL('**/', { timeout: 15000 });
  });

  test('跨路由切换不产生 abort 错误、页面无红字', async ({ page }) => {
    const pageErrors: string[] = [];
    page.on('pageerror', (err) => pageErrors.push(err.message));

    // 依次跨路由导航（模拟 /task → /organize → /announce → /settings 等切换）
    for (const route of ['/organize', '/announce', '/standards-status', '/pending', '/settings']) {
      await page.goto(route);
      await page.waitForLoadState('networkidle');
    }

    // 快速连切（加剧竞态）
    for (const route of ['/organize', '/settings', '/announce', '/settings']) {
      await page.goto(route);
      await page.waitForTimeout(400);
    }

    const errCount = await page.locator('.err-msg').count();
    expect(errCount).toBe(0);

    const abortErrors = pageErrors.filter((e) => /abort|cancel/i.test(e));
    expect(abortErrors).toEqual([]);
  });

  test('Settings 同路由 Tab 切换无红字、无 abort 错误', async ({ page }) => {
    const pageErrors: string[] = [];
    page.on('pageerror', (err) => pageErrors.push(err.message));

    await page.goto('/settings');
    await page.waitForLoadState('networkidle');

    // 同路由 Tab 切换（query 变化、path 不变），不应触发全局取消
    for (const tab of ['站点', 'API 令牌', '用户', '时效性']) {
      await page.click(`.tab-bar button:has-text("${tab}")`);
      await page.waitForTimeout(600);
    }

    // 快速连切 3 次
    for (const tab of ['站点', 'API 令牌', '站点']) {
      await page.click(`.tab-bar button:has-text("${tab}")`);
      await page.waitForTimeout(300);
    }
    await page.waitForTimeout(1000);

    const errCount = await page.locator('.err-msg').count();
    expect(errCount).toBe(0);

    const abortErrors = pageErrors.filter((e) => /abort|cancel/i.test(e));
    expect(abortErrors).toEqual([]);
  });
});
