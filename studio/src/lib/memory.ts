import fs from 'node:fs'
import path from 'node:path'
import matter from 'gray-matter'

import { MEMORY_ROOT, resolveInside, toRepoRelative } from './paths'

/**
 * Память разложена по уровням намеренно. Если сваливать всё в одну кучу,
 * случайная формулировка из черновика получает тот же вес, что подтверждённое
 * правило, и база быстро начинает противоречить сама себе.
 */
export const MEMORY_LAYERS = [
  {
    file: 'facts.md',
    title: 'Факты',
    description: 'Постоянное: кто я, чем занимаюсь, что уже сделал. Меняется редко.',
  },
  {
    file: 'rules.md',
    title: 'Правила стиля',
    description: 'Подтверждённые правила голоса. Сюда попадает только то, что автор утвердил явно.',
  },
  {
    file: 'themes.md',
    title: 'Темы и позиции',
    description: 'О чём я пишу постоянно и какую позицию занимаю.',
  },
  {
    file: 'examples.md',
    title: 'Удачные примеры',
    description: 'Опубликованные посты, которые получились — как калибровка интонации.',
  },
  {
    file: 'edits.md',
    title: 'Правки и отказы',
    description: 'Что я постоянно переписываю и какие варианты отклонил. Сырьё для новых правил.',
  },
] as const

export interface MemoryLayer {
  file: string
  title: string
  description: string
  body: string
  relPath: string
  exists: boolean
}

export interface Proposal {
  id: string
  title: string
  status: 'pending' | 'accepted' | 'rejected'
  target: string
  evidence: string[]
  body: string
  relPath: string
}

export function readLayers(): MemoryLayer[] {
  return MEMORY_LAYERS.map((layer) => {
    const abs = path.join(MEMORY_ROOT, layer.file)
    const exists = fs.existsSync(abs)
    return {
      ...layer,
      exists,
      relPath: toRepoRelative(abs),
      body: exists ? matter(fs.readFileSync(abs, 'utf8')).content.trim() : '',
    }
  })
}

export function readProposals(): Proposal[] {
  const dir = path.join(MEMORY_ROOT, 'proposals')
  if (!fs.existsSync(dir)) return []

  return fs
    .readdirSync(dir)
    .filter((file) => file.endsWith('.md'))
    .map((file) => {
      const abs = resolveInside(dir, file)
      const parsed = matter(fs.readFileSync(abs, 'utf8'))
      const data = parsed.data as Record<string, unknown>
      const status: Proposal['status'] =
        data.status === 'accepted' || data.status === 'rejected' ? data.status : 'pending'
      return {
        id: file.replace(/\.md$/, ''),
        title: typeof data.title === 'string' ? data.title : file,
        status,
        target: typeof data.target === 'string' ? data.target : 'rules.md',
        evidence: Array.isArray(data.evidence) ? data.evidence.map(String) : [],
        body: parsed.content.trim(),
        relPath: toRepoRelative(abs),
      }
    })
    .sort((a, b) => a.id.localeCompare(b.id))
}
