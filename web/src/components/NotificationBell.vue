<script setup lang="ts">
defineOptions({ name: 'NotificationBell' })
// 文案全部走 i18n（notification.bell.*），不硬编码中文
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import Button from 'primevue/button'
import Popover from 'primevue/popover'
import Divider from 'primevue/divider'
import { useNotification } from '@/composables/useNotification'

const router = useRouter()
const { t } = useI18n()
const { messages, markAsRead } = useNotification()
const popoverRef = ref<InstanceType<typeof Popover> | null>(null)

// 同一事件会按启用渠道各写一条 notification_log；铃铛按“事件”展示，不展示渠道副本。
const eventKey = (m: { event_type: string; standard_number?: string | null; sent_at: string; title: string; body: string }) =>
  [m.event_type, m.standard_number || '', m.sent_at, m.title, m.body].join('|')

const recentMessages = computed(() => {
  const seen = new Set<string>()
  return messages.value
    .filter((m) => {
      const key = eventKey(m)
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
    .slice(0, 10)
})

// 角标也按事件去重，避免“两个渠道 = 两条未读”的虚高
const bellUnreadCount = computed(() => {
  const seen = new Set<string>()
  return messages.value.filter((m) => {
    if (m.is_read) return false
    const key = eventKey(m)
    if (seen.has(key)) return false
    seen.add(key)
    return true
  }).length
})

const formatTime = (isoString: string) => {
  const date = new Date(isoString)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  if (diff < 60000) return t('notification.bell.just_now')
  if (diff < 3600000) return t('notification.bell.minutes_ago', { n: Math.floor(diff / 60000) })
  if (diff < 86400000) return t('notification.bell.hours_ago', { n: Math.floor(diff / 3600000) })
  return date.toLocaleDateString()
}

const togglePopover = (event: Event) => {
  popoverRef.value?.toggle(event)
}

const handleItemClick = async (msg: { id?: number; is_read?: boolean; link_url?: string; event_type: string; standard_number?: string | null; sent_at: string; title: string; body: string }) => {
  if (!msg.is_read) {
    // 同一事件的其他渠道副本一并标记，否则刷新后仍会以未读副本出现
    const key = eventKey(msg)
    const siblings = messages.value.filter((m) => !m.is_read && eventKey(m) === key)
    await Promise.all(siblings.map((m) => markAsRead(m.id)))
  }
  router.push({
    path: '/notification-logs',
    query: { highlight: String(msg.id) },
  })
  popoverRef.value?.hide()
}

const markAllAsRead = async () => {
  await markAsRead()
}

const goToLogs = () => {
  router.push('/notification-logs')
  popoverRef.value?.hide()
}
</script>

<template>
  <div class="notification-bell">
    <Button
      :icon="bellUnreadCount > 0 ? 'pi pi-bell' : 'pi pi-bell'"
      :severity="bellUnreadCount > 0 ? 'primary' : 'secondary'"
      text
      rounded
      :badge="bellUnreadCount > 0 ? String(bellUnreadCount) : undefined"
      badge-severity="danger"
      @click="togglePopover"
      :aria-label="t('notification.bell.title')"
    />

    <Popover ref="popoverRef" class="notification-popover">
      <div class="notification-dropdown">
        <div class="dropdown-header">
          <span class="header-title">{{ t('notification.bell.title') }}</span>
          <Button
            v-show="bellUnreadCount > 0"
            text
            size="small"
            class="mark-all-button"
            :label="t('notification.bell.mark_all_read')"
            @click="markAllAsRead"
          />
        </div>
        <Divider class="header-divider" />
        <div class="dropdown-list">
          <div
            v-for="msg in recentMessages"
            :key="msg.id || msg.sent_at"
            class="notification-item"
            :class="{ unread: !msg.is_read, read: msg.is_read }"
            @click="handleItemClick(msg)"
          >
            <div v-if="!msg.is_read" class="item-dot"></div>
            <div class="item-content">
              <div class="item-title">{{ msg.title }}</div>
              <div class="item-body" :title="msg.body">{{ msg.body }}</div>
              <div class="item-time">{{ formatTime(msg.sent_at) }}</div>
            </div>
          </div>
          <div v-if="recentMessages.length === 0" class="empty-state">
            {{ t('notification.bell.empty') }}
          </div>
        </div>
        <Divider class="footer-divider" />
        <div class="dropdown-footer">
          <Button text size="small" :label="t('notification.bell.view_all')" @click="goToLogs" />
        </div>
      </div>
    </Popover>
  </div>
</template>

<style scoped>
.notification-bell {
  display: inline-flex;
  align-items: center;
  /* 固定锚点宽度：badge 从有到无时按钮不能变窄，否则 PrimeVue Popover 会向左重算 */
  width: 2.5rem;
  justify-content: center;
}

.notification-bell :deep(.p-button) {
  width: 2.5rem;
  min-width: 2.5rem;
  justify-content: center;
}

.notification-dropdown {
  display: flex;
  flex-direction: column;
  background: var(--surface-card, #fff);
  border-radius: 8px;
  /* 固定宽度：标记全部已读时按钮显隐不能改变弹层宽度，否则 PrimeVue 会重算位置并“跳”到左边 */
  width: 360px;
  max-width: min(400px, calc(100vw - 32px));
}

.dropdown-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
}

.header-title {
  font-weight: 600;
  font-size: 14px;
}

.header-divider,
.footer-divider {
  margin: 0;
}

.dropdown-list {
  flex: 1;
  overflow-y: auto;
  max-height: 320px;
}

.notification-item {
  display: flex;
  align-items: flex-start;
  padding: 10px 16px;
  cursor: pointer;
  border-bottom: 1px solid var(--surface-border, #eee);
  transition: background 0.2s;
}

.notification-item:hover {
  background: var(--surface-hover, #f0f7ff);
}

.notification-item.unread {
  background: var(--primary-50, #eff6ff);
}

.notification-item.read {
  opacity: 0.65;
}

.item-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--primary-color, #3b82f6);
  margin-right: 12px;
  margin-top: 6px;
  flex-shrink: 0;
}

.item-content {
  flex: 1;
  min-width: 0;
}

.item-title {
  font-weight: 500;
  font-size: 14px;
  color: var(--text-color, #333);
}

.item-body {
  font-size: 13px;
  color: var(--text-color-secondary, #666);
  margin-top: 2px;
  /* 标准号+名称较长：最多两行，悬停看完整正文 */
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  overflow-wrap: anywhere;
}

.item-time {
  font-size: 12px;
  color: var(--text-color-secondary, #999);
  margin-top: 4px;
}

.empty-state {
  padding: 40px 20px;
  text-align: center;
  color: var(--text-color-secondary, #999);
}

.dropdown-footer {
  padding: 8px 16px;
  text-align: center;
}
</style>
