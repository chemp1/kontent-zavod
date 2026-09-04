import { NextResponse } from 'next/server'

import { commitPaths, isDirty } from '@/lib/git'
import { findNode, nodeFileHash, readNodeFile, writeNodeFile } from '@/lib/skill-map'

export const runtime = 'nodejs'

export async function PUT(
  request: Request,
  { params }: { params: Promise<{ nodeId: string }> },
) {
  const { nodeId } = await params
  const node = findNode(nodeId)

  if (!node) return NextResponse.json({ error: 'Блок не найден' }, { status: 404 })
  if (!node.editable) {
    return NextResponse.json(
      { error: `Этот файл из интерфейса не редактируется: ${node.path}` },
      { status: 403 },
    )
  }

  let content = ''
  let baseHash = ''
  try {
    const body = (await request.json()) as { content?: unknown; baseHash?: unknown }
    if (typeof body.content !== 'string') {
      return NextResponse.json({ error: 'Ожидалось поле content' }, { status: 400 })
    }
    if (typeof body.baseHash !== 'string') {
      return NextResponse.json({ error: 'Ожидалось поле baseHash' }, { status: 400 })
    }
    content = body.content
    baseHash = body.baseHash
  } catch {
    return NextResponse.json({ error: 'Ожидался JSON' }, { status: 400 })
  }

  if (!content.trim()) {
    return NextResponse.json({ error: 'Пустой файл сохранять нельзя' }, { status: 400 })
  }

  // Файл могли изменить из другой сессии Claude или второй вкладки, пока эта
  // страница была открыта. Тогда на диске уже не то, что редактировали, и
  // сохранение затёрло бы чужую правку без следа.
  if (nodeFileHash(node) !== baseHash) {
    return NextResponse.json(
      {
        error:
          'Файл изменился с тех пор, как вы его открыли — скорее всего, из другой сессии. ' +
          'Обновите страницу и перенесите правки заново, иначе чужие потеряются.',
      },
      { status: 409 },
    )
  }

  if (readNodeFile(node).trimEnd() === content.trimEnd()) {
    // Текст тот же. Это либо «нечего делать», либо след прошлой неудачи: запись
    // прошла, а коммит упал — например, на index.lock от параллельной сессии.
    // Без этой проверки повтор сохранения вечно отвечал бы «изменений нет»,
    // а файл так и остался бы незакоммиченным.
    if (await isDirty(node.path)) {
      const result = await commitPaths(`Правка скилла: ${node.label}`, [node.path])
      return NextResponse.json(result)
    }
    return NextResponse.json({ committed: false, reason: 'изменений нет' })
  }

  try {
    writeNodeFile(node, content)
    const result = await commitPaths(`Правка скилла: ${node.label}`, [node.path])
    return NextResponse.json(result)
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Не удалось сохранить'
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
