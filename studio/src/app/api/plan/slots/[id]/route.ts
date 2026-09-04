import { NextResponse } from 'next/server'

import { PLATFORM_LABELS } from '@/lib/content-model'
import { commitPaths } from '@/lib/git'
import { deleteSlot, slotInputFrom, updateSlot } from '@/lib/plan'

export const runtime = 'nodejs'

export async function PATCH(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params

  let payload: Record<string, unknown>
  try {
    payload = (await request.json()) as Record<string, unknown>
  } catch {
    return NextResponse.json({ error: 'Ожидался JSON' }, { status: 400 })
  }

  try {
    const { slot, touched } = updateSlot(id, slotInputFrom(payload))
    const commit = await commitPaths(
      `План: ${PLATFORM_LABELS[slot.platform]} ${slot.date} ${slot.time} — правка`,
      touched,
    )
    return NextResponse.json({ id: slot.id, ...commit })
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Не удалось сохранить слот'
    return NextResponse.json({ error: message }, { status: 400 })
  }
}

export async function DELETE(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params

  try {
    const { slot, touched } = deleteSlot(id)
    const commit = await commitPaths(
      `План: снят слот ${PLATFORM_LABELS[slot.platform]} ${slot.date} ${slot.time}`,
      touched,
    )
    return NextResponse.json({ ok: true, ...commit })
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Не удалось удалить слот'
    return NextResponse.json({ error: message }, { status: 400 })
  }
}
