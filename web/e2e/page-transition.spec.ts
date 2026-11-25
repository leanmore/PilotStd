// 页面过渡回归（2026-11-25）—— 锁定「点击进入详情后内容空白、必须刷新浏览器」缺陷
//
// 根因：App.vue 用 `<Transition mode="out-in">` 包裹页面组件，而多数页面模板是**多根节点 fragment**
// （公告列表 = header + v-if 列表 + v-else 空态）。Vue 对 fragment 根无法执行 leave 回调
// （警告 `renders non-element root node that cannot be animated`），`out-in` 下新页面永远等不到入场
// → 客户端路由跳转后内容空白、刷新才恢复（生产实测复现）。
//
// 修复：过渡宿主改为单根 `.page-host` 包裹层（App.vue），本 spec 锁死两类场景：
//   1) 数据无关：从 fragment 页面（公告列表）切到其它页面，新页面必须渲染出来；
//   2) 真实链路：公告列表点击一行进入详情，标准列表必须**不刷新**就出现（无数据时跳过，CI 空库不阻断）。
import { test, expect, type Page } from '@playwright/test'

const USERNAME = process.env.E2E_USERNAME || 'admin'
const PASSWORD = process.env.E2E_PASSWORD || 'Admin@123'

async function login(page: Page): Promise<void> {
  await page.goto('/login', { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('input[name="username"]', { timeout: 20000 })
  await page.fill('input[name="username"]', USERNAME)
  await page.fill('input[name="password"]', PASSWORD)
  await page.click('button[type="submit"]')
  await page.waitForTimeout(2500)
}

test.describe('页面过渡（App.vue <Transition> 单根宿主）', () => {
  test('多根节点页面切走后，新页面必须正常渲染（防 out-in 挂起）', async ({ page }) => {
    await login(page)
    // 公告列表是多根节点 fragment：离开它时旧实现会挂起过渡
    await page.goto('/announce', { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(1500)

    // 点击侧栏「待处理」做客户端路由跳转（不刷新）
    const pendingNav = page.locator('a, button').filter({ hasText: '待处理' }).first()
    await pendingNav.click()

    // 新页面必须在 5s 内渲染出内容（旧缺陷：router-view 恒为空）
    await expect(page.locator('.page-host')).toBeVisible({ timeout: 5000 })
    await expect(page.locator('.page-host')).not.toBeEmpty({ timeout: 5000 })
    await page.waitForURL(/\/pending/, { timeout: 5000 })
  })

  test('公告列表点击进入详情：标准列表不刷新即出现', async ({ page }) => {
    await login(page)
    await page.goto('/announce', { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(2000)

    const rowCount = await page.locator('.announce-row').count()
    test.skip(rowCount === 0, '当前环境公告库为空（CI 空库），跳过真实数据链路用例')

    await page.locator('.announce-row').first().click()
    await page.waitForURL(/\/announce\/[^/]+\/[^/]+/, { timeout: 8000 })

    // 关键断言：不刷新页面，详情组件与标准列表必须出现
    await expect(page.locator('.announce-detail')).toBeVisible({ timeout: 8000 })
    await expect
      .poll(async () => page.locator('.announce-detail tbody tr').count(), { timeout: 12000 })
      .toBeGreaterThan(0)
  })
})
