/** @see G-028: 唯一允许的 admin 字面量定义点。此处仅允许 null 兜底，禁止任何字符串默认值 */
export const SUPERUSER_USERNAME: string | null =
  import.meta.env.VITE_SUPERUSER_USERNAME ?? null
