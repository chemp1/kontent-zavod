import { NextResponse } from 'next/server'

import { listCandidates, readCandidate, setCandidateStatus } from '@/lib/candidates'
import { createIdea } from '@/lib/content'
import { commitPaths } from '@/lib/git'

export const runtime = 'nodejs'

/**
 * Решение по кандидату из звонка: принять (завести идею), отклонить, вернуть.
 *
 * Исходником идеи становится тело кандидата — прямая речь автора. Именно её
 * скиллы ставят выше собственного синтеза, поэтому пересказывать нечего.
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
    const candidate = readCandidate(slug)
    if (!candidate) return NextResponse.json({ error: `Кандидат ${slug} не найден` }, { status: 404 })

    if (action === 'reject' || action === 'reset') {
      const updated = setCandidateStatus(slug, action === 'reject' ? 'rejected' : 'pending')
      const commit = await commitPaths(
        `Кандидаты: ${action === 'reject' ? 'отклонён' : 'возвращён'} — ${updated.title}`,
        [updated.relPath],
      )
      return NextResponse.json({ status: updated.status, ...commit })
    }

    if (action !== 'accept') {
      return NextResponse.json({ error: `Неизвестное действие: ${action}` }, { status: 400 })
    }

    if (candidate.ideaId) return NextResponse.json({ ideaId: candidate.ideaId })

    const idea = createIdea({
      title: candidate.title,
      source: 'transcript',
      sourceText: `${candidate.body}\n\nИз звонка ${candidate.date}.`,
      tags: ['из звонка'],
    })
    const updated = setCandidateStatus(slug, 'accepted', idea.id)

    const commit = await commitPaths(`Идея из звонка: ${candidate.title}`, [`${idea.relDir}/`, updated.relPath])
    return NextResponse.json({
      ideaId: idea.id,
      left: listCandidates().filter((c) => c.status === 'pending').length,
      ...commit,
    })
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Не удалось обновить кандидата'
    return NextResponse.json({ error: message }, { status: 400 })
  }
}
