import { NextResponse } from 'next/server'

import { PLATFORM_LABELS } from '@/lib/content-model'
import { commitPaths } from '@/lib/git'
import { createSlot, slotInputFrom } from '@/lib/plan'

export const runtime = 'nodejs'

export async function POST(request: Request) {
  let payload: Record<string, unknown>
  try {
    payload = (await request.json()) as Record<string, unknown>
  } catch {
    return NextResponse.json({ error: 'Ожидался JSON' }, { status: 400 })
  }

  try {
    const { slot, touched } = createSlot(slotInputFrom(payload))
    const commit = await commitPaths(
      `План: ${PLATFORM_LABELS[slot.platform]} ${slot.date} ${slot.time}`,
      touched,
    )
    return NextResponse.json({ id: slot.id, ...commit })
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Не удалось создать слот'
    return NextResponse.json({ error: message }, { status: 400 })
  }
}
