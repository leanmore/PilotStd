// Playwright config — 前端 E2E 回归测试
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 60000,
  retries: 1,
  // 报告与现场还原产物（T-41 后续 · CI 可观测性）：
  // · html 报告 ⇒ `web/playwright-report/`（与 `.github/workflows/ci.yml` 的 `upload-artifact` 路径一致）
  // · `open: 'never'` ⇒ CI 环境不得尝试打开浏览器
  // · 失败现场（截图/trace）落在下方 `outputDir`，由同一上传步骤一并收集
  reporter: [['list'], ['html', { outputFolder: 'playwright-report', open: 'never' }]],
  outputDir: 'test-results',
  use: {
    baseURL: 'http://localhost:5173',
    navigationTimeout: 60000,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  webServer: {
    command: 'pnpm dev --host 0.0.0.0 --port 5173',
    port: 5173,
    timeout: 120_000,
    reuseExistingServer: true,
    stdout: 'pipe',
    stderr: 'pipe',
  },
});
