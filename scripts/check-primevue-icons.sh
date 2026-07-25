#!/bin/bash
# 拦截任何 @primevue/icons 模块导入
# PrimeVue v4 图标使用 primeicons CSS class：<i class="pi pi-chevron-left"></i>
# 禁止：import ... from '@primevue/icons'
if grep -rEn "from\s+['\"]@primevue/icons" --include="*.ts" --include="*.vue" web/src/ 2>/dev/null; then
  echo "❌ 禁止导入 @primevue/icons 模块。请使用 primeicons CSS class：<i class=\"pi pi-chevron-left\"></i>"
  exit 1
fi
