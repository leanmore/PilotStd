export default {
  '*.{ts,vue}': ['bash scripts/check-primevue-icons.sh', () => 'npx vue-tsc -p tsconfig.app.json --noEmit'],
}
