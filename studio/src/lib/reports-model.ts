/**
 * Типы отчётов без `node:fs` — их импортируют компоненты графиков, а любой
 * импорт файловой системы в клиентский бандл роняет сборку.
 *
 * Форм всего четыре, и каждая отвечает за свою работу данных:
 * величина, сравнение двух групп, доли целого и просто число.
 * Пятую форму заводить только тогда, когда появится работа, которую ни одна
 * из этих не делает.
 */

/** Просто числа. Одно число — это не график, это плитка. */
export interface KpiBlock {
  type: 'kpi'
  title?: string
  items: { label: string; value: string; note?: string }[]
}

/** Сравнение величин по подписанным категориям. Один ряд, один цвет. */
export interface BarsBlock {
  type: 'bars'
  title: string
  hint?: string
  sample?: number
  unit?: string
  items: { label: string; value: number; note?: string }[]
}

/** Две группы по одним и тем же признакам: видно разрыв, а не два частокола. */
export interface DumbbellBlock {
  type: 'dumbbell'
  title: string
  hint?: string
  sample?: number
  unit?: string
  legend: { a: string; b: string }
  items: { label: string; a: number; b: number }[]
}

/** Доли целого. Больше шести сегментов не бывает: дальше читается только таблица. */
export interface StackBlock {
  type: 'stack'
  title: string
  hint?: string
  sample?: number
  items: { label: string; value: number }[]
}

export type Block = KpiBlock | BarsBlock | DumbbellBlock | StackBlock

export interface ReportMeta {
  slug: string
  title: string
  date: string
  summary: string
  tags: string[]
}

export interface Report extends ReportMeta {
  body: string
  blocks: Block[]
  relPath: string
}
