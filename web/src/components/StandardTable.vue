<script setup lang="ts">
defineOptions({ name: 'StandardTable' })
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps<{ data: Record<string, unknown>[] }>()
</script>
<template>
  <DataTable :value="data" paginator :rows="20" stripedRows size="small">
    <Column field="standard_number" :header="t('standard_table.col_standard_number')" />
    <Column field="standard_name" :header="t('standard_table.col_name')" />
    <Column field="status" :header="t('standard_table.col_status')" />
    <Column field="source_site" :header="t('standard_table.col_source')" />
  </DataTable>
</template>
