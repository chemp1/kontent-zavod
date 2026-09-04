import fs from 'node:fs'
import path from 'node:path'

import { num, parseFile, str } from './frontmatter'
import { TELEGRAM_RULES_ROOT, assertValidId, resolveInside, toRepoRelative } from './paths'
import type { Block } from './reports-model'
import { dataRoot } from './studio-config'
import type { DigestMeta, Rule, RuleStatus } from './telegram-model'
import { isRuleStatus } from './telegram-model'

/**
 * Раздел собирается из двух источников, и это не случайность:
 *
 * - правила — `content/telegram/rules/<слаг>.md`, обычный контент в git;
 * - сводки — `<data.telegramDigests>/<дата>.md` из `studio.json`, вне git, потому что в выжимках
 *   содержание личной переписки.
 *
 * Формат сводки тот же, что у отчётов: markdown с фронтматтером плюс
 * `<дата>.data.json` рядом с числами для графиков.
 */

export interface Digest extends DigestMeta {
  body: string
  blocks: Block[]
  relPath: string
}

// ---------------------------------------------------------------- правила

export function listRules(): Rule[] {
  if (!fs.existsSync(TELEGRAM_RULES_ROOT)) return []

  return fs
    .readdirSync(TELEGRAM_RULES_ROOT)
    .filter((file) => file.endsWith('.md'))
    .map((file) => {
      const abs = path.join(TELEGRAM_RULES_ROOT, file)
      const { data, content } = parseFile(abs)
      const status: RuleStatus = isRuleStatus(data.status) ? data.status : 'proposed'
      return {
        id: str(data, 'id', file.replace(/\.md$/, '')),
        title: str(data, 'title', file.replace(/\.md$/, '')),
        status,
        scope: str(data, 'scope'),
        action: str(data, 'action'),
        since: str(data, 'since'),
        body: content.trim(),
        relPath: toRepoRelative(abs),
      }
    })
    .sort((a, b) => a.title.localeCompare(b.title, 'ru'))
}

// ---------------------------------------------------------------- сводки

function readBlocks(date: string): Block[] {
  const abs = resolveInside(dataRoot('telegramDigests'), `${date}.data.json`)
  if (!fs.existsSync(abs)) return []
  try {
    const parsed = JSON.parse(fs.readFileSync(abs, 'utf8')) as { blocks?: Block[] }
    return Array.isArray(parsed.blocks) ? parsed.blocks : []
  } catch {
    // Битый JSON не должен ронять страницу: текст сводки важнее графиков.
    return []
  }
}

function parseDigestMeta(date: string, data: Record<string, unknown>): DigestMeta {
  return {
    date,
    title: str(data, 'title', date),
    summary: str(data, 'summary'),
    chats: num(data, 'chats'),
    messages: num(data, 'messages'),
    marked: num(data, 'marked'),
    failed: num(data, 'failed'),
  }
}

export function listDigests(): DigestMeta[] {
  const dir = dataRoot('telegramDigests')
  if (!fs.existsSync(dir)) return []

  return fs
    .readdirSync(dir)
    .filter((file) => file.endsWith('.md'))
    .map((file) => {
      const date = file.replace(/\.md$/, '')
      const { data } = parseFile(path.join(dir, file))
      return parseDigestMeta(date, data)
    })
    .sort((a, b) => b.date.localeCompare(a.date))
}

export function readDigest(date: string): Digest | null {
  assertValidId(date)
  const abs = resolveInside(dataRoot('telegramDigests'), `${date}.md`)
  if (!fs.existsSync(abs)) return null

  const { data, content } = parseFile(abs)
  return {
    ...parseDigestMeta(date, data),
    body: content.trim(),
    blocks: readBlocks(date),
    relPath: toRepoRelative(abs),
  }
}

/** Сводная статистика правила за всё время — считаем по сводкам, чтобы не заводить второй источник. */
export function digestTotals(digests: DigestMeta[]) {
  return {
    runs: digests.length,
    chats: digests.reduce((sum, d) => sum + d.chats, 0),
    messages: digests.reduce((sum, d) => sum + d.messages, 0),
    failed: digests.reduce((sum, d) => sum + d.failed, 0),
    lastRun: digests[0]?.date ?? '',
  }
}
