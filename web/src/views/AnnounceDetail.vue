<script setup lang="ts">
defineOptions({ name: 'AnnounceDetail' })
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import Card from 'primevue/card'
import Tag from 'primevue/tag'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import InputText from 'primevue/inputtext'
import ProgressSpinner from 'primevue/progressspinner'
import AppCalendar from '@/components/AppCalendar.vue'
import TableLoadFooter from '@/components/TableLoadFooter.vue'
import FavoriteStatusTag from '@/components/FavoriteStatusTag.vue'
import { useAnnounceDetail } from '@/composables/useAnnounceDetail'

const route = useRoute()
// 模板 ref 必须声明在组件内（ref="sentinel" 是字符串属性，TS 不识别为使用）
const sentinel = ref<HTMLElement | null>(null)
// 页面标识从路由取；取数与流程编排全部在 composable 内（见 useAnnounceDetail.ts）
const {
  loading,
  parsing,
  announcement,
  records,
  selectedRecords,
  usePaginated,
  parseStatusLabel,
  parseStatusSeverity,
  parseButtonLabel,
  parseButtonDisabled,
  sanitizedContent,
  startParse,
  statusLabel,
  statusSeverity,
  onCellEditComplete,
  handleBatchApprove,
  displayRecords,
  isLoadingMore,
  showLoadAllButton,
  loadAllRemaining,
  totalCount,
  favMap,
  favStatusMap,
  isFavLoading,
  toggleFavorite,
} = useAnnounceDetail(
  route.params.announceNo as string,
  route.params.source as string,
  sentinel,
)
</script>

<template>
  <div class="announce-detail">
    <div v-if="loading" class="flex justify-content-center align-items-center" style="min-height: 400px">
      <ProgressSpinner />
    </div>

    <div v-else>
      <!-- 公告头 -->
      <Card class="mb-4">
        <template #title>
          <div class="flex justify-content-between align-items-center">
            <span class="flex-1 text-center truncate px-2 text-xl font-semibold" style="color:var(--text-heading)">{{ announcement?.announce_no }}</span>
            <Tag :value="parseStatusLabel" :severity="parseStatusSeverity" />
            <Button
              icon="pi pi-undo"
              aria-label="返回列表"
              class="p-button-text p-button-rounded ml-3"
              @click="$router.back()"
            />
          </div>
        </template>
        <template #content>
          <div class="grid">
            <div class="col-12">
              <label class="text-sm text-color-secondary">标题</label>
              <p class="announce-title">{{ announcement?.title }}</p>
            </div>
            <div class="col-6">
              <label class="text-sm text-color-secondary">发布日期</label>
              <p>{{ announcement?.publish_date || '-' }}</p>
            </div>
            <div class="col-6">
              <label class="text-sm text-color-secondary">来源</label>
              <p>
                <a
                  v-if="announcement?.source_url"
                  :href="announcement.source_url"
                  target="_blank"
                  class="text-primary hover:underline"
                >{{ announcement.site_name || announcement.source_url }}</a>
                <span v-else>{{ announcement?.source_type || announcement?.site_name || '未知来源' }}</span>
              </p>
            </div>
            <div class="col-12">
              <label class="text-sm text-color-secondary">附件</label>
              <div class="attachment-area mt-1">
                <span v-if="announcement?.attachment_url" class="text-sm">
                  {{ announcement.attachment_url.split('/').pop() }}
                </span>
                <span v-else class="text-sm text-color-secondary">无附件</span>
                <Button
                  v-if="announcement?.attachment_url"
                  :label="parseButtonLabel"
                  icon="pi pi-refresh"
                  size="small"
                  :loading="parsing"
                  :disabled="parseButtonDisabled"
                  @click="startParse"
                />
              </div>
            </div>
            <!-- 公告正文 -->
            <div v-if="announcement?.content" class="col-12">
              <label class="text-sm text-color-secondary">公告正文</label>
              <div class="official-doc mt-1 p-3 border-round">
                <div class="doc-content" v-html="sanitizedContent" />
              </div>
            </div>
          </div>
        </template>
      </Card>

      <!-- 标准清单表格 -->
      <Card>
        <template #title>
          <div class="flex justify-content-between align-items-center">
            <span>标准清单（{{ records.length }} 条）</span>
            <Button
              label="批量确认入库"
              icon="pi pi-check"
              severity="success"
              size="small"
              :disabled="selectedRecords.length === 0"
              @click="handleBatchApprove"
            />
          </div>
        </template>
        <template #content>
          <DataTable
            v-model:selection="selectedRecords"
            :value="displayRecords"
            editMode="cell"
            dataKey="id"
            stripedRows
            size="small"
            @cell-edit-complete="onCellEditComplete"
          >
            <Column selectionMode="multiple" headerStyle="width: 3rem" />
            <Column field="row_index" header="#" style="width: 4rem">
              <template #body="slotProps">
                {{ String(slotProps.data.row_index).padStart(2, '0') }}
              </template>
            </Column>
            <Column field="standard_number" header="标准号" style="min-width: 12rem">
              <template #editor="{ data, field }">
                <InputText v-model="data[field]" class="w-full" />
              </template>
              <template #body="{ data }">
                <span :class="{ 'text-red-500': !data.standard_number }">
                  {{ data.standard_number || '(待补全)' }}
                </span>
              </template>
            </Column>
            <Column field="std_name" header="标准名称" style="min-width: 18rem">
              <template #editor="{ data, field }">
                <InputText v-model="data[field]" class="w-full" />
              </template>
              <template #body="{ data }">
                <span :class="{ 'text-red-500': !data.std_name }">
                  {{ data.std_name || '(待补全)' }}
                </span>
              </template>
            </Column>
            <Column field="publish_date" header="发布日期" style="min-width: 10rem">
              <template #editor="{ data, field }">
                <AppCalendar v-model="data[field]" dateFormat="yy-mm-dd" showIcon />
              </template>
              <template #body="{ data }">
                {{ data.publish_date || '-' }}
              </template>
            </Column>
            <Column field="implement_date" header="实施日期" style="width: 10rem">
              <template #editor="{ data, field }">
                <AppCalendar v-model="data[field]" dateFormat="yy-mm-dd" showIcon />
              </template>
              <template #body="{ data }">
                {{ data.implement_date || '-' }}
              </template>
            </Column>
            <Column field="expiry_date" header="作废日期" style="width: 10rem">
              <template #editor="{ data, field }">
                <AppCalendar v-model="data[field]" dateFormat="yy-mm-dd" showIcon />
              </template>
              <template #body="{ data }">
                {{ data.expiry_date || '-' }}
              </template>
            </Column>
            <Column field="superseded_by" header="代替标准" style="min-width: 10rem">
              <template #editor="{ data, field }">
                <InputText v-model="data[field]" class="w-full" />
              </template>
              <template #body="{ data }">
                {{ data.superseded_by || '-' }}
              </template>
            </Column>
            <Column field="status" header="状态" style="width: 8rem">
              <template #body="{ data }">
                <Tag :value="statusLabel(data.status)" :severity="statusSeverity(data.status)" />
              </template>
            </Column>
            <Column header="收藏" style="width: 9rem">
              <template #body="{ data }">
                <div class="fav-cell">
                  <Button
                    :icon="favMap[data.id] ? 'pi pi-star-fill' : 'pi pi-star'"
                    :loading="isFavLoading(data.id)"
                    rounded text size="small"
                    :severity="favMap[data.id] ? 'warn' : 'secondary'"
                    @click.stop="toggleFavorite(data)"
                  />
                  <!-- 收藏对象存在才渲染下载状态标签（不存在则不渲染，星标保持空心） -->
                  <FavoriteStatusTag :status="favStatusMap[data.id]" />
                </div>
              </template>
            </Column>
          </DataTable>

          <TableLoadFooter
            :displayed="displayRecords.length"
            :total="usePaginated ? totalCount : records.length"
            :is-loading="isLoadingMore"
            :show-load-all-button="showLoadAllButton"
            @load-all="loadAllRemaining"
          />
          <!-- 滚动加载哨兵：进入视口前 100px 触发下一批加载（方案 C，不占视觉空间） -->
          <div ref="sentinel" class="scroll-sentinel" style="height: 1px; opacity: 0;" aria-hidden="true" />
        </template>
      </Card>
    </div>
  </div>
</template>

<style scoped>
.announce-detail {
  max-width: 1400px;
  margin: 0 auto;
  padding: 1rem;
  background: var(--bg);
  min-height: 100vh;
}

.p-button-text.p-button-rounded:focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
}

/* fix(a11y): 标题/公告号强制 --text-heading，阻断 Aura 亮色 token 继承（深色主题 1.8:1→≥8:1）。标题居中 — :deep() 穿透 Card，提高特异性对抗 Aura 的 .p-card-content p */
:deep(.p-card-content) .announce-title {
  font-size: 22px;
  font-weight: bold;
  text-align: center;
  line-height: 1.8;
  margin: 0.5rem 0; color: var(--text-heading);
}

.official-doc {
  max-width: 800px;
  margin: 0 auto;
  background: var(--surface);
}

/* 正文通用容器 — 两端对齐 + 舒适行距，作为无特定 class 段落的回退 */
.doc-content {
  color: var(--text);
  text-align: justify;
  line-height: 1.8;
}

/* 通用段落缩进 — 作用于正文区所有段落，优先级低于特定 class */
.doc-content :where(p, section > p, div > p) {
  text-indent: 2em;
  margin: 0.5em 0;
}

/* v-html 注入内容的标题居中 — 仅作用于 official-doc 容器内 */
:deep(.official-doc .announce-heading) {
  text-align: center;
  font-weight: 700;
  text-indent: 0;
  margin-bottom: 0.5em;
}

/* 正文段落 — 两端对齐、首行缩进 */
.doc-content :deep(.announce-body) {
  font-size: 16px;
  color: var(--text);
  text-indent: 2em;
  text-align: justify;
  line-height: 1.8;
  margin: 0.25em 0;
}

/* 落款机关 — 右对齐、无缩进 */
.doc-content :deep(.announce-signature) {
  font-size: 16px;
  color: var(--text);
  text-align: right;
  text-indent: 0;
  line-height: 1.8;
  margin: 0.25em 0;
}

/* 落款日期 — 右对齐、无缩进 */
.doc-content :deep(.announce-date) {
  font-size: 16px;
  color: var(--text);
  text-align: right;
  text-indent: 0;
  line-height: 1.8;
  margin: 0.25em 0;
}

.doc-content :deep(table) {
  border-collapse: collapse;
  width: 100%;
}

.doc-content :deep(td),
.doc-content :deep(th) {
  border: 1px solid var(--border);
  padding: 0.25rem 0.5rem;
}

.attachment-area {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

/* 收藏单元格：星标 + 下载状态标签（标签仅在收藏对象存在时渲染） */
.fav-cell {
  display: flex;
  align-items: center;
  gap: 0.375rem;
}
</style>
