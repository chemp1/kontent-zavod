import { NextResponse } from 'next/server'

import { SOURCES, type Source, createIdea } from '@/lib/content'
import { commitPaths } from '@/lib/git'

export const runtime = 'nodejs'

export async function POST(request: Request) {
  let payload: { title?: unknown; sourceText?: unknown; source?: unknown; tags?: unknown }
  try {
    payload = await request.json()
  } catch {
    return NextResponse.json({ error: 'Ожидался JSON' }, { status: 400 })
  }

  const title = typeof payload.title === 'string' ? payload.title.trim() : ''
  if (!title) {
    return NextResponse.json({ error: 'Нужен заголовок идеи' }, { status: 400 })
  }

  const source: Source =
    typeof payload.source === 'string' && (SOURCES as readonly string[]).includes(payload.source)
      ? (payload.source as Source)
      : 'text'

  const tags =
    typeof payload.tags === 'string'
      ? payload.tags
          .split(',')
          .map((tag) => tag.trim())
          .filter(Boolean)
      : []

  try {
    const idea = createIdea({
      title,
      source,
      sourceText: typeof payload.sourceText === 'string' ? payload.sourceText : undefined,
      tags,
    })

    // Файлы уже на диске; отказ git — не повод отвечать ошибкой.
    const commit = await commitPaths(`Завести идею: ${title}`, [`${idea.relDir}/`])

    return NextResponse.json({ id: idea.id, ...commit })
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Не удалось создать идею'
    return NextResponse.json({ error: message }, { status: 400 })
  }
}
