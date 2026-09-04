/**
 * Типы и константы контентной модели — без обращений к файловой системе.
 *
 * Вынесены отдельно, чтобы клиентские компоненты могли импортировать подписи
 * статусов и площадок, не утаскивая в браузерный бандл `node:fs` из content.ts.
 */

export const STATUSES = [
  'idea',
  'draft',
  'review',
  'ready',
  'scheduled',
  'published',
  'parked',
  'rejected',
] as const

export type Status = (typeof STATUSES)[number]

/** Статусы, которые ведут материал к публикации — в таком порядке они идут на канбане. */
export const PIPELINE_STATUSES: Status[] = [
  'idea',
  'draft',
  'review',
  'ready',
  'scheduled',
  'published',
]

export const STATUS_LABELS: Record<Status, string> = {
  idea: 'Идея',
  draft: 'Черновик',
  review: 'На проверке',
  ready: 'Готово к публикации',
  scheduled: 'Запланировано',
  published: 'Опубликовано',
  parked: 'Отложено',
  rejected: 'Отклонено',
}

export const PLATFORMS = [
  'telegram',
  'threads',
  'x',
  'facebook',
  'instagram',
  'linkedin',
  'youtube',
  'essay',
] as const
export type Platform = (typeof PLATFORMS)[number]

export const PLATFORM_LABELS: Record<Platform, string> = {
  telegram: 'Telegram',
  threads: 'Threads',
  x: 'X',
  facebook: 'Facebook',
  instagram: 'Instagram',
  linkedin: 'LinkedIn',
  youtube: 'YouTube',
  essay: 'Лонгрид',
}

/**
 * Потолок площадки в знаках — чтобы карточка слота сразу говорила «влезает или нет».
 *
 * Числа официальные: Threads 500, X 280 без подписки, Telegram 4096 на сообщение,
 * LinkedIn 3000, подпись Instagram 2200. У лонгрида и сценария для YouTube потолка
 * нет — там ограничение не в знаках.
 */
export const PLATFORM_LIMITS: Partial<Record<Platform, number>> = {
  telegram: 4096,
  threads: 500,
  x: 280,
  linkedin: 3000,
  instagram: 2200,
}

export function isPlatform(value: unknown): value is Platform {
  return typeof value === 'string' && (PLATFORMS as readonly string[]).includes(value)
}

export const SOURCES = ['text', 'transcript', 'bot', 'link'] as const
export type Source = (typeof SOURCES)[number]

export const SOURCE_LABELS: Record<Source, string> = {
  text: 'Текст',
  transcript: 'Транскрипт',
  bot: 'Из бота',
  link: 'Ссылка',
}

export interface Material {
  /** `master` — исходная версия, остальное — адаптации под площадку. */
  name: string
  platform: Platform | 'master'
  kind: 'draft' | 'published'
  relPath: string
  updated?: string
  url?: string
  from?: string
  chars: number
}

export interface Idea {
  id: string
  title: string
  status: Status
  created: string
  source: Source
  tags: string[]
  dir: string
  relDir: string
  hasSource: boolean
  drafts: Material[]
  published: Material[]
}

export function isStatus(value: unknown): value is Status {
  return typeof value === 'string' && (STATUSES as readonly string[]).includes(value)
}

export function isSource(value: unknown): value is Source {
  return typeof value === 'string' && (SOURCES as readonly string[]).includes(value)
}

/** Подпись материала: мастер-версия или площадка. */
export function materialLabel(name: string): string {
  if (name === 'master') return 'Мастер-версия'
  return PLATFORM_LABELS[name as Platform] ?? name
}
