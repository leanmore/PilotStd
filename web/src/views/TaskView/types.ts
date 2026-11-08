// TaskView 及其子组件共享的类型定义（纯类型，无运行时代码）
export interface StepState {
  labelKey: string
  label?: string
  icon: string
  status: 'wait' | 'running' | 'done' | 'fail'
  summary: string
}

export interface TaskRecord {
  id: string
  time: string
  path: string
  scanCount: number
  queryFound: number
  dlSuccess: number
  normCount: number
  status: 'success' | 'partial' | 'fail' | 'stopped'
  steps: StepState[]
}
