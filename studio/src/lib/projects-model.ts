/**
 * Типы раздела «Проекты» без `node:fs` — их импортируют компоненты, а любой
 * импорт файловой системы в клиентский бандл роняет сборку.
 *
 * Проект — это тема наблюдения за Telegram: какие чаты смотрим, что считаем
 * находкой и что срочным. Описание живёт в git, сами находки — вне его.
 */

export type ProjectStatus = 'active' | 'paused' | 'proposed'

export const PROJECT_STATUS_LABELS: Record<ProjectStatus, string> = {
  active: 'следим',
  paused: 'на паузе',
  proposed: 'ждёт данных',
}

export function isProjectStatus(value: unknown): value is ProjectStatus {
  return value === 'active' || value === 'paused' || value === 'proposed'
}

export interface Project {
  id: string
  title: string
  status: ProjectStatus
  /** Сколько чатов входит в тему. */
  chatCount: number
  /** За чем следим. */
  watch: string
  /** Что считается срочным. */
  urgent: string
  since: string
  body: string
  relPath: string
}

export interface ProjectDayMeta {
  /** Дата в виде `ГГГГ-ММ-ДД` — она же адрес страницы. */
  date: string
  projectId: string
  title: string
  summary: string
  findings: number
  urgent: number
}
