#!/bin/bash
# 拦截 PrimeVue v4 错误的默认导出导入模式
# 匹配: import xxx from '@primevue/icons/kebab-case'
# 放行: import { XxxIcon } from '@primevue/icons'
if grep -rEn "import\s+[a-z]+\s+from\s+['\"]@primevue/icons/[a-z]+-?[a-z]*['\"]" --include="*.ts" --include="*.vue" web/src/ 2>/dev/null; then
  echo "❌ PrimeVue v4 图标请使用命名导出 { IconName } from '@primevue/icons'，禁止独立路径默认导出。参考 CI-FIX-005。"
  exit 1
fi
