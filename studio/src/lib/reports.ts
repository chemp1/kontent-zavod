import fs from 'node:fs'
import path from 'node:path'
import matter from 'gray-matter'

import { REPORTS_ROOT, assertValidId, resolveInside, toRepoRelative } from './paths'
import type { Block, Report, ReportMeta } from './reports-model'

/**
 * Отчёт — это `content/reports/<слаг>.md` с фронтматтером. Числа для графиков
 * лежат рядом в `<слаг>.data.json`: markdown остаётся читаемым текстом, а
 * данные не приходится вклеивать в него простынёй.
 */

/**
 * Разбор с запасным вариантом: незакавыченное двоеточие в `summary` — обычная
 * опечатка, и она роняет YAML целиком. Отчёт с битым фронтматтером должен
 * открыться текстом и с понятным заголовком, а не утащить за собой весь раздел.
 */
function parseFile(abs: string): { data: Record<string, unknown>; content: string } {
  const raw = fs.readFileSync(abs, 'utf8')
  try {
    const parsed = matter(raw)
    return { data: parsed.data as Record<string, unknown>, content: parsed.content }
  } catch {
    const body = raw.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n?/, '')
    return { data: {}, content: body }
  }
}

function parseMeta(slug: string, data: Record<string, unknown>): ReportMeta {
  return {
    slug,
    title: typeof data.title === 'string' ? data.title : slug,
    date: typeof data.date === 'string' ? data.date : '',
    summary: typeof data.summary === 'string' ? data.summary : '',
    tags: Array.isArray(data.tags) ? data.tags.map(String) : [],
  }
}

function readBlocks(slug: string): Block[] {
  const abs = resolveInside(REPORTS_ROOT, `${slug}.data.json`)
  if (!fs.existsSync(abs)) return []
  try {
    const parsed = JSON.parse(fs.readFileSync(abs, 'utf8')) as { blocks?: Block[] }
    return Array.isArray(parsed.blocks) ? parsed.blocks : []
  } catch {
    // Битый JSON не должен ронять страницу: текст отчёта важнее графиков.
    return []
  }
}

export function listReports(): ReportMeta[] {
  if (!fs.existsSync(REPORTS_ROOT)) return []

  return fs
    .readdirSync(REPORTS_ROOT)
    .filter((file) => file.endsWith('.md'))
    .map((file) => {
      const slug = file.replace(/\.md$/, '')
      const { data } = parseFile(path.join(REPORTS_ROOT, file))
      return parseMeta(slug, data)
    })
    .sort((a, b) => b.date.localeCompare(a.date))
}

export function readReport(slug: string): Report | null {
  assertValidId(slug)
  const abs = resolveInside(REPORTS_ROOT, `${slug}.md`)
  if (!fs.existsSync(abs)) return null

  const { data, content } = parseFile(abs)
  return {
    ...parseMeta(slug, data),
    body: content.trim(),
    blocks: readBlocks(slug),
    relPath: toRepoRelative(abs),
  }
}
