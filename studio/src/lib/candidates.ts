import fs from 'node:fs'
import path from 'node:path'
import matter from 'gray-matter'

import { isPlatform, type Platform } from './content-model'
import { parseFile, str } from './frontmatter'
import { PLAN_CANDIDATES_ROOT, assertValidId, resolveInside, toRepoRelative } from './paths'

/**
 * Идеи-кандидаты из собственных звонков автора: их кладёт внешний майнер,
 * принимает или отклоняет человек.
 *
 * В файле кандидата — только прямая речь автора. Расшифровки целиком, чужие
 * реплики и имена собеседников остаются у майнера в `.data/`: content/ уходит
 * в git, а на звонках были другие люди.
 */

export const CANDIDATE_STATUSES = ['pending', 'accepted', 'rejected'] as const
export type CandidateStatus = (typeof CANDIDATE_STATUSES)[number]

export const CANDIDATE_STATUS_LABELS: Record<CandidateStatus, string> = {
  pending: 'На решение',
  accepted: 'Принято',
  rejected: 'Отклонено',
}

export interface Candidate {
  slug: string
  title: string
  /** Дата звонка, из которого выросла мысль. */
  date: string
  found: string
  platform: Platform | ''
  status: CandidateStatus
  ideaId: string
  body: string
  relPath: string
}

function isCandidateStatus(value: unknown): value is CandidateStatus {
  return typeof value === 'string' && (CANDIDATE_STATUSES as readonly string[]).includes(value)
}

function parseCandidate(slug: string, abs: string): Candidate {
  const { data, content } = parseFile(abs)
  const platform = str(data, 'platform')
  const status = data.status
  return {
    slug,
    title: str(data, 'title', slug),
    date: str(data, 'date'),
    found: str(data, 'found'),
    platform: isPlatform(platform) ? platform : '',
    status: isCandidateStatus(status) ? status : 'pending',
    ideaId: str(data, 'idea'),
    body: content.trim(),
    relPath: toRepoRelative(abs),
  }
}

export function listCandidates(): Candidate[] {
  if (!fs.existsSync(PLAN_CANDIDATES_ROOT)) return []
  return fs
    .readdirSync(PLAN_CANDIDATES_ROOT)
    .filter((file) => file.endsWith('.md'))
    .map((file) =>
      parseCandidate(file.replace(/\.md$/, ''), path.join(PLAN_CANDIDATES_ROOT, file)),
    )
    .sort((a, b) => b.date.localeCompare(a.date) || a.title.localeCompare(b.title, 'ru'))
}

export function readCandidate(slug: string): Candidate | null {
  assertValidId(slug)
  const abs = resolveInside(PLAN_CANDIDATES_ROOT, `${slug}.md`)
  if (!fs.existsSync(abs)) return null
  return parseCandidate(slug, abs)
}

export function setCandidateStatus(
  slug: string,
  status: CandidateStatus,
  ideaId?: string,
): Candidate {
  assertValidId(slug)
  const abs = resolveInside(PLAN_CANDIDATES_ROOT, `${slug}.md`)
  if (!fs.existsSync(abs)) throw new Error(`Кандидат ${slug} не найден`)

  const parsed = matter(fs.readFileSync(abs, 'utf8'))
  const frontmatter: Record<string, unknown> = {
    ...(parsed.data as Record<string, unknown>),
    status,
  }
  if (ideaId) {
    assertValidId(ideaId)
    frontmatter.idea = ideaId
  }

  fs.writeFileSync(abs, matter.stringify(parsed.content, frontmatter), 'utf8')
  const candidate = readCandidate(slug)
  if (!candidate) throw new Error(`Кандидат ${slug} не читается после правки`)
  return candidate
}
