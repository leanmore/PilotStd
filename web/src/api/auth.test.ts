// auth.test.ts — 认证 / 用户管理 API 组装逻辑（NEW-44）
//
// 只验证本模块自己的契约：
//   - 每个函数落到哪个 HTTP 方法 / URL；
//   - 请求体形状（表单编码 vs JSON，camelCase → 后端 snake_case 的映射）；
//   - 返回值只取响应体 `.data`（不把 AxiosResponse 泄漏给调用方）；
//   - 失败原样透传（不吞错、不返回假成功）。
// http 层（拦截器 / AbortController / 401）由 http.test.ts 覆盖，这里全部 mock 掉。
import { beforeEach, describe, expect, it, vi } from 'vitest'

const h = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
}))

vi.mock('./http', () => ({ default: h }))

import { addUser, changePassword, deleteUser, getUsers, login, register } from './auth'

describe('auth API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('login 走 POST /login，表单编码提交账号密码，返回 data', async () => {
    const payload = { ok: true, username: 'alice', role: 'admin', must_change_password: true }
    h.post.mockResolvedValueOnce({ data: payload })

    const result = await login('alice', 's3cret')

    expect(h.post).toHaveBeenCalledTimes(1)
    expect(h.post.mock.calls[0][0]).toBe('/login')
    const body = h.post.mock.calls[0][1] as URLSearchParams
    // 后端登录端点接受表单编码而非 JSON，形状不能漂移
    expect(body).toBeInstanceOf(URLSearchParams)
    expect(body.get('username')).toBe('alice')
    expect(body.get('password')).toBe('s3cret')
    // 只返回响应体，调用方拿不到 AxiosResponse 外层
    expect(result).toEqual(payload)
  })

  it('getUsers 透传 routeTag，可选参数缺省时为 undefined', async () => {
    h.get.mockResolvedValueOnce({ data: { users: [] } })
    await expect(getUsers()).resolves.toEqual({ users: [] })
    expect(h.get).toHaveBeenLastCalledWith('/users', { routeTag: undefined })

    const users = [{ id: 7, username: 'bob', role: 'user' }]
    h.get.mockResolvedValueOnce({ data: { users } })
    await expect(getUsers('/settings')).resolves.toEqual({ users })
    expect(h.get).toHaveBeenLastCalledWith('/users', { routeTag: '/settings' })
  })

  it('addUser 走 POST /users，JSON body 携带用户名/密码/角色', async () => {
    h.post.mockResolvedValueOnce({ data: { ok: true, username: 'bob', role: 'admin' } })

    const result = await addUser('bob', 'pw-123', 'admin')

    expect(h.post).toHaveBeenCalledWith('/users', { username: 'bob', password: 'pw-123', role: 'admin' })
    expect(result.ok).toBe(true)
  })

  it('deleteUser 走 DELETE /users/:id，数字插值进路径', async () => {
    h.delete.mockResolvedValueOnce({ data: { ok: true } })

    const result = await deleteUser(42)

    expect(h.delete).toHaveBeenCalledWith('/users/42')
    expect(result).toEqual({ ok: true })
  })

  it('changePassword 走 PUT /users/password，camelCase 映射为后端 snake_case', async () => {
    h.put.mockResolvedValueOnce({ data: { ok: true, message: 'done' } })

    const result = await changePassword('old-pw', 'new-pw')

    // 字段名是后端契约：写错则改密静默失败
    expect(h.put).toHaveBeenCalledWith('/users/password', {
      old_password: 'old-pw',
      new_password: 'new-pw',
    })
    expect(result.message).toBe('done')
  })

  it('register 走 POST /auth/register，表单编码提交注册信息', async () => {
    h.post.mockResolvedValueOnce({ data: { ok: true, username: 'carol' } })

    const result = await register('carol', 'pw-456')

    expect(h.post.mock.calls[0][0]).toBe('/auth/register')
    const body = h.post.mock.calls[0][1] as URLSearchParams
    expect(body).toBeInstanceOf(URLSearchParams)
    expect(body.get('username')).toBe('carol')
    expect(body.get('password')).toBe('pw-456')
    expect(result).toEqual({ ok: true, username: 'carol' })
  })

  it('请求失败时原样抛出（不吞错、不伪造成功）', async () => {
    const err = Object.assign(new Error('unauthorized'), { status: 401 })
    h.put.mockRejectedValueOnce(err)

    await expect(changePassword('a', 'b')).rejects.toBe(err)

    const getErr = new Error('network down')
    h.get.mockRejectedValueOnce(getErr)
    await expect(getUsers()).rejects.toBe(getErr)
  })
})
