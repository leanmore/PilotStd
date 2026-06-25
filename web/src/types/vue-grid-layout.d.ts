// web/src/types/vue-grid-layout.d.ts — vue-grid-layout@3.0.0-beta1 类型声明
// 该包无内置 TS 声明，此处补充最小可用类型

declare module 'vue-grid-layout' {
  import type { DefineComponent } from 'vue'

  export interface LayoutItem {
    i: string
    x: number
    y: number
    w: number
    h: number
    minW?: number
    maxW?: number
    minH?: number
    maxH?: number
    static?: boolean
    moved?: boolean
    isDraggable?: boolean
    isResizable?: boolean
    isBounded?: boolean
  }

  export type Layout = LayoutItem[]

  export const GridLayout: DefineComponent<{
    layout?: Layout
    colNum?: number
    rowHeight?: number
    maxRows?: number
    margin?: [number, number]
    isDraggable?: boolean
    isResizable?: boolean
    isMirrored?: boolean
    useCssTransforms?: boolean
    verticalCompact?: boolean
    autoSize?: boolean
    responsive?: boolean
    breakpoints?: Record<string, number>
    cols?: Record<string, number>
    onLayoutUpdated?: (layout: Layout) => void
    onBreakpointChanged?: (breakpoint: string) => void
    [key: string]: unknown
  }>

  export const GridItem: DefineComponent<{
    i: string
    x: number
    y: number
    w: number
    h: number
    minW?: number
    maxW?: number
    minH?: number
    maxH?: number
    static?: boolean
    isDraggable?: boolean
    isResizable?: boolean
    isBounded?: boolean
    dragIgnoreFrom?: string
    dragAllowFrom?: string
    resizeIgnoreFrom?: string
    [key: string]: unknown
  }>
}
