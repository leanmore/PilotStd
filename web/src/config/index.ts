/** @see G-028: 唯一允许的 admin 字面量定义点 */
export const SUPERUSER_USERNAME: string =
  import.meta.env.VITE_SUPERUSER_ROLE || 'admin'
