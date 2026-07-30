// Playwright config — 前端 E2E 回归测试
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 30000,
  retries: 1,
  use: {
    baseURL: process.env.VITE_API_BASE_URL || 'http://localhost:9028',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  webServer: process.env.CI
    ? undefined // CI 中由 Docker service 提供后端
    : {
        command: 'python ../main.py',
        port: 9028,
        reuseExistingServer: true,
        timeout: 30000,
      },
});
