'use client'

import { useRouter } from 'next/navigation'
import { useState } from 'react'

import { apiUrl } from '@/lib/base-path'

/** Решение по идее из звонка: принять (заводится идея), отклонить, вернуть. */
export function CandidateActions({ slug, status }: { slug: string; status: string }) {
  const router = useRouter()
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function send(action: 'accept' | 'reject' | 'reset') {
    setPending(true)
    setError(null)

    const response = await fetch(apiUrl(`/api/candidates/${slug}`), {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ action }),
    })

    if (!response.ok) {
      const body = await response.json().catch(() => ({ error: 'Не удалось' }))
      setError(body.error ?? 'Не удалось')
      setPending(false)
      return
    }

    const body = (await response.json()) as { ideaId?: string }
    setPending(false)
    if (action === 'accept' && body.ideaId) {
      router.push(`/ideas/${body.ideaId}`)
      return
    }
    router.refresh()
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      {status !== 'accepted' ? (
        <button
          type="button"
          disabled={pending}
          onClick={() => void send('accept')}
          className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white disabled:opacity-60"
        >
          Принять
        </button>
      ) : null}
      {status === 'pending' ? (
        <button
          type="button"
          disabled={pending}
          onClick={() => void send('reject')}
          className="text-sm text-muted hover:text-text disabled:opacity-60"
        >
          Отклонить
        </button>
      ) : null}
      {status === 'rejected' ? (
        <button
          type="button"
          disabled={pending}
          onClick={() => void send('reset')}
          className="text-sm text-muted hover:text-text disabled:opacity-60"
        >
          Вернуть
        </button>
      ) : null}
      {error ? <span className="text-sm text-danger">{error}</span> : null}
    </div>
  )
}
