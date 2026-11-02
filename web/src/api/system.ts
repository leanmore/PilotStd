// web/src/api/system.ts — 系统资源监控
import type { AxiosResponse } from 'axios'
import http from './http'
import type { RouteTag } from '../types/route-tag'

export interface SystemCpuInfo {
  percent: number
  count: number
}

export interface SystemMemoryInfo {
  total: number
  available: number
  percent: number
}

export interface SystemDiskInfo {
  total: number
  used: number
  free: number
  percent: number
}

export interface SystemResourcesResponse {
  cpu?: SystemCpuInfo
  memory?: SystemMemoryInfo
  disk?: SystemDiskInfo
  timestamp?: string
  error?: string
}

export interface SystemResourcesUnavailable {
  error: string
}

export function getSystemResources(
  options?: { routeTag?: RouteTag },
): Promise<AxiosResponse<SystemResourcesResponse>> {
  return http.get<SystemResourcesResponse>('/system/resources', options)
}
