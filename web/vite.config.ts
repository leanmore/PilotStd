import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import { visualizer } from 'rollup-plugin-visualizer'

export default defineConfig({
  plugins: [
    vue(),
    // visualizer 仅在本地开发时启用，CI 环境跳过（open: true 在 CI 无意义）
    ...(process.env.CI ? [] : [visualizer({
      open: true,
      gzipSize: true,
      brotliSize: true,
    })]),
  ],
  resolve: {
    alias: { '@': resolve(__dirname, 'src') },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': process.env.VITE_API_TARGET || 'http://192.168.1.18:9028',
    },
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    rollupOptions: {
      output: {
        manualChunks(id) {
          // 强制将这三个组件合并到入口 chunk，避免异步分割导致运行时 undefined
          if (
            id.includes('FileMonitor') ||
            id.includes('CacheManager') ||
            id.includes('TaskManager')
          ) {
            return 'main'
          }
        },
        entryFileNames: 'assets/[name]-[hash].js',
        chunkFileNames: 'assets/[name]-[hash].js',
      },
    },
    chunkSizeWarningLimit: 2000,
  },
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['src/**/*.test.ts'],
    setupFiles: [resolve(__dirname, 'src/test-setup.ts')],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      thresholds: {
        lines: 48.07,
        branches: 32.12,
        functions: 23.42,
        statements: 44.11,
      },
    },
  },
})
