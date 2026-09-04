/**
 * Типы ленты трендов без `node:fs` — их импортируют клиентские компоненты.
 *
 * Карточку кладёт внешний сборщик: что произошло, ссылка и два-три угла, под
 * которыми автор мог бы про это высказаться. Постов робот не пишет — это решение
 * от 29.08.2026: угол это приглашение подумать, готовый пост — конвейер слопа.
 */

export const TREND_STATUSES = ['new', 'used', 'skipped'] as const
export type TrendStatus = (typeof TREND_STATUSES)[number]

export const TREND_STATUS_LABELS: Record<TrendStatus, string> = {
  new: 'Новое',
  used: 'В работе',
  skipped: 'Мимо',
}

export type TrendKind = 'video' | 'article' | 'discussion'

export const TREND_KIND_LABELS: Record<TrendKind, string> = {
  video: 'видео',
  article: 'статья',
  discussion: 'обсуждение',
}

export interface Trend {
  slug: string
  title: string
  /** Id фида из `content/trends/sources.md`. */
  source: string
  sourceTitle: string
  kind: TrendKind
  url: string
  /** Когда вышло у источника. */
  published: string
  /** Когда попало к нам. */
  found: string
  status: TrendStatus
  ideaId: string
  body: string
  relPath: string
}

export function isTrendStatus(value: unknown): value is TrendStatus {
  return typeof value === 'string' && (TREND_STATUSES as readonly string[]).includes(value)
}
