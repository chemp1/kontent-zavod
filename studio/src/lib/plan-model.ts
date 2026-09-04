/**
 * Типы контент-плана без `node:fs` — их импортируют клиентские компоненты,
 * а импорт файловой системы в браузерный бандл роняет сборку.
 *
 * Главное решение раздела: слот хранит только план (когда, где, о чём),
 * а состояние выводится из привязанной идеи. Иначе два источника правды
 * разъедутся на первой же публикации.
 */

import type { Platform } from './content-model'

/** Дни недели в файле ритма — сокращениями, чтобы сетка читалась строкой. */
export const WEEKDAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'] as const
export type Weekday = (typeof WEEKDAYS)[number]

export const WEEKDAY_LABELS: Record<Weekday, string> = {
  mon: 'пн',
  tue: 'вт',
  wed: 'ср',
  thu: 'чт',
  fri: 'пт',
  sat: 'сб',
  sun: 'вс',
}

export type SlotState = 'empty' | 'needs-draft' | 'draft' | 'published'

export const SLOT_STATE_LABELS: Record<SlotState, string> = {
  empty: 'Пусто',
  'needs-draft': 'Нужен драфт',
  draft: 'Черновик',
  published: 'Опубликовано',
}

export interface Rubric {
  key: string
  label: string
  hint: string
}

/** Строка сетки ритма: «на Threads в 09:00 каждый день — тезис». */
export interface RhythmRow {
  platform: Platform
  time: string
  rubric: string
  days: Weekday[]
}

export interface Rhythm {
  rubrics: Rubric[]
  rows: RhythmRow[]
  body: string
  relPath: string
  /**
   * Файл лежит, а сетки из него не вышло. Почти всегда это незакавыченное
   * двоеточие в YAML: разбор падает целиком, и календарь молча остаётся пустым.
   * Молчать тут нельзя — иначе поломка выглядит как «ритм не задан».
   */
  broken: boolean
}

/** Слот как он лежит на диске. */
export interface Slot {
  id: string
  date: string
  time: string
  platform: Platform
  rubric: string
  ideaId: string
  /** Имя файла материала внутри идеи; пусто — берём одноимённый с площадкой. */
  material: string
  note: string
  relPath: string
}

/**
 * Слот, готовый к показу: план плюс всё, что удалось вывести из идеи.
 *
 * `ghost` — слот, которого на диске нет: его предлагает ритм. Заводится
 * по клику, до этого файла не существует.
 */
export interface PlannedSlot extends Omit<Slot, 'id' | 'relPath'> {
  id: string | null
  relPath: string | null
  ghost: boolean
  state: SlotState
  ideaTitle: string
  chars: number
  limit: number | null
  url: string
}

export interface DayPlan {
  date: string
  weekday: Weekday
  slots: PlannedSlot[]
}

/** Сколько слотов запланировано против того, сколько предлагает ритм. */
export interface PlatformLoad {
  platform: Platform
  planned: number
  rhythm: number
  ready: number
}

export interface WeekPlan {
  /** Понедельник недели, `ГГГГ-ММ-ДД`. */
  start: string
  previous: string
  next: string
  days: DayPlan[]
  load: PlatformLoad[]
  rubrics: Rubric[]
  rhythmBroken: boolean
}

export function isWeekday(value: unknown): value is Weekday {
  return typeof value === 'string' && (WEEKDAYS as readonly string[]).includes(value)
}

export function rubricLabel(rubrics: Rubric[], key: string): string {
  return rubrics.find((rubric) => rubric.key === key)?.label ?? key
}
