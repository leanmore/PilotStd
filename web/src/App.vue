<script setup lang="ts">
defineOptions({ name: 'App' })
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import AppToast from '@/components/ui/AppToast.vue'
import AppLayout from '@/components/AppLayout.vue'
import { useThemeSync } from '@/composables/useThemeSync'
import { bindAppToast } from '@/composables/useAppToast'
import { useAppStore } from '@/stores/app'

const route = useRoute()
const store = useAppStore()

useThemeSync()

// DS 模块四：把 PrimeVue 的 toast 实例绑定到全局单例，
// 让 composables / api 层（没有 setup 上下文的地方）也能统一发提示。
// 必须在 setup 同步调用 useToast()，故放在顶层而不是 onMounted。
bindAppToast(useToast() as never)

// 偏好数据由 app store 的 watch(loggedIn) 在登录成功后自动拉取；此处兜底调用幂等安全
onMounted(() => {
  store.loadPreferences()
})
</script>

<template>
  <!-- DS 模块四：Toast 宿主统一走 AppToast（渲染口径收口在组件内） -->
  <AppToast />
  <AppLayout v-if="route.path !== '/login'">
    <router-view v-slot="{ Component, route: routeParam }">
      <!-- 页面切换过渡统一走 .page 类（定义在本文件 style，全站唯一一份）。
           2026-11-25 修复：包一层单根 `.page-host` 再交给 <Transition>。
           原因：多数页面模板是**多根节点 fragment**（如公告列表 = header + v-if 列表 + v-else 空态），
           <Transition> 对 fragment 根无法执行 leave 回调（Vue 警告 "renders non-element root node
           that cannot be animated"），`mode="out-in"` 下新页面永远等不到入场 → 点击进入详情后
           内容空白、必须刷新浏览器（生产实测复现）。 -->
      <Transition name="page" mode="out-in">
        <div :key="routeParam.path" class="page-host">
          <component :is="Component" />
        </div>
      </Transition>
    </router-view>
  </AppLayout>
  <router-view v-else v-slot="{ Component, route: routeParam }">
    <Transition name="page" mode="out-in">
      <div :key="routeParam.path" class="page-host">
        <component :is="Component" />
      </div>
    </Transition>
  </router-view>
</template>

<style>
/* ═══ 全站页面切换过渡（唯一真相）═══
   规则来源：docs/reference/ui-system.md §14.3
   - 进入 150ms、离开 100ms（离开更快，减少"卡住"感）
   - 位移 8px → 0（进入）/ 0 → -4px（离开），幅度小，避免页面大幅晃动
   - 统一使用 `mode="out-in"`，保证同一时刻只有一个页面在动（默认并行会让两页重叠）
   任何页面不得再自写 page 过渡；需要特殊过渡的走 <Transition name="..."> 并在规范登记。 */
/* 过渡宿主：Transition 需要**单根元素**才能可靠执行 leave/enter 回调（fragment 根会挂起 out-in）。
   这里用 block 包裹层承载过渡，内部页面各根节点照旧；宽度/高度不引入额外约束。 */
.page-host {
  display: block;
}

.page-enter-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.page-leave-active {
  transition: opacity 0.1s ease, transform 0.1s ease;
}
.page-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.page-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* 尊重「减少动效」偏好：直接跳过过渡，不做位移 */
@media (prefers-reduced-motion: reduce) {
  .page-enter-active,
  .page-leave-active {
    transition: none;
  }
  .page-enter-from,
  .page-leave-to {
    opacity: 1;
    transform: none;
  }
}
</style>
