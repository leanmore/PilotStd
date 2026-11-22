<script setup lang="ts">
defineOptions({ name: 'StandardTable' })
import { useI18n } from 'vue-i18n'
import AppTable from '@/components/ui/AppTable.vue'

const { t } = useI18n()

defineProps<{ data: Record<string, unknown>[] }>()
</script>
<template>
  <AppTable :value="data" paginator :rows="20" stripedRows size="small">
    <Column field="standard_number" :header="t('standard_table.col_standard_number')" />
    <Column field="standard_name" :header="t('standard_table.col_name')" />
    <Column field="status" :header="t('standard_table.col_status')" />
    <Column field="source_site" :header="t('standard_table.col_source')" />
  </AppTable>
</template>
