<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getApiKeys, createApiKey, updateApiKey, revokeApiKey, reactivateApiKey } from '@/api/apiKeys'
import type { ApiKey } from '@/api/apiKeys'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import Tag from 'primevue/tag'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'

// ── 列表 ──
const keys = ref<ApiKey[]>([])
const loadErr = ref('')
async function load() {
  try { const r = await getApiKeys(); keys.value = r.api_keys; loadErr.value = '' }
  catch (e: any) { loadErr.value = e.response?.data?.detail || '加载失败' }
}

// ── 创建 ──
const showCreate = ref(false)
const createForm = ref({ key_id: '', description: '', scopes: 'query:read', expires_at: '' })
const createErr = ref('')
const createdKey = ref('')
async function doCreate() {
  createErr.value = ''
  if (!createForm.value.key_id) { createErr.value = '请输入 Key ID'; return }
  try {
    const r = await createApiKey({
      key_id: createForm.value.key_id,
      description: createForm.value.description,
      scopes: createForm.value.scopes.split(',').map(s => s.trim()).filter(Boolean),
      expires_at: createForm.value.expires_at,
    })
    createdKey.value = r.raw_key
  } catch (e: any) { createErr.value = e.response?.data?.detail || '创建失败'; return }
}
function onCreatedOk() {
  createdKey.value = ''
  createForm.value = { key_id: '', description: '', scopes: 'query:read', expires_at: '' }
  showCreate.value = false
  load()
}

// ── 编辑 ──
const showEdit = ref(false)
const editKeyId = ref('')
const editForm = ref({ description: '', scopes: '', expires_at: '' })
const editErr = ref('')
function openEdit(k: ApiKey) {
  editKeyId.value = k.key_id
  editForm.value = {
    description: k.description,
    scopes: (k.scopes || []).join(', '),
    expires_at: k.expires_at || '',
  }
  editErr.value = ''
  showEdit.value = true
}
async function doEdit() {
  try {
    await updateApiKey(editKeyId.value, {
      description: editForm.value.description,
      scopes: editForm.value.scopes.split(',').map(s => s.trim()).filter(Boolean),
      expires_at: editForm.value.expires_at || '',
    })
    showEdit.value = false
    load()
  } catch (e: any) { editErr.value = e.response?.data?.detail || '更新失败' }
}

// ── 吊销 / 重新激活 ──
async function doRevoke(k: ApiKey) {
  if (!confirm(`确认吊销 Key "${k.key_id}"？吊销后该 Key 将无法使用。`)) return
  await revokeApiKey(k.key_id)
  load()
}
async function doReactivate(k: ApiKey) {
  await reactivateApiKey(k.key_id)
  load()
}

onMounted(load)
</script>

<template>
  <div>
    <div class="flex-between mb-3">
      <h2 class="page-title">API Key 管理</h2>
      <Button label="创建 API Key" icon="pi pi-plus" @click="showCreate = true" />
    </div>

    <p v-if="loadErr" class="err-msg">{{ loadErr }}</p>

    <!-- ═══ 列表 ═══ -->
    <DataTable :value="keys" stripedRows size="small" v-if="keys.length">
      <Column field="key_id" header="Key ID" />
      <Column field="description" header="描述" />
      <Column header="Scopes">
        <template #body="{ data }">
          <Tag v-for="s in data.scopes" :key="s" :value="s" severity="info" class="mr-1" />
        </template>
      </Column>
      <Column field="created_at" header="创建时间" />
      <Column header="状态">
        <template #body="{ data }">
          <Tag :value="data.is_active ? '活跃' : '已吊销'" :severity="data.is_active ? 'success' : 'danger'" />
        </template>
      </Column>
      <Column field="last_used_at" header="最后使用" />
      <Column header="操作">
        <template #body="{ data }">
          <div style="display:flex;gap:4px">
            <Button label="编辑" size="small" text @click="openEdit(data)" />
            <Button
              v-if="data.is_active"
              label="吊销" size="small" text severity="danger"
              @click="doRevoke(data)"
            />
            <Button
              v-else
              label="重新激活" size="small" text severity="success"
              @click="doReactivate(data)"
            />
          </div>
        </template>
      </Column>
    </DataTable>
    <p v-else-if="!loadErr" class="text-dim mt-3">暂无 API Key，点击上方按钮创建。</p>

    <!-- ═══ 创建弹窗 ═══ -->
    <Dialog v-model:visible="showCreate" header="创建 API Key" :modal="true" :style="{ width: '420px' }">
      <template v-if="!createdKey">
        <div class="form-col">
          <label class="label">Key ID</label>
          <input v-model="createForm.key_id" class="fi" placeholder="default" />
          <label class="label">描述</label>
          <input v-model="createForm.description" class="fi" placeholder="可选描述" />
          <label class="label">Scopes（逗号分隔）</label>
          <input v-model="createForm.scopes" class="fi" placeholder="query:read" />
          <label class="label">过期时间</label>
          <input v-model="createForm.expires_at" class="fi" placeholder="YYYY-MM-DD，留空不过期" />
        </div>
        <p v-if="createErr" class="err-msg">{{ createErr }}</p>
        <div class="flex-between mt-3">
          <Button label="取消" severity="secondary" @click="showCreate = false" />
          <Button label="生成 Key" @click="doCreate" />
        </div>
      </template>
      <template v-else>
        <div class="raw-key-box">
          <p class="text-dim">API Key 已生成。<strong>以下内容仅显示一次，请立即复制保存。</strong></p>
          <pre class="raw-key">{{ createdKey }}</pre>
        </div>
        <div class="flex-between mt-3">
          <Button label="我已复制，关闭" @click="onCreatedOk" />
        </div>
      </template>
    </Dialog>

    <!-- ═══ 编辑弹窗 ═══ -->
    <Dialog v-model:visible="showEdit" header="编辑 API Key" :modal="true" :style="{ width: '420px' }">
      <div class="form-col">
        <label class="label">描述</label>
        <input v-model="editForm.description" class="fi" />
        <label class="label">Scopes（逗号分隔）</label>
        <input v-model="editForm.scopes" class="fi" placeholder="query:read" />
        <label class="label">过期时间</label>
        <input v-model="editForm.expires_at" class="fi" placeholder="YYYY-MM-DD，留空不过期" />
      </div>
      <p v-if="editErr" class="err-msg">{{ editErr }}</p>
      <div class="flex-between mt-3">
        <Button label="取消" severity="secondary" @click="showEdit = false" />
        <Button label="保存" @click="doEdit" />
      </div>
    </Dialog>
  </div>
</template>

<style scoped>
.page-title { font-size: 18px; font-weight: 600; margin: 0; }
.flex-between { display: flex; align-items: center; justify-content: space-between; }
.form-col { display: flex; flex-direction: column; gap: 6px; }
.label { font-size: 12px; color: var(--text-dim); }
.fi { padding: 8px 10px; border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--surface); color: var(--text); font-size: 13px; }
.raw-key-box { background: var(--primary-bg); padding: 16px; border-radius: var(--radius); }
.raw-key { font-family: monospace; font-size: 12px; word-break: break-all; color: var(--primary); margin: 8px 0 0; white-space: pre-wrap; }
.mt-3 { margin-top: 12px; }
.mr-1 { margin-right: 4px; }
.text-dim { color: var(--text-dim); font-size: 13px; }
.err-msg { color: var(--danger); font-size: 12px; margin: 8px 0 0; }
</style>
