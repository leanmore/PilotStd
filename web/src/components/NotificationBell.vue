<script setup lang="ts">
defineOptions({ name: 'NotificationBell' })
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import Popover from 'primevue/popover'
import Divider from 'primevue/divider'
import { useNotification } from '@/composables/useNotification'

const router = useRouter()
const { messages, unreadCount, markAsRead } = useNotification()
const popoverRef = ref<InstanceType<typeof Popover> | null>(null)

const recentMessages = computed(() => messages.value.slice(0, 10))

const formatTime = (isoString: string) => {
  const date = new Date(isoString)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return Math.floor(diff / 60000) + '分钟前'
  if (diff < 86400000) return Math.floor(diff / 3600000) + '小时前'
  return date.toLocaleDateString()
}

const togglePopover = (event: Event) => {
  popoverRef.value?.toggle(event)
}

const handleItemClick = async (msg: { id: number; is_read?: boolean; link_url?: string }) => {
  if (!msg.is_read) {
    await markAsRead(msg.id)
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
      :icon="unreadCount > 0 ? 'pi pi-bell' : 'pi pi-bell'"
      :severity="unreadCount > 0 ? 'primary' : 'secondary'"
      text
      rounded
      :badge="unreadCount > 0 ? String(unreadCount) : undefined"
      badge-severity="danger"
      @click="togglePopover"
      aria-label="通知"
    />

    <Popover ref="popoverRef" class="notification-popover">
      <div class="notification-dropdown">
        <div class="dropdown-header">
          <span class="header-title">通知</span>
          <Button
            v-if="unreadCount > 0"
            text
            size="small"
            label="全部标记已读"
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
              <div class="item-body">{{ msg.body }}</div>
              <div class="item-time">{{ formatTime(msg.sent_at) }}</div>
            </div>
          </div>
          <div v-if="recentMessages.length === 0" class="empty-state">
            暂无通知
          </div>
        </div>
        <Divider class="footer-divider" />
        <div class="dropdown-footer">
          <Button text size="small" label="查看全部通知 →" @click="goToLogs" />
        </div>
      </div>
    </Popover>
  </div>
</template>

<style scoped>
.notification-bell {
  display: inline-flex;
  align-items: center;
}

.notification-dropdown {
  display: flex;
  flex-direction: column;
  background: var(--surface-card, #fff);
  border-radius: 8px;
  min-width: 320px;
  max-width: 400px;
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
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
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
