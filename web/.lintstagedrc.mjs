export default {
  '*.{ts,vue}': () => 'npx vue-tsc -p tsconfig.app.json --noEmit',
}
