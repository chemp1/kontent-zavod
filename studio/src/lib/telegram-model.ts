/**
 * Типы раздела «Telegram» без `node:fs` — их импортируют компоненты, а любой
 * импорт файловой системы в клиентский бандл роняет сборку.
 *
 * Раздел показывает две разные вещи: правила (что мы обещали делать с личным
 * Telegram) и сводки (что по этим правилам реально произошло за сутки).
 */

export type RuleStatus = 'active' | 'paused' | 'proposed'

export const RULE_STATUS_LABELS: Record<RuleStatus, string> = {
  active: 'работает',
  paused: 'на паузе',
  proposed: 'предложено',
}

export function isRuleStatus(value: unknown): value is RuleStatus {
  return value === 'active' || value === 'paused' || value === 'proposed'
}

export interface Rule {
  id: string
  title: string
  status: RuleStatus
  /** К чему правило применяется: «диалоги в архиве», «чаты с непрочитанным дольше недели». */
  scope: string
  /** Что именно делается. */
  action: string
  /** С какого дня правило живёт. */
  since: string
  body: string
  relPath: string
}

export interface DigestMeta {
  /** Дата в виде `ГГГГ-ММ-ДД` — она же адрес страницы. */
  date: string
  title: string
  summary: string
  chats: number
  messages: number
  marked: number
  failed: number
}
