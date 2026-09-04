import { NextResponse } from 'next/server'

import { createIdea } from '@/lib/content'
import { commitPaths } from '@/lib/git'
import { readTrend, setTrendStatus } from '@/lib/trends'

export const runtime = 'nodejs'

/**
 * Что человек делает с карточкой тренда: берёт в работу, отправляет мимо или
 * возвращает в ленту. Текст карточки студия не трогает — его кладёт внешний сборщик.
 */
export async function POST(request: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params

  let action: string
  try {
    const body = (await request.json()) as { action?: unknown }
    action = typeof body.action === 'string' ? body.action : ''
  } catch {
    return NextResponse.json({ error: 'Ожидался JSON' }, { status: 400 })
  }

  try {
    const trend = readTrend(slug)
    if (!trend) return NextResponse.json({ error: `Карточка ${slug} не найдена` }, { status: 404 })

    if (action === 'skip' || action === 'reset') {
      const updated = setTrendStatus(slug, action === 'skip' ? 'skipped' : 'new')
      const commit = await commitPaths(
        `Тренды: ${action === 'skip' ? 'мимо' : 'вернул в ленту'} — ${updated.title}`,
        [updated.relPath],
      )
      return NextResponse.json({ status: updated.status, ...commit })
    }

    if (action !== 'idea') {
      return NextResponse.json({ error: `Неизвестное действие: ${action}` }, { status: 400 })
    }

    if (trend.ideaId) {
      return NextResponse.json({ ideaId: trend.ideaId })
    }

    // Исходник идеи — карточка целиком: суть, углы и ссылка. Скиллы ставят
    // материалы выше собственного синтеза, поэтому пересказывать её не нужно.
    const idea = createIdea({
      title: trend.title,
      source: 'link',
      sourceText: `${trend.body}\n\nИсточник: ${trend.url}`,
      tags: ['тренд', trend.source],
    })
    const updated = setTrendStatus(slug, 'used', idea.id)

    const commit = await commitPaths(`Идея из тренда: ${trend.title}`, [`${idea.relDir}/`, updated.relPath])
    return NextResponse.json({ ideaId: idea.id, ...commit })
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Не удалось обновить карточку'
    return NextResponse.json({ error: message }, { status: 400 })
  }
}
