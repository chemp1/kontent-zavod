'use client'

import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { apiUrl } from '@/lib/base-path'

export function FileEditor({
  nodeId,
  initialContent,
  baseHash,
}: {
  nodeId: string
  initialContent: string
  /** Отпечаток файла на момент открытия — сервер по нему ловит правку из другой сессии. */
  baseHash: string
}) {
  const router = useRouter()
  const [content, setContent] = useState(initialContent)
  const [status, setStatus] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  const changed = content !== initialContent

  async function save() {
    setPending(true)
    setError(null)
    setStatus(null)

    const response = await fetch(apiUrl(`/api/skill/${nodeId}`), {
      method: 'PUT',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ content, baseHash }),
    })

    const body = (await response.json().catch(() => ({}))) as {
      committed?: boolean
      sha?: string
      reason?: string
      error?: string
    }

    if (!response.ok) {
      setError(body.error ?? 'Не удалось сохранить')
      setPending(false)
      return
    }

    setStatus(
      body.committed
        ? `Сохранено и закоммичено (${body.sha?.slice(0, 7)})`
        : `Сохранено без коммита: ${body.reason ?? 'изменений нет'}`,
    )
    setPending(false)
    router.refresh()
  }

  return (
    <div>
      <textarea
        value={content}
        onChange={(event) => setContent(event.target.value)}
        spellCheck={false}
        rows={30}
        className="w-full rounded-lg border border-border bg-surface p-4 font-mono text-xs leading-relaxed outline-none focus:border-accent"
      />

      <div className="mt-3 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={save}
          disabled={pending || !changed}
          className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {pending ? 'Сохраняю…' : 'Сохранить и закоммитить'}
        </button>

        {changed ? (
          <button
            type="button"
            onClick={() => {
              setContent(initialContent)
              setStatus(null)
              setError(null)
            }}
            className="text-sm text-muted hover:text-text"
          >
            Отменить правки
          </button>
        ) : null}

        {status ? <span className="text-sm text-ok">{status}</span> : null}
        {error ? <span className="text-sm text-danger">{error}</span> : null}
      </div>

      <p className="mt-2 text-xs text-muted">
        Правится всё тело файла целиком, включая frontmatter. Сломанный frontmatter =
        скилл перестаёт грузиться, поэтому шапку меняйте осознанно.
      </p>
    </div>
  )
}
