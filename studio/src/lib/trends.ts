import fs from 'node:fs'
import path from 'node:path'
import matter from 'gray-matter'

import { parseFile, str } from './frontmatter'
import { TRENDS_ROOT, TRENDS_SOURCES_FILE, assertValidId, resolveInside, toRepoRelative } from './paths'
import { isTrendStatus, type Trend, type TrendKind, type TrendStatus } from './trends-model'

export * from './trends-model'

/**
 * Лента трендов: карточки от внешнего сборщика плюс список источников, по которому
 * подписи фидов в интерфейсе совпадают с тем, что реально опрашивает сборщик.
 */

export interface Feed {
  id: string
  title: string
  kind: TrendKind
}

function parseKind(value: string): TrendKind {
  return value === 'video' || value === 'discussion' ? value : 'article'
}

export function listFeeds(): Feed[] {
  if (!fs.existsSync(TRENDS_SOURCES_FILE)) return []
  const { data } = parseFile(TRENDS_SOURCES_FILE)
  if (!Array.isArray(data.feeds)) return []

  return data.feeds
    .map((entry) => {
      const item = (entry ?? {}) as Record<string, unknown>
      const id = str(item, 'id')
      if (!id) return null
      return { id, title: str(item, 'title', id), kind: parseKind(str(item, 'kind')) }
    })
    .filter((feed): feed is Feed => feed !== null)
}

function parseTrend(slug: string, abs: string, feeds: Map<string, Feed>): Trend {
  const { data, content } = parseFile(abs)
  const source = str(data, 'source')
  const status = data.status
  return {
    slug,
    title: str(data, 'title', slug),
    source,
    sourceTitle: feeds.get(source)?.title ?? source,
    kind: parseKind(str(data, 'kind')),
    url: str(data, 'url'),
    published: str(data, 'published'),
    found: str(data, 'found'),
    status: isTrendStatus(status) ? status : 'new',
    ideaId: str(data, 'idea'),
    body: content.trim(),
    relPath: toRepoRelative(abs),
  }
}

export function listTrends(): Trend[] {
  if (!fs.existsSync(TRENDS_ROOT)) return []
  const feeds = new Map(listFeeds().map((feed) => [feed.id, feed]))

  return fs
    .readdirSync(TRENDS_ROOT)
    .filter((file) => file.endsWith('.md') && file !== 'sources.md')
    .map((file) => parseTrend(file.replace(/\.md$/, ''), path.join(TRENDS_ROOT, file), feeds))
    .sort((a, b) => (b.found || b.published).localeCompare(a.found || a.published))
}

export function readTrend(slug: string): Trend | null {
  assertValidId(slug)
  const abs = resolveInside(TRENDS_ROOT, `${slug}.md`)
  if (!fs.existsSync(abs)) return null
  const feeds = new Map(listFeeds().map((feed) => [feed.id, feed]))
  return parseTrend(slug, abs, feeds)
}

/**
 * Статус карточки — единственное, что студия в ней меняет. Текст пишет сборщик,
 * решение принимает человек: «беру» или «мимо».
 */
export function setTrendStatus(slug: string, status: TrendStatus, ideaId?: string): Trend {
  assertValidId(slug)
  const abs = resolveInside(TRENDS_ROOT, `${slug}.md`)
  if (!fs.existsSync(abs)) throw new Error(`Карточка ${slug} не найдена`)

  const raw = fs.readFileSync(abs, 'utf8')
  const parsed = matter(raw)
  const frontmatter: Record<string, unknown> = { ...(parsed.data as Record<string, unknown>), status }
  if (ideaId) {
    assertValidId(ideaId)
    frontmatter.idea = ideaId
  }

  fs.writeFileSync(abs, matter.stringify(parsed.content, frontmatter), 'utf8')
  const trend = readTrend(slug)
  if (!trend) throw new Error(`Карточка ${slug} не читается после правки`)
  return trend
}
