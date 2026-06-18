// web/src/api/auth.ts — 认证与用户管理
import http from './http'
import type { UserListResponse, SuccessResponse } from '../types/api'

export const login = (username: string, password: string): Promise<SuccessResponse> =>
  http.post('/login', new URLSearchParams({ username, password })).then(r => r.data)

export const getUsers = (): Promise<UserListResponse> =>
  http.get('/users').then(r => r.data)

export const addUser = (username: string, password: string, role: string): Promise<SuccessResponse> =>
  http.post('/users', { username, password, role }).then(r => r.data)

export const deleteUser = (id: number): Promise<SuccessResponse> =>
  http.delete(`/users/${id}`).then(r => r.data)

export const changePassword = (oldPassword: string, newPassword: string): Promise<SuccessResponse> =>
  http.put('/users/password', { old_password: oldPassword, new_password: newPassword }).then(r => r.data)
