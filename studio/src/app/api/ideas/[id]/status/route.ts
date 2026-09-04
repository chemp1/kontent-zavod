import { NextResponse } from 'next/server'

import { STATUSES, STATUS_LABELS, type Status, setStatus } from '@/lib/content'
import { commitPaths } from '@/lib/git'

export const runtime = 'nodejs'

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params

  let status: string
  try {
    const body = (await request.json()) as { status?: unknown }
    status = typeof body.status === 'string' ? body.status : ''
  } catch {
    return NextResponse.json({ error: 'Ожидался JSON' }, { status: 400 })
  }

  if (!(STATUSES as readonly string[]).includes(status)) {
    return NextResponse.json({ error: `Неизвестный статус: ${status}` }, { status: 400 })
  }

  try {
    const idea = setStatus(id, status as Status)
    const commit = await commitPaths(
      `Статус «${idea.title}» → ${STATUS_LABELS[idea.status]}`,
      [`${idea.relDir}/idea.md`],
    )
    return NextResponse.json({ status: idea.status, ...commit })
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Не удалось сменить статус'
    return NextResponse.json({ error: message }, { status: 400 })
  }
}
