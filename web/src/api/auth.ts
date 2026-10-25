// web/src/api/auth.ts — 认证与用户管理
import http from './http'
import type { RouteTag } from '../types/route-tag'
import type { UserListResponse, SuccessResponse } from '../types/api'

export const login = async (username: string, password: string): Promise<SuccessResponse> =>
  (await http.post('/login', new URLSearchParams({ username, password }))).data

export const getUsers = async (routeTag?: RouteTag): Promise<UserListResponse> =>
  (await http.get('/users', { routeTag })).data

export const addUser = async (username: string, password: string, role: string): Promise<SuccessResponse> =>
  (await http.post('/users', { username, password, role })).data

export const deleteUser = async (id: number): Promise<SuccessResponse> =>
  (await http.delete(`/users/${id}`)).data

export const changePassword = async (oldPassword: string, newPassword: string): Promise<SuccessResponse> =>
  (await http.put('/users/password', { old_password: oldPassword, new_password: newPassword })).data

export const register = async (username: string, password: string): Promise<SuccessResponse> =>
  (await http.post('/auth/register', new URLSearchParams({ username, password }))).data
