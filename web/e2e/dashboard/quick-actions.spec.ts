import { test, expect } from '@playwright/test';

test.describe('快捷操作卡片修复回归', () => {
  test.beforeEach(async ({ page }) => {
    // Step 1: 防御性 API 健康检查，确保 backend 可达
    // 健康检查端点取自 docker/app.py 的 /api/health 路由
    const healthResp = await page.request.get('http://localhost:9028/api/health', { timeout: 30000 });
    expect(healthResp.ok()).toBeTruthy();

    // Step 2: 验证登录接口本身是否正常（排除 DB/Seed 问题）
    const loginResp = await page.request.post('http://localhost:9028/api/auth/login', {
      data: { username: 'admin', password: 'Admin@123' },
      timeout: 15000,
    });
    console.log('Login API status:', loginResp.status());
    console.log('Login API body:', await loginResp.text());
    expect(loginResp.ok()).toBeTruthy();

    // Step 3: 导航到前端登录页
    await page.goto('/login');
    await page.waitForSelector('input[name="username"]', { timeout: 15000 });
    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', 'Admin@123');
    await page.click('button[type="submit"]');

    // Step 4: 等待 Store 初始化，带超时诊断快照
    try {
      await page.waitForFunction(
        () => window.__STORE_INITIALIZED__ === true ||
              document.querySelector('[data-testid="quick-actions-card"]') !== null,
        { timeout: 45000 }
      );
    } catch (e) {
      const url = page.url();
      const storeFlag = await page.evaluate(() => (window as any).__STORE_INITIALIZED__);
      const cardExists = await page.evaluate(() => !!document.querySelector('[data-testid="quick-actions-card"]'));
      await page.screenshot({ path: 'test-results/store-init-timeout.png' });
      console.error(`[Store Init Timeout] URL: ${url} | Flag: ${storeFlag} | Card: ${cardExists}`);
      throw e;
    }
  });

  test('Admin 刷新后 scan_index 操作仍可见', async ({ page }) => {
    const actions = page.locator('[data-testid="quick-action-item"]');
    await expect(actions).toHaveCount(5);
    await expect(actions.filter({ hasText: '扫描索引' })).toBeVisible();

    await page.reload();
    await page.waitForSelector('[data-testid="quick-actions-card"]');

    await expect(actions).toHaveCount(5);
    await expect(actions.filter({ hasText: '扫描索引' })).toBeVisible();
  });

  test('快捷操作显示中文标签而非英文键名', async ({ page }) => {
    const labels = ['任务', '整理', '待处理', '公告', '扫描索引'];
    const actions = page.locator('[data-testid="quick-action-item"]');

    for (const label of labels) {
      await expect(actions.filter({ hasText: label })).toBeVisible();
    }

    await expect(actions.filter({ hasText: /nav\.|action\./ })).toHaveCount(0);
  });

  test('登出后重新登录不残留旧角色状态', async ({ page }) => {
    await page.click('[data-testid="user-menu-logout"]');
    await page.waitForURL('/login');

    await page.fill('input[name="username"]', 'user');
    await page.fill('input[name="password"]', 'User@123');
    await page.click('button[type="submit"]');
    await page.waitForSelector('[data-testid="quick-actions-card"]');

    const actions = page.locator('[data-testid="quick-action-item"]');
    await expect(actions.filter({ hasText: '扫描索引' })).toHaveCount(0);
    await expect(actions).toHaveCount(4);
  });
});
