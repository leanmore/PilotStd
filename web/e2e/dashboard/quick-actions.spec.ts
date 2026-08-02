import { test, expect } from '@playwright/test';

test.describe('快捷操作卡片修复回归', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.waitForSelector('input[name="username"]', { timeout: 15000 });
    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', 'Admin@123');
    await page.click('button[type="submit"]');
    // DEBUG: capture post-login state before waiting
    await page.screenshot({ path: 'test-results/debug-post-login.png' });
    await page.waitForFunction(() =>
      window.__STORE_INITIALIZED__ === true ||
      document.querySelector('[data-testid="quick-actions-card"]') !== null
    );
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
