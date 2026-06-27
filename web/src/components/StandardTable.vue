<script setup lang="ts">
defineOptions({ name: 'StandardTable' })
defineProps<{ data: any[] }>()
</script>
<template>
  <DataTable :value="data" paginator :rows="20" stripedRows size="small">
    <Column field="standard_number" header="标准号" />
    <Column field="standard_name" header="名称" />
    <Column field="status" header="状态" />
    <Column field="source_site" header="来源" />
  </DataTable>
</template>
