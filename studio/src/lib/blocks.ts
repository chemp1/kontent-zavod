import type { Block } from './reports-model'

/**
 * Графики ставятся по тексту маркером `[[block:N]]` на отдельной строке.
 * Так материал читается статьёй: цифра стоит рядом с абзацем, который её
 * объясняет, а не свалена в общую галерею сверху.
 *
 * Без `node:fs` — модуль общий для отчётов и сводок по Telegram.
 */
const MARKER = /^\[\[block:(\d+)\]\]$/gm

export type BodyPart = { kind: 'md' | 'block'; value: string | Block }

export function splitBody(body: string, blocks: Block[]): BodyPart[] {
  const parts: BodyPart[] = []
  const used = new Set<number>()
  let last = 0

  for (const match of body.matchAll(MARKER)) {
    const index = Number(match[1])
    const block = blocks[index]
    if (!block) continue

    const text = body.slice(last, match.index).trim()
    if (text) parts.push({ kind: 'md', value: text })
    parts.push({ kind: 'block', value: block })
    used.add(index)
    last = (match.index ?? 0) + match[0].length
  }

  const tail = body.slice(last).trim()
  if (tail) parts.push({ kind: 'md', value: tail })

  // Блоки, которые забыли поставить в текст, показываем в конце: молча
  // терять посчитанные цифры хуже, чем показать их не на месте.
  blocks.forEach((block, i) => {
    if (!used.has(i)) parts.push({ kind: 'block', value: block })
  })

  return parts
}
