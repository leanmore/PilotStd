// api.test.ts — 总导出桶的兼容契约（NEW-44）
//
// `web/src/api.ts` 是历史遗留的“总导出桶”：业务代码大量使用 `import { login } from '@/api'`。
// 本文件锁住两件事：
//   1. 导出名清单固定 —— 少一个导出即造成全仓 import 报错（构建期才发现成本最高）；
//   2. 桶里导出的是**同一函数引用**（不是重新包一层的 wrapper），保证行为与源模块一致。
import { describe, expect, it } from 'vitest'

import * as api from './api'
import * as announce from './api/announce'
import * as auth from './api/auth'
import * as download from './api/download'
import * as files from './api/files'
import * as query from './api/query'
import * as settings from './api/settings'

/** 桶契约：新增/删除导出必须同步本清单（防止破坏既有 import 路径） */
const EXPECTED_EXPORTS = [
  'addUser',
  'changePassword',
  'deleteUser',
  'getAnnounceFetchFailures',
  'getAnnounceResults',
  'getFiles',
  'getLoginBackground',
  'getPendingItems',
  'getQueryResults',
  'getSettings',
  'getSettingsCached',
  'getSettingsMetadata',
  'getSettingsSchema',
  'getStats',
  'getToken',
  'getUsers',
  'login',
  'postAnnounceCheck',
  'postArchive',
  'postCleanEmpty',
  'postDownload',
  'postNormalize',
  'postQuery',
  'postRequery',
  'postScan',
  'putSettings',
  'refreshToken',
  'saveQueryResults',
  'uploadFile',
]

describe('api 总导出桶', () => {
  it('导出名清单与业务 import 契约一致', () => {
    expect(Object.keys(api).sort()).toEqual([...EXPECTED_EXPORTS].sort())
  })

  it('全部导出都是可直接调用的函数（不存在半成品常量/类型占位）', () => {
    for (const name of Object.keys(api)) {
      expect(typeof (api as Record<string, unknown>)[name], name).toBe('function')
    }
  })

  it('导出与源模块是同一引用（桶不重新包装，行为不会分叉）', () => {
    expect(api.login).toBe(auth.login)
    expect(api.changePassword).toBe(auth.changePassword)
    expect(api.postQuery).toBe(query.postQuery)
    expect(api.saveQueryResults).toBe(query.saveQueryResults)
    expect(api.getFiles).toBe(files.getFiles)
    expect(api.uploadFile).toBe(files.uploadFile)
    expect(api.getAnnounceResults).toBe(announce.getAnnounceResults)
    expect(api.postAnnounceCheck).toBe(announce.postAnnounceCheck)
    expect(api.getAnnounceFetchFailures).toBe(announce.getAnnounceFetchFailures)
    expect(api.getSettings).toBe(settings.getSettings)
    expect(api.getSettingsCached).toBe(settings.getSettingsCached)
    expect(api.getLoginBackground).toBe(settings.getLoginBackground)
    expect(api.postDownload).toBe(download.postDownload)
  })
})
