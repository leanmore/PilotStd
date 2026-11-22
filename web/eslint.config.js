// eslint.config.js — 在既有配置上接入 DS 门禁（no-raw-button，阶段一 warn）
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
      // DS 阶段二完成：142 处存量已全部替换为 <AppButton>，规则升级为阻断级。
      // 任何新增的原生 <button> / PrimeVue <Button> 都会让 lint 失败。
      'custom/no-raw-button': 'error',
      // DS 阶段三模块一完成：全站输入控件（原生 input/select/textarea 与 PrimeVue
      // InputText/InputNumber/Textarea/Password/Select/Dropdown/Checkbox/ToggleSwitch/
      // DatePicker/SelectButton）已全部替换为 App* 封装，规则升级为阻断级。
      // 任何新增的原生输入控件都会让 lint 失败。
      'custom/no-raw-input': 'error',
    },
  },
  // router.ts 是 titleKey 的定义点，豁免 no-raw-i18n-key
  {
    files: ['src/router.ts'],
    rules: {
      'custom/no-raw-i18n-key': 'off',
    },
  },
  // 测试文件刻意使用原始键（fixture/断言目标），不适用该规则
  {
    files: ['**/*.test.ts', '**/*.spec.ts'],
    rules: {
      'custom/no-raw-i18n-key': 'off',
      'custom/no-raw-button': 'off',
      'custom/no-raw-input': 'off',
    },
  },
  // DS 骨架自身允许用原生 button（封装点）
  {
    files: ['src/components/ui/AppButton.vue'],
    rules: {
      'custom/no-raw-button': 'off',
    },
  },
  // 阶段三进行中：App* 封装点内部允许原生标签与 PrimeVue 原语（样式在封装内收口）
  {
    files: ['src/components/ui/App*.vue'],
    rules: {
      'custom/no-raw-input': 'off',
    },
  },
  // PrimeVue 全局注册点：必须直接 import 原语组件（DS 封装之下仍依赖它们）
  {
    files: ['src/main.ts'],
    rules: {
      'custom/no-raw-input': 'off',
    },
  },
);
