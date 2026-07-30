// ESLint flat config — 项目自定义规则 + TypeScript + Vue
import js from '@eslint/js';
import tseslint from 'typescript-eslint';
import pluginVue from 'eslint-plugin-vue';
import globals from 'globals';
import custom from './eslint-plugin-custom/index.js';

export default tseslint.config(
  // 全局忽略
  { ignores: ['e2e/**', 'dist/**', 'node_modules/**', 'eslint-plugin-custom/**'] },
  // JS/TS/Vue 推荐规则 — 全部降级为 warn（存量代码不阻塞）
  {
    ...js.configs.recommended,
    rules: Object.fromEntries(
      Object.keys(js.configs.recommended.rules || {}).map(k => [k, 'warn'])
    ),
  },
  ...tseslint.configs.recommended.map(c => ({
    ...c,
    rules: Object.fromEntries(
      Object.keys(c.rules || {}).map(k => [k, 'warn'])
    ),
  })),
  ...pluginVue.configs['flat/essential'].map(c => ({
    ...c,
    rules: Object.fromEntries(
      Object.keys(c.rules || {}).map(k => [k, 'warn'])
    ),
  })),
  // 项目自定义规则（唯一阻断级）
  {
    files: ['src/**/*.{ts,vue}'],
    plugins: { custom },
    languageOptions: {
      globals: globals.browser,
      parserOptions: {
        parser: tseslint.parser,
        ecmaVersion: 'latest',
        sourceType: 'module',
      },
    },
    rules: {
      'custom/no-raw-i18n-key': 'error',
      'custom/no-sensitive-persist': 'error',
    },
  },
  // router.ts 是 titleKey 的定义点，豁免 no-raw-i18n-key
  {
    files: ['src/router.ts'],
    rules: {
      'custom/no-raw-i18n-key': 'off',
    },
  },
);
