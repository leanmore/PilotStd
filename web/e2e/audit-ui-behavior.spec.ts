import { test, expect } from '@playwright/test';

async function login(page, username: string, password: string) {
  await page.goto('/login');
  await page.waitForSelector('input[name="username"]');
  await page.fill('input[name="username"]', username);
  await page.fill('input[name="password"]', password);
  await page.click('button[type="submit"]');
  await page.waitForURL('**/', { timeout: 15000 });
}

const isBackendApi = (url: string) => {
  try {
    return new URL(url).pathname.startsWith('/api/');
  } catch {
    return false;
  }
};

test.describe('UI 行为审计', () => {
  test('普通用户访问管理页跳转 /403', async ({ page }) => {
    await login(page, 'user', 'User@123');
    for (const route of ['/task', '/quality', '/backup', '/resources']) {
      await page.goto(route);
      await page.waitForURL('**/403', { timeout: 10000 });
      await expect(page.locator('body')).toContainText('403');
    }
  });

  test('普通用户 /settings 只加载个人偏好，不请求 admin API', async ({ page }) => {
    const adminCalls: string[] = [];
    page.on('request', (req) => {
      const url = req.url();
      if (!isBackendApi(url)) return;
      if (/\/api\/(settings|tasks|backup|quality|resources|admin)/.test(url) && !url.includes('/api/user/')) {
        adminCalls.push(url);
      }
    });
    await login(page, 'user', 'User@123');
    await page.goto('/settings');
    await page.waitForTimeout(1500);
    await expect(page.locator('body')).toContainText('仅管理员');
    expect(adminCalls, `普通用户不应请求 admin API：${adminCalls.join(', ')}`).toEqual([]);
  });

  test('管理员访问管理页不跳 403', async ({ page }) => {
    await login(page, 'admin', 'Admin@123');
    for (const route of ['/task', '/quality', '/backup', '/resources']) {
      await page.goto(route);
      await page.waitForTimeout(800);
      expect(page.url()).not.toContain('/403');
      await expect(page.locator('body')).not.toBeEmpty();
    }
  });

  test('后端断开时页面有可读错误而非白屏', async ({ page }) => {
    await login(page, 'admin', 'Admin@123');
    await page.goto('/announce');
    await page.waitForTimeout(1500);
    await page.route('**/api/**', (route) => route.abort());
    await page.locator('button', { hasText: '刷新列表' }).first().click();
    await expect(page.locator('.err-msg')).toBeVisible({ timeout: 15000 });
    const text = (await page.locator('.err-msg').innerText()).trim();
    expect(text.length).toBeGreaterThan(0);
    expect(text).not.toContain('[object Object]');
  });

  test('公告列表 100 条/页可渲染且无卡死', async ({ page }) => {
    const pageErrors: string[] = [];
    page.on('pageerror', (e) => pageErrors.push(e.message));
    const rows = Array.from({ length: 100 }, (_, i) => ({
      announce_no: `2026-${String(i).padStart(3, '0')}`,
      announcement_title: `测试公告 ${i}`,
      source_site: 'announcement_gb',
      standard_count: 1,
      publish_date: '2026-01-01',
    }));
    await page.route('**/api/announce/results**', (route) =>
      route.fulfill({ json: { results: rows, total: rows.length } })
    );
    await page.route('**/api/announce/stats**', (route) =>
      route.fulfill({ json: { total: { all: 100, gb: 100, hb: 0, db: 0 }, matched: 0, new: { all: 0, gb: 0, hb: 0, db: 0 } } })
    );
    await login(page, 'admin', 'Admin@123');
    await page.goto('/announce');
    await page.waitForSelector('.announce-row', { timeout: 15000 });
    const dropdown = page.locator('.p-paginator-rpp-dropdown').first();
    await dropdown.click();
    await page.locator('li', { hasText: /^100$/ }).first().click();
    await page.waitForTimeout(1200);
    const count = await page.locator('.announce-row').count();
    expect(count).toBeGreaterThan(0);
    expect(count).toBeLessThanOrEqual(100);
    expect(pageErrors).toEqual([]);
    await expect(page.locator('.p-paginator')).toBeVisible();
  });

  test('弱密码表单显示中文错误而非 [object Object]', async ({ page }) => {
    await login(page, 'admin', 'Admin@123');
    await page.goto('/settings');
    await page.waitForTimeout(1500);
    const usersTab = page.locator('button', { hasText: '用户' }).first();
    await usersTab.click();
    await page.waitForTimeout(500);
    const addBtn = page.locator('button', { hasText: /新增|添加/ }).first();
    await addBtn.click();
    const dialog = page.locator('.p-dialog').last();
    await expect(dialog).toBeVisible();
    const inputs = dialog.locator('input');
    await inputs.nth(0).fill('audit_user_' + Date.now());
    await inputs.nth(1).fill('1');
    await dialog.locator('button', { hasText: /添加|保存|创建/ }).last().click();
    await page.waitForTimeout(1500);
    const body = await page.locator('body').innerText();
    expect(body).not.toContain('[object Object]');
    expect(/密码|长度|至少|字符/.test(body)).toBeTruthy();
  });
});
