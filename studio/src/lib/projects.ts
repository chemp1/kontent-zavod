import fs from 'node:fs'
import path from 'node:path'

import { num, parseFile, str } from './frontmatter'
import { PROJECTS_ROOT, assertValidId, resolveInside, toRepoRelative } from './paths'
import type { Block } from './reports-model'
import { dataRoot } from './studio-config'
import type { Project, ProjectDayMeta, ProjectStatus } from './projects-model'
import { isProjectStatus } from './projects-model'

/**
 * Раздел собирается из двух источников, как и «Telegram»:
 *
 * - описания тем — `content/telegram/projects/<слаг>.md`, в git;
 * - находки — `<data.projectFindings>/<слаг>/<дата>.md` из `studio.json`, вне git, потому что это
 *   содержимое чужих чатов.
 */

export interface ProjectDay extends ProjectDayMeta {
  body: string
  blocks: Block[]
  relPath: string
}

function countList(data: Record<string, unknown>, key: string): number {
  const value = data[key]
  if (Array.isArray(value)) return value.length
  // Список чатов может прийти строкой «[1, 2, 3]», если YAML не разобрал.
  if (typeof value === 'string') {
    const inner = value.replace(/^\[|\]$/g, '').trim()
    return inner ? inner.split(',').length : 0
  }
  return 0
}

// ---------------------------------------------------------------- проекты

export function listProjects(): Project[] {
  if (!fs.existsSync(PROJECTS_ROOT)) return []

  return fs
    .readdirSync(PROJECTS_ROOT)
    .filter((file) => file.endsWith('.md'))
    .map((file) => {
      const abs = path.join(PROJECTS_ROOT, file)
      const { data, content } = parseFile(abs)
      const status: ProjectStatus = isProjectStatus(data.status) ? data.status : 'proposed'
      return {
        id: str(data, 'id', file.replace(/\.md$/, '')),
        title: str(data, 'title', file.replace(/\.md$/, '')),
        status,
        chatCount: countList(data, 'chats'),
        watch: str(data, 'watch'),
        urgent: str(data, 'urgent'),
        since: str(data, 'since'),
        body: content.trim(),
        relPath: toRepoRelative(abs),
      }
    })
    .sort((a, b) => {
      // Активные вперёд: раздел про то, что работает, а не про заготовки.
      const order = { active: 0, paused: 1, proposed: 2 }
      if (order[a.status] !== order[b.status]) return order[a.status] - order[b.status]
      return a.title.localeCompare(b.title, 'ru')
    })
}

export function readProject(id: string): Project | null {
  assertValidId(id)
  return listProjects().find((p) => p.id === id) ?? null
}

// ---------------------------------------------------------------- находки

function projectDataDir(id: string): string {
  return resolveInside(dataRoot('projectFindings'), assertValidId(id))
}

function parseDayMeta(projectId: string, date: string, data: Record<string, unknown>): ProjectDayMeta {
  return {
    date,
    projectId,
    title: str(data, 'title', date),
    summary: str(data, 'summary'),
    findings: num(data, 'findings'),
    urgent: num(data, 'urgent'),
  }
}

export function listProjectDays(projectId: string): ProjectDayMeta[] {
  let dir: string
  try {
    dir = projectDataDir(projectId)
  } catch {
    return []
  }
  if (!fs.existsSync(dir)) return []

  return fs
    .readdirSync(dir)
    .filter((file) => file.endsWith('.md'))
    .map((file) => {
      const date = file.replace(/\.md$/, '')
      const { data } = parseFile(path.join(dir, file))
      return parseDayMeta(projectId, date, data)
    })
    .sort((a, b) => b.date.localeCompare(a.date))
}

export function readProjectDay(projectId: string, date: string): ProjectDay | null {
  assertValidId(date)
  const dir = projectDataDir(projectId)
  const abs = resolveInside(dir, `${date}.md`)
  if (!fs.existsSync(abs)) return null

  const { data, content } = parseFile(abs)
  let blocks: Block[] = []
  const dataAbs = resolveInside(dir, `${date}.data.json`)
  if (fs.existsSync(dataAbs)) {
    try {
      const parsed = JSON.parse(fs.readFileSync(dataAbs, 'utf8')) as { blocks?: Block[] }
      blocks = Array.isArray(parsed.blocks) ? parsed.blocks : []
    } catch {
      // Битый JSON не должен ронять страницу: текст обзора важнее графиков.
      blocks = []
    }
  }

  return {
    ...parseDayMeta(projectId, date, data),
    body: content.trim(),
    blocks,
    relPath: toRepoRelative(abs),
  }
}

/** Сводка по теме за последние `days` дней — для карточки в списке. */
export function projectTotals(projectId: string, days = 7) {
  const all = listProjectDays(projectId)
  const cutoff = new Date(Date.now() - days * 86400_000).toISOString().slice(0, 10)
  const recent = all.filter((d) => d.date >= cutoff)
  return {
    findings: recent.reduce((sum, d) => sum + d.findings, 0),
    urgent: recent.reduce((sum, d) => sum + d.urgent, 0),
    lastDay: all[0]?.date ?? '',
    daysTracked: all.length,
  }
}
